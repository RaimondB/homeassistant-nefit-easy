"""Sensor platform for Nefit/Bosch Easy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import NefitDataUpdateCoordinator
from .entity import NefitEntity


@dataclass(frozen=True, kw_only=True)
class NefitSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over coordinator data."""

    value_fn: Callable[[dict[str, Any]], Any]


# Read-only boiler operation indicator (BAI). Unknown/missing -> None
# (entity shows "unknown") rather than an out-of-options value.
_BAI_MAP = {"No": "off", "CH": "central_heating", "HW": "hot_water"}


SENSORS: tuple[NefitSensorDescription, ...] = (
    NefitSensorDescription(
        key="system_pressure",
        translation_key="system_pressure",
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPressure.BAR,
        value_fn=lambda d: d.get("pressure"),
    ),
    NefitSensorDescription(
        key="supply_temperature",
        translation_key="supply_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.get("supplyTemperature"),
    ),
    NefitSensorDescription(
        key="outdoor_temperature",
        translation_key="outdoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.get("outdoorTemperature"),
    ),
    NefitSensorDescription(
        key="indoor_temperature",
        translation_key="indoor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda d: d.get("uiStatus", {}).get("IHT"),
    ),
    NefitSensorDescription(
        key="boiler_indicator",
        translation_key="boiler_indicator",
        device_class=SensorDeviceClass.ENUM,
        options=["off", "central_heating", "hot_water"],
        value_fn=lambda d: _BAI_MAP.get(d.get("uiStatus", {}).get("BAI")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NefitSensor(coordinator, desc) for desc in SENSORS)


class NefitSensor(NefitEntity, SensorEntity):
    """A single Nefit-derived sensor."""

    entity_description: NefitSensorDescription

    def __init__(
        self,
        coordinator: NefitDataUpdateCoordinator,
        description: NefitSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._serial}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data or {})
