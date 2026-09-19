"""DataUpdateCoordinator for Nefit/Bosch Easy.

One refresh prefers a single ``/ecus/rrc/uiStatus`` (carries most fields)
plus a few minimal extra GETs, serialized by the client's single-flight
lock and bounded by the ~60s Nefit rate limit.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NefitAuthError, NefitClient, NefitError
from .const import (
    DOMAIN,
    SENSOR_SENTINEL_VALUE,
    URI_CAUSECODE,
    URI_DISPLAYCODE,
    URI_OUTDOOR_TEMP,
    URI_PRESSURE,
    URI_SUPPLY_TEMP,
    URI_UISTATUS,
)

_LOGGER = logging.getLogger(__name__)


def _drop_sentinel(value: Any) -> Any:
    """Map the appliance's "no reading" marker to None.

    Keeps a sensor the boiler cannot read out of the entity state (and out of
    long-term statistics) instead of publishing the raw sentinel as a value.
    """
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return value
    return None if numeric == SENSOR_SENTINEL_VALUE else numeric


class NefitDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the Nefit gateway and exposes a merged data dict."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NefitClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.client = client
        self.entry = entry
        # Set by __init__ when the gas-history import option is enabled.
        self.gas_statistics: Any | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data: dict[str, Any] = {}
            data["uiStatus"] = (await self.client.get(URI_UISTATUS)).get("value", {})
            data["pressure"] = _drop_sentinel(
                (await self.client.get(URI_PRESSURE)).get("value")
            )
            data["supplyTemperature"] = (await self.client.get(URI_SUPPLY_TEMP)).get(
                "value"
            )
            data["outdoorTemperature"] = (await self.client.get(URI_OUTDOOR_TEMP)).get(
                "value"
            )
            data["hotWaterSupply"] = await self.client.get_hot_water_supply(
                data["uiStatus"].get("UMD")
            )
            data["displayCode"] = (await self.client.get(URI_DISPLAYCODE)).get("value")
            data["causeCode"] = (await self.client.get(URI_CAUSECODE)).get("value")
        except NefitAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NefitError as err:
            raise UpdateFailed(str(err)) from err
        return data
