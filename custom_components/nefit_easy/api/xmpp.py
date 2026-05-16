"""XMPP transport for the Nefit/Bosch Easy cloud protocol.

HTTP/1.1 GET/PUT requests are tunnelled inside XMPP <message> chat stanza
bodies; responses arrive the same way. Auth is SASL SCRAM-SHA-1 with a
derived JID and an access-key-prefixed password.

This module owns only the transport (connect, send-body, recv-body, ping,
reconnect). Body crypto and the request/response HTTP framing live in
``client.py``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

import slixmpp

from ..const import (
    ACCESSKEY_PREFIX,
    DEFAULT_HOST,
    DEFAULT_PORT,
    RRC_CONTACT_PREFIX,
    RRC_GATEWAY_PREFIX,
)
from .errors import NefitAuthError, NefitConnectionError

_LOGGER = logging.getLogger(__name__)

_PING_INTERVAL = 30.0


class NefitXMPP(slixmpp.ClientXMPP):
    """Minimal XMPP client tuned for the Bosch Easy backend."""

    def __init__(
        self,
        serial_number: str,
        access_key: str,
        password: str,
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> None:
        self._from = f"{RRC_CONTACT_PREFIX}{serial_number}@{host}"
        self._to = f"{RRC_GATEWAY_PREFIX}{serial_number}@{host}"
        super().__init__(self._from, ACCESSKEY_PREFIX + access_key)

        self._host = host
        self._port = port
        self._message_cb: Callable[[str], None] | None = None
        self._connected_evt = asyncio.Event()
        self._ping_task: asyncio.Task | None = None

        # Bosch backend only offers SCRAM-SHA-1.
        self["feature_mechanisms"].unencrypted_plain = False
        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
        self.add_event_handler("failed_auth", self._on_failed_auth)

    # -- lifecycle --------------------------------------------------------
    def set_message_callback(self, cb: Callable[[str], None]) -> None:
        self._message_cb = cb

    async def async_connect(self, timeout: float = 30.0) -> None:
        """Connect and wait until the XMPP session is live."""
        self._connected_evt.clear()
        self.connect((self._host, self._port), use_ssl=False)
        try:
            async with asyncio.timeout(timeout):
                await self._connected_evt.wait()
        except TimeoutError as err:
            self.disconnect()
            raise NefitConnectionError("Timed out establishing XMPP session") from err

    async def async_disconnect(self) -> None:
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        self.disconnect()

    # -- event handlers ---------------------------------------------------
    async def _on_session_start(self, _event: object) -> None:
        self.send_presence()
        self._connected_evt.set()
        if self._ping_task is None:
            self._ping_task = asyncio.create_task(self._ping_loop())

    def _on_failed_auth(self, _event: object) -> None:
        self._connected_evt.set()  # unblock the waiter so it can raise
        raise NefitAuthError("XMPP authentication failed (serial/access key)")

    def _on_message(self, msg: slixmpp.stanza.Message) -> None:
        if self._message_cb and msg["type"] in ("chat", "normal"):
            body = msg["body"]
            if body:
                self._message_cb(body)

    async def _ping_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(_PING_INTERVAL)
                self.send_presence()
        except asyncio.CancelledError:
            pass

    # -- send -------------------------------------------------------------
    def send_body(self, body: str) -> None:
        """Send a raw (already framed/encrypted) HTTP body to the gateway."""
        self.send_message(mto=self._to, mfrom=self._from, mbody=body, mtype="chat")
