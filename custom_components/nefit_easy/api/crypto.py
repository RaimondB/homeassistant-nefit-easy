"""AES-256-ECB body encryption for the Nefit/Bosch Easy protocol.

Faithful port of nefit-easy-core/lib/encryption.js:

    MAGIC = <32 bytes>
    key   = MD5(accessKey || MAGIC) || MD5(MAGIC || password)   # 32 bytes
    encrypt: AES-256-ECB, no library padding, manual zero-pad to 16 bytes,
             output base64
    decrypt: base64 -> AES-256-ECB -> strip trailing NUL bytes

ECB with a static key is what the Bosch backend requires; do not "improve"
it. Correctness here is pinned by known-answer tests in tests/test_crypto.py.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..const import MAGIC_HEX

_MAGIC = bytes.fromhex(MAGIC_HEX)
_BLOCK = 16


def derive_key(access_key: str, password: str) -> bytes:
    """Return the 32-byte AES key for the given credentials."""
    part1 = hashlib.md5(access_key.encode("utf-8") + _MAGIC).digest()  # noqa: S324
    part2 = hashlib.md5(_MAGIC + password.encode("utf-8")).digest()  # noqa: S324
    return part1 + part2


class NefitCrypto:
    """Encrypt/decrypt message bodies with a credentials-derived key."""

    def __init__(self, access_key: str, password: str) -> None:
        self._key = derive_key(access_key, password)

    def _cipher(self) -> Cipher:
        return Cipher(algorithms.AES(self._key), modes.ECB())  # noqa: S305

    def encrypt(self, data: str) -> str:
        """Zero-pad UTF-8 ``data`` to a block boundary and return base64."""
        raw = data.encode("utf-8")
        if len(raw) % _BLOCK != 0:
            raw += b"\x00" * (_BLOCK - (len(raw) % _BLOCK))
        encryptor = self._cipher().encryptor()
        return base64.b64encode(encryptor.update(raw) + encryptor.finalize()).decode(
            "ascii"
        )

    def decrypt(self, data: str) -> str:
        """Base64-decode + decrypt, stripping trailing NUL padding."""
        raw = base64.b64decode(data)
        decryptor = self._cipher().decryptor()
        plain = decryptor.update(raw) + decryptor.finalize()
        return plain.rstrip(b"\x00").decode("utf-8", errors="replace")
