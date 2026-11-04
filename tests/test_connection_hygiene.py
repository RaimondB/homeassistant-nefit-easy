"""Failed connects leave nothing behind, and reconnects are spaced.

2026-10-28: a backend hiccup turned into 48 minutes unavailable. slixmpp's
disconnect()/abort() do not cancel a connect that has no transport yet, so
every failed connect — and every config-entry reload by the self-heal
automation — left a client retrying on its own. The strays logged in as the
same JID and kicked each other off (10 drops in 3 s).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry
from slixmpp.exceptions import IqError, IqTimeout
from slixmpp.xmlstream.xmlstream import NotConnectedError

from custom_components.nefit_easy.api import async_create_client
from custom_components.nefit_easy.api.client import ReconnectGate
from custom_components.nefit_easy.api.errors import NefitConnectionError
from custom_components.nefit_easy.const import DOMAIN

ENTRY_DATA = {
    "serial_number": "757921601",
    "access_key": "abcd1234",
    "password": "secret",
}


@pytest.fixture
async def xmpp(hass):
    client = await async_create_client(hass, "757921601", "abcd1234", "secret")
    yield client._xmpp
    await client.disconnect()


def _hanging_connect(xmpp):
    """A connect that never gets a transport, like an unreachable backend."""
    loop = asyncio.get_running_loop()
    attempts = []

    def connect(*_args):
        attempt = loop.create_future()
        attempts.append(attempt)
        xmpp._current_connection_attempt = attempt
        return attempt

    xmpp.connect = connect
    return attempts


async def test_timed_out_connect_cancels_the_attempt(xmpp) -> None:
    attempts = _hanging_connect(xmpp)
    with pytest.raises(NefitConnectionError):
        await xmpp.async_connect(timeout=0.01)
    assert attempts[0].cancelled()
    assert xmpp._current_connection_attempt is None


async def test_failed_connect_cancels_the_attempt(xmpp) -> None:
    attempts = _hanging_connect(xmpp)
    task = asyncio.ensure_future(xmpp.async_connect(timeout=5))
    await asyncio.sleep(0)
    xmpp._on_connection_failed("Errno 110")
    with pytest.raises(NefitConnectionError):
        await task
    assert attempts[0].cancelled()


async def test_reconnect_cancels_a_pending_attempt_first(xmpp) -> None:
    attempts = _hanging_connect(xmpp)
    stale = asyncio.get_running_loop().create_future()
    xmpp._current_connection_attempt = stale  # no transport yet
    with pytest.raises(NefitConnectionError):
        await xmpp.async_reconnect(timeout=0.01)
    assert stale.cancelled()
    assert attempts[0].cancelled()


async def test_disconnect_cancels_a_pending_attempt(xmpp) -> None:
    pending = asyncio.get_running_loop().create_future()
    xmpp._current_connection_attempt = pending
    await xmpp.async_disconnect()
    assert pending.cancelled()


def test_backoff_doubles_to_five_minutes_and_resets() -> None:
    gate = ReconnectGate()
    now = [0.0]
    gate.clock = lambda: now[0]
    waits = []
    for _ in range(6):
        gate.failed()
        waits.append(gate.not_before - now[0])
        now[0] = gate.not_before
    assert waits == [60, 120, 240, 300, 300, 300]
    gate.succeeded()
    gate.failed()
    assert gate.not_before - now[0] == 60


def test_gate_blocks_until_due_with_slack() -> None:
    gate = ReconnectGate()
    now = [0.0]
    gate.clock = lambda: now[0]
    gate.failed()
    now[0] = 30
    with pytest.raises(NefitConnectionError, match="Waiting 30s"):
        gate.check()
    now[0] = 57  # a poll a few seconds early is let through
    gate.check()


async def test_backoff_survives_a_reload(hass) -> None:
    """A new client for the same boiler (entry reload) inherits the wait."""
    first = await async_create_client(hass, "757921601", "a", "b")
    first._xmpp.async_connect = AsyncMock(side_effect=NefitConnectionError("x"))
    with pytest.raises(NefitConnectionError):
        await first.connect()

    second = await async_create_client(hass, "757921601", "a", "b")
    second._xmpp.async_connect = AsyncMock()
    with pytest.raises(NefitConnectionError, match="Waiting"):
        await second.connect()
    second._xmpp.async_connect.assert_not_awaited()

    other = await async_create_client(hass, "111111111", "a", "b")
    other._xmpp.async_connect = AsyncMock()
    await other.connect()  # another boiler has its own gate
    for c in (first, second, other):
        await c.disconnect()


@pytest.mark.parametrize("fail_on", ["connect", "first_refresh"])
async def test_failed_setup_stops_the_client(hass, mock_client, fail_on) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    mock_client.disconnect = AsyncMock()
    if fail_on == "connect":
        mock_client.connect.side_effect = NefitConnectionError("down")
    else:
        mock_client.get.side_effect = NefitConnectionError("down")
    with patch(
        "custom_components.nefit_easy.async_create_client",
        AsyncMock(return_value=mock_client),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mock_client.disconnect.assert_awaited()


async def test_disconnect_stops_the_filter_task(xmpp) -> None:
    filters = asyncio.ensure_future(asyncio.sleep(3600))
    xmpp._run_out_filters = filters
    await xmpp.async_disconnect()
    await asyncio.sleep(0)
    assert filters.cancelled()


def _fake_iq(xmpp, outcome):
    sent = []

    class _Iq(dict):
        def __init__(self):
            super().__init__()
            self.xml = []

        async def send(self, timeout=None):  # noqa: ASYNC109 - slixmpp's signature
            sent.append((dict(self), [e.tag for e in self.xml], timeout))
            if isinstance(outcome, BaseException):
                raise outcome

    xmpp.Iq = _Iq
    return sent


@pytest.mark.parametrize(
    ("outcome", "alive"),
    [
        (None, True),
        # Built without a stanza: only the type matters here.
        (IqError.__new__(IqError), True),  # an error reply still proves the stream
        (IqTimeout.__new__(IqTimeout), False),
        (NotConnectedError(), False),
    ],
)
async def test_server_ping(xmpp, outcome, alive) -> None:
    xmpp.transport = MagicMock()
    xmpp._session_live = True
    sent = _fake_iq(xmpp, outcome)
    assert await xmpp.async_server_alive() is alive
    ((iq, tags, timeout),) = sent
    assert iq == {"type": "get", "to": "wa2-mz36-qrmzh6.bosch.de"}
    assert tags == ["{urn:xmpp:ping}ping"]
    assert timeout == 10.0
    xmpp.transport = None


async def test_no_ping_without_a_session(xmpp) -> None:
    sent = _fake_iq(xmpp, None)
    assert await xmpp.async_server_alive() is False
    assert sent == []


async def test_failed_first_connect_reports_backend_unreachable(hass) -> None:
    client = await async_create_client(hass, "757921601", "a", "b")
    client._xmpp.async_connect = AsyncMock(side_effect=NefitConnectionError("x"))
    with pytest.raises(NefitConnectionError):
        await client.connect()
    assert client.connection_state == "backend_unreachable"
    await client.disconnect()


async def test_a_requested_disconnect_is_not_a_lost_connection(xmpp, caplog) -> None:
    xmpp._session_live = True
    xmpp._ready.set()
    await xmpp.async_disconnect()
    assert "Lost the XMPP connection" not in caplog.text
