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
from homeassistant.const import EntityCategory, UnitOfPressure, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .boiler_codes import describe
from .const import CONNECTION_STATES, DOMAIN
from .coordinator import NefitDataUpdateCoordinator
from .entity import NefitEntity


@dataclass(frozen=True, kw_only=True)
class NefitSensorDescription(SensorEntityDescription):
    """Sensor description with a value extractor over coordinator data."""

    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


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
    NefitSensorDescription(
        key="boiler_status",
        translation_key="boiler_status",
        value_fn=lambda d: describe(d.get("displayCode")),
        attrs_fn=lambda d: {
            "display_code": d.get("displayCode"),
            "cause_code": d.get("causeCode"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            *(NefitSensor(coordinator, desc) for desc in SENSORS),
            NefitConnectionSensor(coordinator),
        ]
    )


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

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data or {})


class NefitConnectionSensor(NefitEntity, SensorEntity):
    """Which side is down: the Bosch backend, or the thermostat behind it.

    Stays available while the other entities are not — that is when it
    matters — and follows the client directly, because the coordinator stops
    notifying entities while polls keep failing.
    """

    _attr_translation_key = "connection"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CONNECTION_STATES)
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NefitDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._serial}_connection"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.client.add_state_listener(self.async_write_ha_state)
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> str:
        return self.coordinator.client.connection_state
