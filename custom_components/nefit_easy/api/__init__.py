"""Native Nefit/Bosch Easy protocol client (XMPP + AES, no external lib)."""

from __future__ import annotations

from .client import NefitClient, async_create_client
from .errors import (
    NefitAuthError,
    NefitConnectionError,
    NefitError,
    NefitTimeoutError,
)

__all__ = [
    "NefitAuthError",
    "NefitClient",
    "NefitConnectionError",
    "NefitError",
    "NefitTimeoutError",
    "async_create_client",
]
