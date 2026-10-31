"""DataUpdateCoordinator for Nefit/Bosch Easy.

A poll is ``/ecus/rrc/uiStatus`` (room temp, setpoint, modes, burner state,
hot-water setting) plus the display code: two requests a minute. The display
code stays at that rate because the boiler's waiting episodes last one or two
minutes. Everything else is read on its own slower clock, the cause code only
when the display code changes. The backend drops sessions that are polled
much harder; a poll used to be seven requests.
"""

from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import NefitAuthError, NefitClient, NefitError
from .const import (
    DOMAIN,
    MIN_SCAN_INTERVAL,
    SENSOR_SENTINEL_VALUE,
    URI_CAUSECODE,
    URI_DISPLAYCODE,
    URI_OUTDOOR_TEMP,
    URI_PRESSURE,
    URI_SUPPLY_TEMP,
    URI_UISTATUS,
)

_LOGGER = logging.getLogger(__name__)

# Seconds between reads of the slow values.
_SLOW_READS = {
    URI_SUPPLY_TEMP: 300.0,
    URI_OUTDOOR_TEMP: 900.0,
    URI_PRESSURE: 900.0,
}
# A refresh asked for sooner than this after the last poll sends nothing.
_MIN_POLL_GAP = MIN_SCAN_INTERVAL - 5


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
        self.clock = time.monotonic
        self._last_poll: float | None = None
        self._read_at: dict[str, float] = {}
        # Cleared when the boiler answers "no sensor"; it never grows one.
        self._has_pressure = True

    def _due(self, uri: str) -> bool:
        read_at = self._read_at.get(uri)
        return read_at is None or self.clock() - read_at >= _SLOW_READS[uri] - 5

    async def _read_slow(self, uri: str) -> Any:
        value = (await self.client.get(uri)).get("value")
        self._read_at[uri] = self.clock()
        return value

    async def _async_update_data(self) -> dict[str, Any]:
        prev = self.data or {}
        now = self.clock()
        if self._last_poll is not None and now - self._last_poll < _MIN_POLL_GAP:
            # A refresh asked for between polls (update_entity, a reload
            # race): the last poll is fresh enough, send nothing.
            return prev
        self._last_poll = now
        data = dict(prev)  # slow values carry over until they are due
        try:
            status = (await self.client.get(URI_UISTATUS)).get("value", {})
            data["uiStatus"] = status
            # DHW in uiStatus is the hot-water supply setting itself; the
            # dhwOperation*Mode endpoints only repeat it.
            data["hotWaterSupply"] = status.get("DHW")
            display = (await self.client.get(URI_DISPLAYCODE)).get("value")
            if "causeCode" not in prev or display != prev.get("displayCode"):
                data["causeCode"] = (await self.client.get(URI_CAUSECODE)).get("value")
            data["displayCode"] = display
            if self._due(URI_SUPPLY_TEMP):
                data["supplyTemperature"] = await self._read_slow(URI_SUPPLY_TEMP)
            if self._due(URI_OUTDOOR_TEMP):
                data["outdoorTemperature"] = await self._read_slow(URI_OUTDOOR_TEMP)
            if self._has_pressure and self._due(URI_PRESSURE):
                raw = await self._read_slow(URI_PRESSURE)
                data["pressure"] = _drop_sentinel(raw)
                if raw is not None and data["pressure"] is None:
                    _LOGGER.debug("Boiler has no pressure sensor; not asking again")
                    self._has_pressure = False
            data.setdefault("pressure", None)
        except NefitAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NefitError as err:
            raise UpdateFailed(str(err)) from err
        return data

    @callback
    def async_patch_status(self, **fields: Any) -> None:
        """Show a write at once; the next scheduled poll confirms it.

        Used instead of an immediate refresh, which would be a second
        monitoring poll within the minute.
        """
        if self.data is None:
            return
        status = {**self.data.get("uiStatus", {}), **fields}
        data = {**self.data, "uiStatus": status}
        if "DHW" in fields:
            data["hotWaterSupply"] = fields["DHW"]
        self.async_set_updated_data(data)
