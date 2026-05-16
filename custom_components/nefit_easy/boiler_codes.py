"""Nefit/Bosch Easy boiler display-code -> human status.

English code map adapted from the ksya/ha-nefiteasy integration (MIT),
extended with an ok/fault classification so a single "boiler problem"
binary sensor and a friendly status sensor can both be derived from the
appliance display code. Unmapped codes -> unknown (status falls back to
the raw code; problem is unknown rather than asserted).
"""

from __future__ import annotations

# code -> (message, is_fault)
_CODES: dict[str, tuple[str, bool]] = {
    "-H": ("Central heating active", False),
    "=H": ("Hot water active", False),
    "0C": ("System starting", False),
    "0L": ("System starting", False),
    "0U": ("System starting", False),
    "0E": ("System waiting", False),
    "0H": ("System standby", False),
    "rE": ("System restarting", False),
    "0A": ("Waiting — boiler cannot transfer heat to central heating", True),
    "0Y": ("Waiting — boiler cannot transfer heat to central heating", True),
    "2E": ("Boiler water pressure too low", True),
    "H07": ("Boiler water pressure too low", True),
    "2F": ("Sensors measured an abnormal temperature", True),
    "2L": ("Sensors measured an abnormal temperature", True),
    "2P": ("Sensors measured an abnormal temperature", True),
    "2U": ("Sensors measured an abnormal temperature", True),
    "4F": ("Sensors measured an abnormal temperature", True),
    "4L": ("Sensors measured an abnormal temperature", True),
    "6A": ("Burner does not ignite", True),
    "6C": ("Burner does not ignite", True),
}


def describe(display_code: str | None) -> str | None:
    """Friendly message, or the raw code if unmapped, or None if missing."""
    if not display_code:
        return None
    entry = _CODES.get(display_code)
    return entry[0] if entry else display_code


def is_fault(display_code: str | None) -> bool | None:
    """True=fault, False=ok, None=unknown/missing code."""
    if not display_code:
        return None
    entry = _CODES.get(display_code)
    return entry[1] if entry else None
