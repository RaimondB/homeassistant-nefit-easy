"""Known-answer tests for the Nefit AES body crypto.

These pin the key derivation and AES-256-ECB behaviour to fixed vectors
computed independently from the documented algorithm. If the protocol
client ever connects but every request fails to decrypt, suspect this.
"""

from __future__ import annotations

from custom_components.nefit_easy.api.crypto import NefitCrypto, derive_key

# Vectors computed from the reference algorithm (MD5(ak||MAGIC)||MD5(MAGIC||pw),
# AES-256-ECB, zero-pad to 16, base64) for the sample credentials below.
_ACCESS_KEY = "ABC123DEF4"
_PASSWORD = "secretpass"
_EXPECTED_KEY_HEX = "27c06c9d10d928ffa245498d105be70799e9617bd1a692003a69ec798e885d2d"
_PLAINTEXT = '{"value":21}'
_EXPECTED_CT_B64 = "AM8XN2jlThKwolZzG3LqyQ=="


def test_key_derivation_matches_reference() -> None:
    assert derive_key(_ACCESS_KEY, _PASSWORD).hex() == _EXPECTED_KEY_HEX
    assert len(derive_key(_ACCESS_KEY, _PASSWORD)) == 32


def test_encrypt_matches_reference_vector() -> None:
    crypto = NefitCrypto(_ACCESS_KEY, _PASSWORD)
    assert crypto.encrypt(_PLAINTEXT) == _EXPECTED_CT_B64


def test_decrypt_reference_vector() -> None:
    crypto = NefitCrypto(_ACCESS_KEY, _PASSWORD)
    assert crypto.decrypt(_EXPECTED_CT_B64) == _PLAINTEXT


def test_roundtrip_non_block_aligned() -> None:
    crypto = NefitCrypto(_ACCESS_KEY, _PASSWORD)
    for payload in ("a", "x" * 15, "y" * 16, "z" * 17, '{"complex": "json", "n": 3}'):
        assert crypto.decrypt(crypto.encrypt(payload)) == payload
