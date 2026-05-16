"""Switch platform for Nefit/Bosch Easy: hot-water supply, fireplace mode."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NefitDataUpdateCoordinator
from .entity import NefitEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NefitHotWaterSwitch(coordinator),
            NefitFireplaceSwitch(coordinator),
        ]
    )


class _NefitSwitch(NefitEntity, SwitchEntity):
    """Base for the optimistic Nefit switches."""

    _key: str

    def __init__(self, coordinator: NefitDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._serial}_{self._key}"

    async def _write(self, on: bool) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    async def async_turn_on(self, **_kwargs: Any) -> None:
        await self._write(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_kwargs: Any) -> None:
        await self._write(False)
        await self.coordinator.async_request_refresh()


class NefitHotWaterSwitch(_NefitSwitch):
    """Hot-water supply on/off (program-mode aware)."""

    _key = "hot_water_supply"
    _attr_translation_key = "hot_water_supply"

    @property
    def is_on(self) -> bool | None:
        val = (self.coordinator.data or {}).get("hotWaterSupply")
        if val in ("on", "off"):
            return val == "on"
        return None

    async def _write(self, on: bool) -> None:
        user_mode = (self.coordinator.data or {}).get("uiStatus", {}).get("UMD")
        await self.coordinator.client.set_hot_water_supply(on, user_mode)


class NefitFireplaceSwitch(_NefitSwitch):
    """Fireplace mode on/off (FPA in uiStatus)."""

    _key = "fireplace_mode"
    _attr_translation_key = "fireplace_mode"

    @property
    def is_on(self) -> bool | None:
        val = (self.coordinator.data or {}).get("uiStatus", {}).get("FPA")
        if val in ("on", "off"):
            return val == "on"
        return None

    async def _write(self, on: bool) -> None:
        await self.coordinator.client.set_fireplace_mode(on)
