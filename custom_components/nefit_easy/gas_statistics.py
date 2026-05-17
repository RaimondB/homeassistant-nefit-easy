"""Import Nefit/Bosch Easy gas-usage history into HA long-term statistics.

A slow, opt-in, second data path that is deliberately kept off the 60s
coordinator poll. The boiler stores daily CH/HW gas (kWh) plus a daily
outdoor-temperature average; we publish those as four *external*
statistics (``nefit_easy:gas_central_heating``, ``…:gas_hot_water``,
``…:gas_total``, ``…:gas_outdoor_temp``).

These are only published — HA never auto-adds them to the Energy
dashboard. The user opts in via the integration option and may add
``nefit_easy:gas_total`` (or CH/HW) under Settings → Energy themselves.

Idempotency: each device date label (``DD-MM-YYYY``) is interpreted as a
UTC-midnight bucket ``datetime(y, m, d, tzinfo=UTC)``. This avoids local
DST drift and means re-imports land on the exact same ``start`` so the
recorder de-duplicates by ``(statistic_id, start)``. Per energy stat we
resume from ``get_last_statistics`` and only append days strictly after
the last recorded ``start``, carrying our own monotonic running sum.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.helpers.recorder import get_instance

# mean_type was added in HA 2025.x; guard so the same code runs on
# older HA installs (phacc pin) and produces no deprecation warning
# on newer ones.
try:
    from homeassistant.components.recorder.models import (
        StatisticMeanType,
    )

    _MEAN_NONE = StatisticMeanType.NONE
    _MEAN_ARITHMETIC = StatisticMeanType.ARITHMETIC
except ImportError:
    _MEAN_NONE = None  # type: ignore[assignment]
    _MEAN_ARITHMETIC = None  # type: ignore[assignment]

from .api import NefitError
from .const import (
    DOMAIN,
    GAS_PAGE_DELAY_SECONDS,
    GAS_PAGE_SIZE,
    STAT_ID_CH,
    STAT_ID_HW,
    STAT_ID_OUTDOOR,
    STAT_ID_TOTAL,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .api import NefitClient

_LOGGER = logging.getLogger(__name__)

# Energy statistics (cumulative sum) keyed by statistic_id -> friendly name.
_ENERGY_STATS: dict[str, str] = {
    STAT_ID_CH: "Nefit gas — central heating",
    STAT_ID_HW: "Nefit gas — hot water",
    STAT_ID_TOTAL: "Nefit gas — total",
}


def _bucket(day: Any) -> datetime:
    """Device date label -> stable UTC-midnight statistics bucket."""
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


class NefitGasStatistics:
    """Collects gas-usage history and writes it as external statistics."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: NefitClient
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._client = client
        # Serialize service / daily / backfill so they never overlap.
        self._lock = asyncio.Lock()

    # -- public orchestration -------------------------------------------
    async def async_backfill(self) -> None:
        """Full-history import (first enable / service / reload)."""
        await self.async_import(full=True)

    async def async_daily(self, _now: Any = None) -> None:
        """Scheduled incremental import (last page only)."""
        await self.async_import(full=False)

    async def async_import(self, *, full: bool) -> None:
        """Collect history and publish all four statistics.

        Never raises into a scheduler/background task: NefitError (and a
        cancelled/stopping hass) are logged and swallowed; the next run
        resumes idempotently.
        """
        _LOGGER.debug("Gas-usage import started (full=%s)", full)
        async with self._lock:
            try:
                days = await self._collect(full=full)
            except NefitError as err:
                _LOGGER.warning("Gas-usage import aborted: %s", err)
                return
            except Exception:
                _LOGGER.exception("Gas-usage import unexpected error")
                return
            _LOGGER.debug("Gas-usage import collected %d days", len(days))
            if not days:
                _LOGGER.debug("Gas-usage import: no rows collected")
                return
            # De-dup by bucket, sort ascending — the device can repeat a
            # day across the boundary page on incremental runs.
            by_start = {_bucket(d["date"]): d for d in days}
            ordered = [by_start[s] for s in sorted(by_start)]
            _LOGGER.debug(
                "Gas-usage import: date range %s to %s",
                ordered[0]["date"],
                ordered[-1]["date"],
            )
            await self._publish_energy(ordered)
            await self._publish_outdoor(ordered)
            _LOGGER.debug("Gas-usage import finished")

    # -- collection ------------------------------------------------------
    async def _collect(self, *, full: bool) -> list[dict[str, Any]]:
        pointer = await self._client.gas_usage_pointer()
        _LOGGER.debug("Gas-usage pointer: %d records", pointer)
        if pointer <= 0:
            return []
        # Pages are 1-indexed (page=0 is rejected with HTTP 400).
        pages = math.ceil(pointer / GAS_PAGE_SIZE)
        # Incremental: only the newest (last) page; full: every page.
        page_range = range(1, pages + 1) if full else range(pages, pages + 1)
        _LOGGER.debug("Gas-usage collecting pages %s (full=%s)", list(page_range), full)
        rows: list[dict[str, Any]] = []
        for i, page in enumerate(page_range):
            if self._hass.is_stopping:
                _LOGGER.debug("Gas-usage import interrupted (hass stopping)")
                break
            if i:
                await asyncio.sleep(GAS_PAGE_DELAY_SECONDS)
            page_rows = await self._client.gas_usage(page)
            _LOGGER.debug("Gas-usage page %d: %d rows", page, len(page_rows))
            rows.extend(page_rows)
        return rows

    # -- recorder reads (executor) --------------------------------------
    async def _last_sum(self, statistic_id: str) -> tuple[datetime | None, float]:
        last = await get_instance(self._hass).async_add_executor_job(
            get_last_statistics,
            self._hass,
            1,
            statistic_id,
            True,
            {"sum", "start"},
        )
        rows = last.get(statistic_id)
        if not rows:
            return None, 0.0
        row = rows[0]
        start = datetime.fromtimestamp(row["start"], tz=UTC)
        return start, float(row["sum"] or 0.0)

    async def _last_start(self, statistic_id: str) -> datetime | None:
        last = await get_instance(self._hass).async_add_executor_job(
            get_last_statistics,
            self._hass,
            1,
            statistic_id,
            True,
            {"start"},
        )
        rows = last.get(statistic_id)
        if not rows:
            return None
        return datetime.fromtimestamp(rows[0]["start"], tz=UTC)

    # -- publishing ------------------------------------------------------
    async def _publish_energy(self, ordered: list[dict[str, Any]]) -> None:
        def _daily(statistic_id: str, row: dict[str, Any]) -> float:
            if statistic_id == STAT_ID_CH:
                return row["ch_kwh"]
            if statistic_id == STAT_ID_HW:
                return row["hw_kwh"]
            return row["ch_kwh"] + row["hw_kwh"]

        for statistic_id, name in _ENERGY_STATS.items():
            last_start, running = await self._last_sum(statistic_id)
            _LOGGER.debug(
                "%s: resume from last_start=%s running_sum=%.3f",
                statistic_id,
                last_start,
                running,
            )
            stats: list[StatisticData] = []
            for row in ordered:
                start = _bucket(row["date"])
                if last_start is not None and start <= last_start:
                    continue
                daily = _daily(statistic_id, row)
                running += daily
                stats.append(StatisticData(start=start, state=daily, sum=running))
            if not stats:
                _LOGGER.debug("%s: no new rows to publish", statistic_id)
                continue
            meta: StatisticMetaData = {
                "has_mean": False,
                "has_sum": True,
                "name": name,
                "source": DOMAIN,
                "statistic_id": statistic_id,
                "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
            }
            if _MEAN_NONE is not None:
                meta["mean_type"] = _MEAN_NONE  # type: ignore[typeddict-unknown-key]
            metadata = meta
            async_add_external_statistics(self._hass, metadata, stats)
            _LOGGER.debug("Published %d rows to %s", len(stats), statistic_id)

    async def _publish_outdoor(self, ordered: list[dict[str, Any]]) -> None:
        last_start = await self._last_start(STAT_ID_OUTDOOR)
        stats: list[StatisticData] = []
        for row in ordered:
            start = _bucket(row["date"])
            if last_start is not None and start <= last_start:
                continue
            stats.append(StatisticData(start=start, mean=row["outdoor_temp"]))
        if not stats:
            return
        meta_out: StatisticMetaData = {
            "has_mean": True,
            "has_sum": False,
            "name": "Nefit gas — outdoor temperature",
            "source": DOMAIN,
            "statistic_id": STAT_ID_OUTDOOR,
            "unit_of_measurement": "°C",
        }
        if _MEAN_ARITHMETIC is not None:
            meta_out["mean_type"] = _MEAN_ARITHMETIC  # type: ignore[typeddict-unknown-key]
        metadata = meta_out
        async_add_external_statistics(self._hass, metadata, stats)
        _LOGGER.debug("Published %d rows to %s", len(stats), STAT_ID_OUTDOOR)
