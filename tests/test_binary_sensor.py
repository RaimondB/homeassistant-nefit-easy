"""Binary sensor on/off mapping from uiStatus codes."""

from __future__ import annotations

import pytest

from custom_components.nefit_easy.binary_sensor import BINARY_SENSORS

_BY_KEY = {d.key: d for d in BINARY_SENSORS}
_CODE = {
    "holiday_mode": "HMD",
    "powersave_mode": "ESI",
    "hot_water_active": "DHW",
    "boiler_block": "BBE",
    "boiler_lock": "BLE",
    "boiler_maintenance": "BMR",
}


@pytest.mark.parametrize("key", list(_CODE))
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("on", True),
        ("off", False),
        ("true", True),  # BBE/BLE/BMR report true/false, not on/off
        ("false", False),
        (None, None),
        ("???", None),
    ],
)
def test_flag_mapping(key, raw, expected) -> None:
    desc = _BY_KEY[key]
    ui = {} if raw is None else {_CODE[key]: raw}
    assert desc.is_on_fn({"uiStatus": ui}) is expected


def test_all_six_present() -> None:
    assert set(_BY_KEY) == set(_CODE)
