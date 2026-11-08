"""Sensor value mapping + translation-file integrity."""

from __future__ import annotations

import json
import pathlib
from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorDeviceClass

from custom_components.nefit_easy.coordinator import NefitDataUpdateCoordinator
from custom_components.nefit_easy.sensor import SENSORS, NefitConnectionSensor

_CC = pathlib.Path("custom_components/nefit_easy")


def _desc(key: str):
    return next(d for d in SENSORS if d.key == "boiler_indicator") if key else None


@pytest.mark.parametrize(
    ("bai", "expected"),
    [
        ("CH", "central_heating"),
        ("HW", "hot_water"),
        ("No", "off"),
        ("???", None),
        (None, None),
    ],
)
def test_boiler_indicator_value(bai, expected) -> None:
    desc = _desc("boiler_indicator")
    data = {"uiStatus": {} if bai is None else {"BAI": bai}}
    value = desc.value_fn(data)
    assert value == expected
    assert value is None or value in desc.options


def test_boiler_indicator_is_enum() -> None:
    desc = _desc("boiler_indicator")
    assert desc.device_class is SensorDeviceClass.ENUM
    assert desc.options == ["off", "central_heating", "hot_water"]
    assert desc.native_unit_of_measurement is None
    assert desc.state_class is None


def test_translation_files_identical_and_have_boiler_indicator() -> None:
    strings = json.loads((_CC / "strings.json").read_text())
    en = json.loads((_CC / "translations" / "en.json").read_text())
    assert strings == en, "strings.json and translations/en.json drifted"
    assert "boiler_indicator" in strings["entity"]["sensor"]
    assert set(strings["entity"]["sensor"]["boiler_indicator"]["state"]) == {
        "off",
        "central_heating",
        "hot_water",
    }


async def test_connection_sensor_stays_available_and_follows_the_client(hass) -> None:
    entry = MagicMock()
    entry.data = {"serial_number": "ABC123"}
    client = MagicMock()
    client.connection_state = "thermostat_offline"
    coordinator = NefitDataUpdateCoordinator(hass, entry, client, scan_interval=60)
    coordinator.last_update_success = False  # the other entities are unavailable
    sensor = NefitConnectionSensor(coordinator)
    assert sensor.available is True
    assert sensor.native_value == "thermostat_offline"
    assert sensor.options == ["ok", "thermostat_offline", "backend_unreachable"]
    assert sensor.unique_id == "ABC123_connection"
