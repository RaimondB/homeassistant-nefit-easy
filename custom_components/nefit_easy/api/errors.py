"""Typed errors for the Nefit Easy protocol client."""

from __future__ import annotations


class NefitError(Exception):
    """Base error for all Nefit protocol failures."""


class NefitConnectionError(NefitError):
    """Raised when the XMPP transport cannot connect or is lost."""


class NefitAuthError(NefitError):
    """Raised on authentication failure (bad serial/access key/password).

    Decryption that yields non-JSON for a JSON endpoint is treated as a
    likely-invalid-password signal, mirroring nefit-easy-core behaviour.
    """


class NefitTimeoutError(NefitError):
    """Raised when a request is not answered within the timeout/retries."""
