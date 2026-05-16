"""Transport must be STARTTLS-only for the Bosch backend.

slixmpp 1.15 attempts direct TLS first; the Bosch server requires
plaintext-then-STARTTLS, so direct TLS fails immediately and our
connection_failed handler aborts before the STARTTLS fallback.
"""

from __future__ import annotations

from custom_components.nefit_easy.api import async_create_client


async def test_starttls_only(hass) -> None:
    client = await async_create_client(hass, "757921601", "abcd1234", "secret")
    assert client._xmpp.enable_direct_tls is False
    assert client._xmpp.enable_starttls is True
    await client.disconnect()
