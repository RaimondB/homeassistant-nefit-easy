"""Climate program-mode (UMD) vs boiler-indicator (BAI) modeling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import HVACAction, HVACMode

from custom_components.nefit_easy.climate import NefitClimate
from custom_components.nefit_easy.const import URI_USERMODE
from custom_components.nefit_easy.coordinator import NefitDataUpdateCoordinator


def _climate(hass, ui_status, client=None):
    entry = MagicMock()
    entry.data = {"serial_number": "ABC123"}
    coordinator = NefitDataUpdateCoordinator(
        hass, entry, client or AsyncMock(), scan_interval=60
    )
    coordinator.data = {"uiStatus": ui_status}
    coordinator.async_request_refresh = AsyncMock()
    return NefitClimate(coordinator)


@pytest.mark.parametrize(
    ("umd", "bai", "mode", "action"),
    [
        ("manual", "CH", HVACMode.HEAT, HVACAction.HEATING),
        ("clock", "CH", HVACMode.AUTO, HVACAction.HEATING),
        ("clock", "HW", HVACMode.AUTO, HVACAction.IDLE),
        ("clock", "No", HVACMode.AUTO, HVACAction.IDLE),
        ("manual", "No", HVACMode.HEAT, HVACAction.IDLE),
    ],
)
async def test_mode_and_action(hass, umd, bai, mode, action) -> None:
    entity = _climate(hass, {"UMD": umd, "BAI": bai})
    assert entity.hvac_mode is mode
    assert entity.hvac_action is action


async def test_defaults_when_status_missing(hass) -> None:
    entity = _climate(hass, {})
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.hvac_action is HVACAction.IDLE
    assert HVACMode.OFF not in entity.hvac_modes


@pytest.mark.parametrize(
    ("mode", "expected"),
    [(HVACMode.AUTO, "clock"), (HVACMode.HEAT, "manual")],
)
async def test_set_hvac_mode(hass, mode, expected) -> None:
    client = AsyncMock()
    entity = _climate(hass, {"UMD": "clock"}, client=client)
    await entity.async_set_hvac_mode(mode)
    client.put.assert_awaited_once_with(URI_USERMODE, {"value": expected})
    entity.coordinator.async_request_refresh.assert_awaited_once()


async def test_set_temperature_flip_observed_via_refresh(hass) -> None:
    client = AsyncMock()
    entity = _climate(hass, {"UMD": "clock"}, client=client)
    assert entity.hvac_mode is HVACMode.AUTO

    await entity.async_set_temperature(temperature=20)
    client.set_temperature.assert_awaited_once_with(20.0)

    # The device auto-flips; simulate the coordinator refresh result.
    entity.coordinator.data = {"uiStatus": {"UMD": "manual"}}
    assert entity.hvac_mode is HVACMode.HEAT


async def test_preset_modes_are_settable_only(hass) -> None:
    entity = _climate(hass, {})
    assert entity.preset_modes == ["none", "fireplace"]
    assert "holiday" not in entity.preset_modes


@pytest.mark.parametrize(
    ("fpa", "expected"),
    [("on", "fireplace"), ("off", "none"), (None, "none")],
)
async def test_preset_mode_value(hass, fpa, expected) -> None:
    ui = {} if fpa is None else {"FPA": fpa}
    assert _climate(hass, ui).preset_mode == expected


@pytest.mark.parametrize(
    ("preset", "expected_on"),
    [("fireplace", True), ("none", False)],
)
async def test_set_preset_mode(hass, preset, expected_on) -> None:
    client = AsyncMock()
    entity = _climate(hass, {}, client=client)
    await entity.async_set_preset_mode(preset)
    client.set_fireplace_mode.assert_awaited_once_with(expected_on)
    entity.coordinator.async_request_refresh.assert_awaited_once()
