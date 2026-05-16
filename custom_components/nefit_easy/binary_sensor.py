"""Binary sensor platform for Nefit/Bosch Easy.

All from raw ``uiStatus`` codes (each "on"/"off"): HMD (holiday),
ESI (powersave), BBE/BLE/BMR (boiler block/lock/maintenance),
DHW (hot water active).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NefitDataUpdateCoordinator
from .entity import NefitEntity


@dataclass(frozen=True, kw_only=True)
class NefitBinaryDescription(BinarySensorEntityDescription):
    """Binary sensor description with an is_on extractor."""

    is_on_fn: Callable[[dict[str, Any]], bool | None]


# The device is inconsistent: HMD/FPA/ESI/DHW use "on"/"off" while
# BBE/BLE/BMR use "true"/"false" (verified against a real device — the
# reference nefit-easy-commands parseBoolean only handles on/off and
# returns null for these, which is a latent bug we don't reproduce).
_TRUE = {"on", "true", "1", "yes"}
_FALSE = {"off", "false", "0", "no"}


def _flag(code: str) -> Callable[[dict[str, Any]], bool | None]:
    def _fn(data: dict[str, Any]) -> bool | None:
        val = str(data.get("uiStatus", {}).get(code, "")).lower()
        if val in _TRUE:
            return True
        if val in _FALSE:
            return False
        return None

    return _fn


BINARY_SENSORS: tuple[NefitBinaryDescription, ...] = (
    NefitBinaryDescription(
        key="holiday_mode",
        translation_key="holiday_mode",
        is_on_fn=_flag("HMD"),
    ),
    NefitBinaryDescription(
        key="powersave_mode",
        translation_key="powersave_mode",
        device_class=BinarySensorDeviceClass.POWER,
        is_on_fn=_flag("ESI"),
    ),
    NefitBinaryDescription(
        key="hot_water_active",
        translation_key="hot_water_active",
        device_class=BinarySensorDeviceClass.RUNNING,
        is_on_fn=_flag("DHW"),
    ),
    NefitBinaryDescription(
        key="boiler_block",
        translation_key="boiler_block",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_flag("BBE"),
    ),
    NefitBinaryDescription(
        key="boiler_lock",
        translation_key="boiler_lock",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_flag("BLE"),
    ),
    NefitBinaryDescription(
        key="boiler_maintenance",
        translation_key="boiler_maintenance",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=_flag("BMR"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NefitBinarySensor(coordinator, desc) for desc in BINARY_SENSORS)


class NefitBinarySensor(NefitEntity, BinarySensorEntity):
    """A single Nefit-derived binary sensor."""

    entity_description: NefitBinaryDescription

    def __init__(
        self,
        coordinator: NefitDataUpdateCoordinator,
        description: NefitBinaryDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._serial}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.is_on_fn(self.coordinator.data or {})
