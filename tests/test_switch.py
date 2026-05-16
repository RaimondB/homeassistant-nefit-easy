"""Hot-water and fireplace switch state + write behaviour."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.nefit_easy.coordinator import NefitDataUpdateCoordinator
from custom_components.nefit_easy.switch import (
    NefitFireplaceSwitch,
    NefitHotWaterSwitch,
)


def _coord(hass, data, client=None):
    entry = MagicMock()
    entry.data = {"serial_number": "ABC123"}
    c = NefitDataUpdateCoordinator(hass, entry, client or AsyncMock(), scan_interval=60)
    c.data = data
    c.async_request_refresh = AsyncMock()
    return c


@pytest.mark.parametrize(
    ("hws", "expected"),
    [("on", True), ("off", False), (None, None)],
)
async def test_hot_water_is_on(hass, hws, expected) -> None:
    sw = NefitHotWaterSwitch(_coord(hass, {"hotWaterSupply": hws}))
    assert sw.is_on is expected


async def test_hot_water_turn_on_uses_user_mode(hass) -> None:
    client = AsyncMock()
    coord = _coord(
        hass, {"hotWaterSupply": "off", "uiStatus": {"UMD": "clock"}}, client
    )
    await NefitHotWaterSwitch(coord).async_turn_on()
    client.set_hot_water_supply.assert_awaited_once_with(True, "clock")
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize(
    ("fpa", "expected"),
    [("on", True), ("off", False), (None, None)],
)
async def test_fireplace_is_on(hass, fpa, expected) -> None:
    sw = NefitFireplaceSwitch(_coord(hass, {"uiStatus": {"FPA": fpa}}))
    assert sw.is_on is expected


async def test_fireplace_turn_off(hass) -> None:
    client = AsyncMock()
    coord = _coord(hass, {"uiStatus": {"FPA": "on"}}, client)
    await NefitFireplaceSwitch(coord).async_turn_off()
    client.set_fireplace_mode.assert_awaited_once_with(False)
