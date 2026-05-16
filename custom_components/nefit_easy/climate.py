"""Climate platform for Nefit/Bosch Easy.

Two independent device concepts, kept separate:

* Program/user mode ``UMD`` ("manual"/"clock") -> ``hvac_mode``
  HEAT/AUTO. Changing the setpoint makes the device auto-flip to
  ``manual``; that flip is observed via the coordinator refresh, not set
  here explicitly.
* Boiler indicator ``BAI`` (CH/HW/No) is read-only status. HA's
  ``HVACAction`` has no "hot water", so it maps lossily here (CH->HEATING,
  else IDLE); the full off/central-heating/hot-water state is exposed
  separately by the ``boiler_indicator`` enum sensor.

Raw ``uiStatus`` field codes used: IHT (in-house temp), TSP (temp
setpoint), UMD (user mode), BAI (boiler indicator), FPA (fireplace
preset, settable). Holiday (HMD) is read-only and lives on
binary_sensor.holiday_mode, not as a climate preset.
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

from .const import DOMAIN, URI_USERMODE
from .coordinator import NefitDataUpdateCoordinator
from .entity import NefitEntity

# Only settable presets are listed. Holiday is read-only on this API
# and is exposed via binary_sensor.holiday_mode instead.
PRESET_FIREPLACE = "fireplace"
PRESET_NONE = "none"

# BAI is read-only. HVACAction has no "hot water" member, so HW and the
# burner-idle "No" both map to IDLE (the room circuit is not being
# served); the full tri-state is the boiler_indicator sensor instead.
_BAI_TO_ACTION = {
    "CH": HVACAction.HEATING,
    "HW": HVACAction.IDLE,
    "No": HVACAction.IDLE,
}


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
    _attr_preset_modes = [PRESET_NONE, PRESET_FIREPLACE]
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
        return _BAI_TO_ACTION.get(self._status.get("BAI"), HVACAction.IDLE)

    @property
    def preset_mode(self) -> str:
        # Must be one of _attr_preset_modes. Holiday is read-only and
        # surfaced via binary_sensor.holiday_mode, not here.
        if self._status.get("FPA") == "on":
            return PRESET_FIREPLACE
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.client.set_fireplace_mode(
            preset_mode == PRESET_FIREPLACE
        )
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        # The device auto-flips UMD to "manual" until the next scheduled
        # switch point; we don't set the mode here — the refresh below
        # surfaces UMD=manual and hvac_mode becomes HEAT.
        await self.coordinator.client.set_temperature(float(temp))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        mode = "manual" if hvac_mode == HVACMode.HEAT else "clock"
        await self.coordinator.client.put(URI_USERMODE, {"value": mode})
        await self.coordinator.async_request_refresh()
