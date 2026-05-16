"""Binary sensor mapping: uiStatus flags + boiler problem from code."""

from __future__ import annotations

import pytest
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.nefit_easy.binary_sensor import BINARY_SENSORS

_BY_KEY = {d.key: d for d in BINARY_SENSORS}
_FLAG = {
    "holiday_mode": "HMD",
    "powersave_mode": "ESI",
    "hot_water_active": "DHW",
}


def test_entities() -> None:
    assert set(_BY_KEY) == {*_FLAG, "boiler_problem"}
    assert "boiler_block" not in _BY_KEY
    assert _BY_KEY["boiler_problem"].device_class is BinarySensorDeviceClass.PROBLEM


@pytest.mark.parametrize("key", list(_FLAG))
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("on", True), ("off", False), ("true", True), ("false", False), ("?", None)],
)
def test_flag_mapping(key, raw, expected) -> None:
    desc = _BY_KEY[key]
    assert desc.is_on_fn({"uiStatus": {_FLAG[key]: raw}}) is expected


@pytest.mark.parametrize(
    ("display_code", "expected"),
    [
        ("-H", False),
        ("=H", False),
        ("2E", True),
        ("6A", True),
        ("ZZ", None),
        (None, None),
    ],
)
def test_boiler_problem(display_code, expected) -> None:
    is_on = _BY_KEY["boiler_problem"].is_on_fn({"displayCode": display_code})
    assert is_on is expected


def test_boiler_problem_uses_cause_code() -> None:
    fn = _BY_KEY["boiler_problem"].is_on_fn
    assert fn({"displayCode": "0H", "causeCode": 0}) is False
    assert fn({"displayCode": "0H", "causeCode": 204}) is True
    assert fn({"displayCode": "ZZ", "causeCode": 7}) is True
