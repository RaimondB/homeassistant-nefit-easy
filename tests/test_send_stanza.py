"""The outgoing stanza must match nefit-easy-core byte-for-byte.

The Bosch gateway accepts GETs with slixmpp's extra id/type/xml:lang
attributes but rejects writes (HTTP 400). The stanza must be a bare
<message from to><body> with \\r serialised as &#13;\\n.
"""

from __future__ import annotations

from custom_components.nefit_easy.api import async_create_client


async def test_send_body_matches_reference(hass) -> None:
    client = await async_create_client(hass, "757921601", "abcd1234", "secret")
    xmpp = client._xmpp

    sent: list[str] = []
    xmpp.send_raw = sent.append  # capture instead of transmitting

    xmpp.send_body("PUT /x HTTP/1.1\rUser-Agent: NefitEasy\r\r")
    await client.disconnect()

    (stanza,) = sent
    assert stanza == (
        '<message from="rrccontact_757921601@wa2-mz36-qrmzh6.bosch.de" '
        'to="rrcgateway_757921601@wa2-mz36-qrmzh6.bosch.de">'
        "<body>PUT /x HTTP/1.1&#13;\nUser-Agent: NefitEasy&#13;\n&#13;\n"
        "</body></message>"
    )
    # The attributes slixmpp would otherwise add and that break writes:
    assert "xml:lang" not in stanza
    assert " id=" not in stanza
    assert " type=" not in stanza
