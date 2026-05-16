"""High-level Nefit/Bosch Easy client.

Wraps the XMPP transport with HTTP-in-stanza framing, AES body crypto, a
single-flight lock (the cloud allows one in-flight request) and typed
errors. This is the only surface the HA layer talks to.
"""

from __future__ import annotations

import asyncio
import json
import logging
from functools import partial
from typing import TYPE_CHECKING, Any

from .crypto import NefitCrypto
from .errors import NefitAuthError, NefitConnectionError, NefitTimeoutError
from .xmpp import NefitXMPP

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 30.0
_USER_AGENT = "NefitEasy"


async def async_create_client(
    hass: HomeAssistant, serial_number: str, access_key: str, password: str
) -> NefitClient:
    """Build a NefitClient off the event loop, bound to HA's loop.

    slixmpp's ClientXMPP.__init__ creates an ssl.SSLContext, which does
    blocking disk I/O (load_default_certs / set_default_verify_paths), so
    construction is offloaded to an executor. But slixmpp also binds to
    the event loop at construction time — in a worker thread that would
    be a dead loop. Capture HA's running loop here and inject it
    explicitly so slixmpp schedules its connection on the right loop.
    """
    loop = asyncio.get_running_loop()
    return await hass.async_add_executor_job(
        partial(NefitClient, serial_number, access_key, password, loop=loop)
    )


class NefitClient:
    """Connected, single-flight Nefit Easy API client."""

    def __init__(
        self,
        serial_number: str,
        access_key: str,
        password: str,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._xmpp = NefitXMPP(serial_number, access_key, password, loop=loop)
        self._crypto = NefitCrypto(access_key, password)
        self._lock = asyncio.Lock()
        self._response: asyncio.Future[str] | None = None
        self._xmpp.set_message_callback(self._on_body)

    async def connect(self) -> None:
        await self._xmpp.async_connect()

    async def disconnect(self) -> None:
        await self._xmpp.async_disconnect()

    # -- transport callback ----------------------------------------------
    def _on_body(self, body: str) -> None:
        if self._response is not None and not self._response.done():
            self._response.set_result(body)

    # -- HTTP-in-stanza framing ------------------------------------------
    @staticmethod
    def _parse_http(raw: str) -> tuple[int, dict[str, str], str]:
        head, _, body = raw.partition("\r\r")
        if "\r\r" not in raw:  # some gateways use \n
            head, _, body = raw.partition("\n\n")
        lines = head.replace("\r", "\n").splitlines()
        status = int(lines[0].split(" ")[1]) if lines else 0
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        return status, headers, body.strip()

    async def _request(self, message: str) -> str:
        async with self._lock:
            loop = asyncio.get_running_loop()
            self._response = loop.create_future()
            self._xmpp.send_body(message)
            try:
                async with asyncio.timeout(_REQUEST_TIMEOUT):
                    return await self._response
            except TimeoutError as err:
                raise NefitTimeoutError("No response from Nefit gateway") from err
            finally:
                self._response = None

    async def get(self, uri: str) -> Any:
        """GET a Nefit endpoint and return the decoded JSON value."""
        msg = f"GET {uri} HTTP/1.1\rUser-Agent: {_USER_AGENT}\r\r"
        status, headers, body = self._parse_http(await self._request(msg))
        if status == 401 or status == 403:
            raise NefitAuthError(f"Unauthorized for {uri}")
        if status != 200:
            raise NefitConnectionError(f"GET {uri} -> HTTP {status}")
        if "application/json" in headers.get("content-type", ""):
            try:
                return json.loads(self._crypto.decrypt(body))
            except json.JSONDecodeError as err:
                # Non-JSON after decrypt strongly implies bad credentials.
                raise NefitAuthError("Decrypt failed; check credentials") from err
        return body

    async def put(self, uri: str, data: Any) -> dict[str, str]:
        """PUT JSON ``data`` to a Nefit endpoint."""
        payload = data if isinstance(data, str) else json.dumps(data)
        encrypted = self._crypto.encrypt(payload)
        msg = "\r".join(
            [
                f"PUT {uri} HTTP/1.1",
                "Content-Type: application/json",
                f"Content-Length: {len(encrypted)}",
                f"User-Agent: {_USER_AGENT}",
                "",
                encrypted,
            ]
        )
        status, _headers, _body = self._parse_http(await self._request(msg))
        if status in (401, 403):
            raise NefitAuthError(f"Unauthorized for {uri}")
        if status >= 300:
            raise NefitConnectionError(f"PUT {uri} -> HTTP {status}")
        return {"status": "ok"}
