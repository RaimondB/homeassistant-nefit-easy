"""Diagnostics for Nefit/Bosch Easy (credentials redacted)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_KEY, CONF_PASSWORD, CONF_SERIAL_NUMBER, DOMAIN
from .coordinator import NefitDataUpdateCoordinator

_REDACT = {CONF_ACCESS_KEY, CONF_PASSWORD, CONF_SERIAL_NUMBER}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "entry_data": async_redact_data(dict(entry.data), _REDACT),
        "options": dict(entry.options),
        "last_update_success": coordinator.last_update_success,
        "data": coordinator.data,
    }
