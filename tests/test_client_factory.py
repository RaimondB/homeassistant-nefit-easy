"""The client must be constructed off the event loop.

slixmpp's ClientXMPP.__init__ builds an ssl.SSLContext, which does
blocking disk I/O. Home Assistant (and pytest-homeassistant-custom-
component's loop protection) flags that if done in the event loop.
async_create_client offloads it to an executor.
"""

from __future__ import annotations

from custom_components.nefit_easy.api import NefitClient, async_create_client


async def test_async_create_client_runs_off_loop(hass) -> None:
    """Building via the factory must not trigger blocking-call detection."""
    client = await async_create_client(hass, "757921601", "abcd1234", "secret")
    assert isinstance(client, NefitClient)
    await client.disconnect()


async def test_client_bound_to_running_loop(hass) -> None:
    """slixmpp must be bound to HA's running loop, not the executor's.

    Regression: built in an executor without an injected loop, slixmpp
    binds to a dead worker-thread loop and connect() never runs
    (symptom: immediate "disconnected: None" then a connect timeout).
    """
    import asyncio

    client = await async_create_client(hass, "757921601", "abcd1234", "secret")
    assert client._xmpp.loop is asyncio.get_running_loop()
    await client.disconnect()
