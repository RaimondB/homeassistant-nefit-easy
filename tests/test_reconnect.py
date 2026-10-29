"""The client must recover from a lost XMPP session without a HA restart.

2026-10-21: the stream dropped after a request timed out, slixmpp did not
reconnect, every poll raised NotConnectedError (not a NefitError, so it was
logged as an "unexpected error"), and the integration stayed unavailable for
four days until Home Assistant was restarted.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from slixmpp.xmlstream.xmlstream import NotConnectedError

from custom_components.nefit_easy.api import async_create_client
from custom_components.nefit_easy.api import client as client_mod
from custom_components.nefit_easy.api.errors import (
    NefitConnectionError,
    NefitTimeoutError,
)

OK = "HTTP/1.1 200 OK\r\r"


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _fake_clock(client) -> _Clock:
    clock = _Clock()
    client._gate.clock = clock
    return clock


@pytest.fixture
async def nefit(hass):
    """A real NefitClient whose transport is faked at the socket boundary."""
    client = await async_create_client(hass, "757921601", "abcd1234", "secret")
    xmpp = client._xmpp
    loop = asyncio.get_running_loop()

    state = {"answer": True, "sent": 0}

    def send_raw(_data: str) -> None:
        if xmpp.transport is None:
            raise NotConnectedError
        state["sent"] += 1
        if state["answer"]:
            loop.call_soon(client._on_body, OK)

    def go_live() -> None:
        xmpp.transport = MagicMock()
        xmpp._session_live = True

    async def reconnect(timeout: float = 30.0) -> None:  # noqa: ASYNC109
        go_live()

    xmpp.send_raw = send_raw
    xmpp.async_reconnect = AsyncMock(side_effect=reconnect)
    yield client, xmpp, state, go_live
    xmpp.transport = None
    await client.disconnect()


async def test_request_on_dead_session_reconnects_first(nefit) -> None:
    client, xmpp, state, _ = nefit
    assert not xmpp.session_live  # never connected

    assert await client._request("GET /x HTTP/1.1\r\r") == OK
    xmpp.async_reconnect.assert_awaited_once()
    assert state["sent"] == 1


async def test_live_session_does_not_reconnect(nefit) -> None:
    client, xmpp, _, go_live = nefit
    go_live()

    await client._request("GET /x HTTP/1.1\r\r")
    xmpp.async_reconnect.assert_not_awaited()


async def test_dropped_stream_raises_nefit_error_then_recovers(nefit) -> None:
    client, xmpp, _state, go_live = nefit
    go_live()
    xmpp.transport = None  # the stream drops; _session_live is still True

    # Before the fix this was a bare slixmpp NotConnectedError, which the
    # coordinator did not treat as a connection failure.
    with pytest.raises(NefitConnectionError):
        xmpp.send_body("GET /x HTTP/1.1\r\r")
    assert not xmpp.session_live

    assert await client._request("GET /x HTTP/1.1\r\r") == OK
    xmpp.async_reconnect.assert_awaited_once()


async def test_two_timeouts_in_a_row_force_a_reconnect(nefit, monkeypatch) -> None:
    client, xmpp, state, go_live = nefit
    monkeypatch.setattr(client_mod, "_REQUEST_TIMEOUT", 0.01)
    go_live()
    state["answer"] = False

    with pytest.raises(NefitTimeoutError):
        await client._request("GET /x HTTP/1.1\r\r")
    assert xmpp.session_live  # one timeout is not yet a dead session

    with pytest.raises(NefitTimeoutError):
        await client._request("GET /x HTTP/1.1\r\r")
    assert not xmpp.session_live

    state["answer"] = True
    clock = _fake_clock(client)
    # The backend gets a minute before the first reconnect.
    with pytest.raises(NefitConnectionError, match="Waiting"):
        await client._request("GET /x HTTP/1.1\r\r")
    xmpp.async_reconnect.assert_not_awaited()
    clock.advance(60)
    assert await client._request("GET /x HTTP/1.1\r\r") == OK
    xmpp.async_reconnect.assert_awaited_once()


async def test_a_success_resets_the_timeout_count(nefit, monkeypatch) -> None:
    client, xmpp, state, go_live = nefit
    monkeypatch.setattr(client_mod, "_REQUEST_TIMEOUT", 0.01)
    go_live()

    for answer in (False, True, False):
        state["answer"] = answer
        try:
            await client._request("GET /x HTTP/1.1\r\r")
        except NefitTimeoutError:
            pass
    assert xmpp.session_live  # timeout, success, timeout: never two in a row
    xmpp.async_reconnect.assert_not_awaited()


async def test_failed_reconnect_is_a_connection_error(nefit) -> None:
    client, xmpp, _, _ = nefit
    xmpp.async_reconnect.side_effect = NefitConnectionError("backend unreachable")

    clock = _fake_clock(client)
    with pytest.raises(NefitConnectionError):
        await client._request("GET /x HTTP/1.1\r\r")
    # A poll during the backoff does not touch the network...
    with pytest.raises(NefitConnectionError, match="Waiting"):
        await client._request("GET /x HTTP/1.1\r\r")
    assert xmpp.async_reconnect.await_count == 1
    # ...the one after it tries again.
    clock.advance(60)
    with pytest.raises(NefitConnectionError):
        await client._request("GET /x HTTP/1.1\r\r")
    assert xmpp.async_reconnect.await_count == 2


async def test_disconnect_event_marks_the_session_dead(nefit, caplog) -> None:
    _, xmpp, _, go_live = nefit
    go_live()
    xmpp._ready.set()

    xmpp._on_disconnected("connection reset by peer")
    assert not xmpp.session_live
    assert "Lost the XMPP connection" in caplog.text
