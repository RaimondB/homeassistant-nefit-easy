"""Base entity for Nefit/Bosch Easy."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import NefitDataUpdateCoordinator


class NefitEntity(CoordinatorEntity[NefitDataUpdateCoordinator]):
    """Common device info / availability for all Nefit entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: NefitDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self._serial = coordinator.entry.data[CONF_SERIAL_NUMBER]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            manufacturer="Bosch/Nefit",
            name=f"Nefit Easy {self._serial}",
            model="Easy",
        )

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None
