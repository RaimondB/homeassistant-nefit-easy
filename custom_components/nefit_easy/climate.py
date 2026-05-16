"""Climate platform for Nefit/Bosch Easy.

Raw ``uiStatus`` field codes used: IHT (in-house temp), TSP (temp setpoint),
UMD (user mode: "manual"/"clock"), BAI (boiler indicator), HMD (holiday).
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    URI_TEMP_ROOM_MANUAL,
    URI_USERMODE,
)
from .coordinator import NefitDataUpdateCoordinator
from .entity import NefitEntity

PRESET_FIREPLACE = "fireplace"
PRESET_HOLIDAY = "holiday"
PRESET_NONE = "none"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NefitClimate(coordinator)])


class NefitClimate(NefitEntity, ClimateEntity):
    """The thermostat."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO]
    _attr_preset_modes = [PRESET_NONE, PRESET_FIREPLACE, PRESET_HOLIDAY]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_min_temp = 5
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator: NefitDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._serial}_climate"

    @property
    def _status(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get("uiStatus", {})

    @property
    def current_temperature(self) -> float | None:
        val = self._status.get("IHT")
        return float(val) if val is not None else None

    @property
    def target_temperature(self) -> float | None:
        val = self._status.get("TSP")
        return float(val) if val is not None else None

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT if self._status.get("UMD") == "manual" else HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        return (
            HVACAction.HEATING if self._status.get("BAI") == "CH" else HVACAction.IDLE
        )

    @property
    def preset_mode(self) -> str:
        if self._status.get("HMD") == "on":
            return PRESET_HOLIDAY
        if self._status.get("FPA") == "on":
            return PRESET_FIREPLACE
        return PRESET_NONE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.client.put(URI_TEMP_ROOM_MANUAL, {"value": float(temp)})
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode = "manual" if hvac_mode == HVACMode.HEAT else "clock"
        await self.coordinator.client.put(URI_USERMODE, {"value": mode})
        await self.coordinator.async_request_refresh()
