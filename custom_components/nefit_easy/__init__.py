"""The Nefit/Bosch Easy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .api import NefitError, async_create_client
from .const import (
    CONF_ACCESS_KEY,
    CONF_IMPORT_GAS_HISTORY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_NUMBER,
    DEFAULT_IMPORT_GAS_HISTORY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    GAS_DAILY_INTERVAL,
    SERVICE_IMPORT_GAS_HISTORY,
)
from .coordinator import NefitDataUpdateCoordinator
from .gas_statistics import NefitGasStatistics

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Nefit/Bosch Easy from a config entry."""
    client = await async_create_client(
        hass,
        entry.data[CONF_SERIAL_NUMBER],
        entry.data[CONF_ACCESS_KEY],
        entry.data[CONF_PASSWORD],
    )
    try:
        await client.connect()
    except NefitError as err:
        raise ConfigEntryNotReady(str(err)) from err

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = NefitDataUpdateCoordinator(hass, entry, client, scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))

    if entry.options.get(CONF_IMPORT_GAS_HISTORY, DEFAULT_IMPORT_GAS_HISTORY):
        # Attach to the coordinator so the hass.data[DOMAIN] shape (read
        # by all platforms) stays untouched.
        gas = NefitGasStatistics(hass, entry, client)
        coordinator.gas_statistics = gas
        entry.async_on_unload(
            async_track_time_interval(hass, gas.async_daily, GAS_DAILY_INTERVAL)
        )
        # One-time, resumable full backfill; idempotent on restart/reload.
        entry.async_create_background_task(
            hass, gas.async_backfill(), "nefit_easy gas backfill"
        )

    _async_register_services(hass)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the gas-history import service once per HA instance."""
    if hass.services.has_service(DOMAIN, SERVICE_IMPORT_GAS_HISTORY):
        return

    async def _import_gas_history(_call: ServiceCall) -> None:
        for coordinator in hass.data.get(DOMAIN, {}).values():
            gas = getattr(coordinator, "gas_statistics", None)
            if gas is not None:
                await gas.async_backfill()

    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_GAS_HISTORY, _import_gas_history
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: NefitDataUpdateCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_IMPORT_GAS_HISTORY)
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
