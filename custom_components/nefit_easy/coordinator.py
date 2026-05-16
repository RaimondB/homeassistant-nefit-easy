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
    URI_OUTDOOR_TEMP,
    URI_PRESSURE,
    URI_SUPPLY_TEMP,
    URI_UISTATUS,
)

_LOGGER = logging.getLogger(__name__)


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

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data: dict[str, Any] = {}
            data["uiStatus"] = (await self.client.get(URI_UISTATUS)).get("value", {})
            data["pressure"] = (await self.client.get(URI_PRESSURE)).get("value")
            data["supplyTemperature"] = (await self.client.get(URI_SUPPLY_TEMP)).get(
                "value"
            )
            data["outdoorTemperature"] = (await self.client.get(URI_OUTDOOR_TEMP)).get(
                "value"
            )
            data["hotWaterSupply"] = await self.client.get_hot_water_supply(
                data["uiStatus"].get("UMD")
            )
        except NefitAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NefitError as err:
            raise UpdateFailed(str(err)) from err
        return data
