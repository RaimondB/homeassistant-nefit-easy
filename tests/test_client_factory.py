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
