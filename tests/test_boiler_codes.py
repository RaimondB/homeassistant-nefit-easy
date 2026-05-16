"""Boiler display-code mapping (describe / is_fault) + status sensor."""

from __future__ import annotations

import pytest

from custom_components.nefit_easy.boiler_codes import describe, is_fault
from custom_components.nefit_easy.sensor import SENSORS


@pytest.mark.parametrize(
    ("code", "msg", "fault"),
    [
        ("-H", "Central heating active", False),
        ("=H", "Hot water active", False),
        ("0H", "System standby", False),
        ("2E", "Boiler water pressure too low", True),
        ("6A", "Burner does not ignite", True),
        ("ZZ", "ZZ", None),  # unknown -> raw code, problem unknown
        (None, None, None),
        ("", None, None),
    ],
)
def test_describe_and_is_fault(code, msg, fault) -> None:
    assert describe(code) == msg
    assert is_fault(code) is fault


@pytest.mark.parametrize(
    ("dc", "cc", "expected"),
    [
        ("0H", 0, False),  # normal standby, no cause
        ("0H", "0", False),
        ("0H", 204, True),  # any non-zero cause -> fault
        ("ZZ", 12, True),  # unknown code + cause -> fault
        ("ZZ", 0, False),  # unknown code, explicit no cause -> ok
        ("ZZ", None, None),  # unknown code, no info -> unknown
        ("2E", 0, True),  # known fault stays fault even if cause 0
    ],
)
def test_is_fault_with_cause(dc, cc, expected) -> None:
    assert is_fault(dc, cc) is expected


def test_boiler_status_sensor_value_and_attrs() -> None:
    desc = next(d for d in SENSORS if d.key == "boiler_status")
    data = {"displayCode": "2E", "causeCode": 204}
    assert desc.value_fn(data) == "Boiler water pressure too low"
    assert desc.attrs_fn(data) == {"display_code": "2E", "cause_code": 204}
    # unknown code falls back to raw, attrs still present
    data2 = {"displayCode": "ZZ", "causeCode": 0}
    assert desc.value_fn(data2) == "ZZ"
    assert desc.attrs_fn(data2)["display_code"] == "ZZ"
