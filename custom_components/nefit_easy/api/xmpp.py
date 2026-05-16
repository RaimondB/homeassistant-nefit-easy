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
import ssl
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
        # _ready resolves either way; _error carries the failure reason so
        # async_connect can raise instead of silently "succeeding".
        self._ready = asyncio.Event()
        self._error: Exception | None = None
        self._ping_task: asyncio.Task | None = None

        # Bosch only offers SCRAM-SHA-1; never fall back to PLAIN.
        self["feature_mechanisms"].unencrypted_plain = False

        # The Bosch backend presents a certificate that does not validate
        # against the public trust store. Every working Nefit client
        # disables verification here; the message bodies are AES-encrypted
        # independently of TLS, so confidentiality does not rely on it.
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
        self.add_event_handler("failed_auth", self._on_failed_auth)
        self.add_event_handler("disconnected", self._on_disconnected)
        self.add_event_handler("connection_failed", self._on_connection_failed)
        self.add_event_handler("session_bind", self._on_session_bind)

    # -- lifecycle --------------------------------------------------------
    def set_message_callback(self, cb: Callable[[str], None]) -> None:
        self._message_cb = cb

    async def async_connect(self, timeout: float = 30.0) -> None:  # noqa: ASYNC109
        """Connect and wait until the XMPP session is live (or fail)."""
        self._ready.clear()
        self._error = None
        _LOGGER.debug(
            "Connecting to Nefit backend %s:%s as %s",
            self._host,
            self._port,
            self._from,
        )
        # slixmpp 1.15: ClientXMPP.connect(host, port); STARTTLS is applied
        # automatically. Returns a future we don't await — readiness is
        # signalled via the session_start / failed_auth / disconnected events.
        self.connect(self._host, self._port)
        try:
            async with asyncio.timeout(timeout):
                await self._ready.wait()
        except TimeoutError as err:
            _LOGGER.error(
                "Timed out after %ss connecting to %s:%s — no XMPP session. "
                "Check that the Home Assistant host can resolve and reach "
                "%s on port %s (DNS / firewall / network).",
                timeout,
                self._host,
                self._port,
                self._host,
                self._port,
            )
            self.disconnect()
            raise NefitConnectionError(
                f"Timed out establishing XMPP session to {self._host}:{self._port}"
            ) from err
        if self._error is not None:
            _LOGGER.error("Connection to Nefit backend failed: %s", self._error)
            self.disconnect()
            raise self._error
        _LOGGER.debug("Nefit XMPP session established")

    async def async_disconnect(self) -> None:
        if self._ping_task:
            self._ping_task.cancel()
            self._ping_task = None
        self.disconnect()

    # -- event handlers ---------------------------------------------------
    def _on_session_bind(self, jid: object) -> None:
        _LOGGER.debug("XMPP resource bound: %s", jid)

    async def _on_session_start(self, _event: object) -> None:
        _LOGGER.debug("XMPP session started; sending presence")
        self.send_presence()
        if self._ping_task is None:
            self._ping_task = asyncio.create_task(self._ping_loop())
        self._ready.set()

    def _on_failed_auth(self, _event: object) -> None:
        _LOGGER.warning("Nefit authentication rejected by the backend")
        self._error = NefitAuthError(
            "Authentication failed — check serial number, access key and password"
        )
        self._ready.set()

    def _on_connection_failed(self, reason: object) -> None:
        _LOGGER.error(
            "TCP/TLS connection to %s:%s failed: %s",
            self._host,
            self._port,
            reason,
        )
        if not self._ready.is_set():
            if self._error is None:
                self._error = NefitConnectionError(
                    f"Could not reach {self._host}:{self._port}: {reason}"
                )
            self._ready.set()

    def _on_disconnected(self, reason: object) -> None:
        # Only meaningful before we are ready; afterwards reconnects are fine.
        if not self._ready.is_set():
            _LOGGER.error(
                "Disconnected from %s before session start: %s",
                self._host,
                reason,
            )
            if self._error is None:
                self._error = NefitConnectionError(
                    f"Disconnected before session start: {reason}"
                )
            self._ready.set()
        else:
            _LOGGER.debug("XMPP disconnected: %s", reason)

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
        """Send a raw (already framed/encrypted) HTTP body to the gateway.

        Must be a ``normal`` message — the Bosch gateway ignores ``chat``
        typed messages (matches nefit-easy-core / aionefit).
        """
        self.send_message(mto=self._to, mfrom=self._from, mbody=body, mtype="normal")
