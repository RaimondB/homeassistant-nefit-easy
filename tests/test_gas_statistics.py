"""Gas-usage history -> external statistics (fully offline)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.nefit_easy.api.client import NefitClient
from custom_components.nefit_easy.const import (
    STAT_ID_CH,
    STAT_ID_HW,
    STAT_ID_OUTDOOR,
    STAT_ID_TOTAL,
)
from custom_components.nefit_easy.gas_statistics import NefitGasStatistics

# --- client.gas_usage parsing -------------------------------------------


def _client_with(get_result) -> NefitClient:
    client = NefitClient.__new__(NefitClient)
    client.get = AsyncMock(return_value=get_result)  # type: ignore[method-assign]
    return client


async def test_gas_usage_skips_sentinel_and_malformed() -> None:
    client = _client_with(
        {
            "value": [
                {"d": "13-02-2024", "ch": 10.0, "hw": 2.0, "T": 55},
                {"d": "255-256-65535", "ch": 0, "hw": 0, "T": 0},  # sentinel
                {"d": "garbage", "ch": 1, "hw": 1, "T": 1},  # malformed
                {"d": "14-02-2024", "ch": 5, "hw": 1, "T": -3},
            ]
        }
    )
    days = await client.gas_usage(0)
    assert [d["date"] for d in days] == [date(2024, 2, 13), date(2024, 2, 14)]
    assert days[0] == {
        "date": date(2024, 2, 13),
        "ch_kwh": 10.0,
        "hw_kwh": 2.0,
        "outdoor_temp": 5.5,
    }
    assert days[1]["outdoor_temp"] == pytest.approx(-0.3)


async def test_gas_usage_pointer() -> None:
    client = _client_with({"value": "67"})
    assert await client.gas_usage_pointer() == 67


# --- NefitGasStatistics -------------------------------------------------


def _row(d: date, ch: float, hw: float, t: float) -> dict:
    return {"date": d, "ch_kwh": ch, "hw_kwh": hw, "outdoor_temp": t}


def _make(monkeypatch, *, pages: dict[int, list[dict]], pointer: int):
    hass = MagicMock()
    hass.is_stopping = False
    client = AsyncMock()
    client.gas_usage_pointer = AsyncMock(return_value=pointer)
    client.gas_usage = AsyncMock(side_effect=lambda p: pages.get(p, []))

    recorder = MagicMock()

    async def _exec(func, *args):
        return func(*args)

    recorder.async_add_executor_job = AsyncMock(side_effect=_exec)

    added: list[tuple] = []
    last: dict[str, list[dict]] = {}

    monkeypatch.setattr(
        "custom_components.nefit_easy.gas_statistics.get_instance",
        lambda _h: recorder,
    )
    monkeypatch.setattr(
        "custom_components.nefit_easy.gas_statistics.async_add_external_statistics",
        lambda _h, meta, stats: added.append((meta, stats)),
    )
    monkeypatch.setattr(
        "custom_components.nefit_easy.gas_statistics.get_last_statistics",
        lambda _h, _n, sid, _c, _t: {k: v for k, v in last.items() if k == sid},
    )
    # No sleeping between pages in tests.
    monkeypatch.setattr(
        "custom_components.nefit_easy.gas_statistics.asyncio.sleep",
        AsyncMock(),
    )

    gas = NefitGasStatistics(hass, MagicMock(), client)
    return gas, added, last


async def test_backfill_pagination_sums_and_total(monkeypatch) -> None:
    pages = {
        1: [_row(date(2024, 1, 1), 10.0, 2.0, 5.0)],
        2: [_row(date(2024, 1, 2), 4.0, 1.0, 6.0)],
    }
    gas, added, _ = _make(monkeypatch, pages=pages, pointer=33)  # ceil(33/32)=2

    await gas.async_backfill()

    by_id = {meta["statistic_id"]: stats for meta, stats in added}
    assert set(by_id) == {STAT_ID_CH, STAT_ID_HW, STAT_ID_TOTAL, STAT_ID_OUTDOOR}

    ch = by_id[STAT_ID_CH]
    assert [s["state"] for s in ch] == [10.0, 4.0]
    assert [s["sum"] for s in ch] == [10.0, 14.0]  # monotonic, cumulative

    total = by_id[STAT_ID_TOTAL]
    assert [s["state"] for s in total] == [12.0, 5.0]
    assert [s["sum"] for s in total] == [12.0, 17.0]

    outdoor = by_id[STAT_ID_OUTDOOR]
    assert [s["mean"] for s in outdoor] == [5.0, 6.0]
    assert all("sum" not in s for s in outdoor)
    assert [s["start"] for s in ch] == [
        datetime(2024, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 2, tzinfo=UTC),
    ]


async def test_metadata_objects(monkeypatch) -> None:
    pages = {1: [_row(date(2024, 1, 1), 1.0, 1.0, 3.0)]}
    gas, added, _ = _make(monkeypatch, pages=pages, pointer=1)
    await gas.async_backfill()
    meta_by_id = {m["statistic_id"]: m for m, _ in added}
    for sid in (STAT_ID_CH, STAT_ID_HW, STAT_ID_TOTAL):
        m = meta_by_id[sid]
        assert m["has_sum"] is True and m["has_mean"] is False
        assert m["source"] == "nefit_easy"
        assert m["unit_of_measurement"] == "kWh"
    om = meta_by_id[STAT_ID_OUTDOOR]
    assert om["has_mean"] is True and om["has_sum"] is False
    assert om["unit_of_measurement"] == "°C"


async def test_idempotent_resume(monkeypatch) -> None:
    pages = {1: [_row(date(2024, 1, 1), 10.0, 2.0, 5.0)]}
    gas, added, last = _make(monkeypatch, pages=pages, pointer=1)

    # Pretend everything up to and including 2024-01-01 was already stored.
    ts = datetime(2024, 1, 1, tzinfo=UTC).timestamp()
    for sid, total in (
        (STAT_ID_CH, 10.0),
        (STAT_ID_HW, 2.0),
        (STAT_ID_TOTAL, 12.0),
        (STAT_ID_OUTDOOR, 0.0),
    ):
        last[sid] = [{"start": ts, "sum": total}]

    await gas.async_backfill()
    assert added == []  # nothing new written


async def test_incremental_last_page_only(monkeypatch) -> None:
    pages = {
        1: [_row(date(2024, 1, 1), 9.0, 0.0, 1.0)],
        3: [_row(date(2024, 3, 1), 3.0, 0.0, 2.0)],
    }
    gas, added, _ = _make(monkeypatch, pages=pages, pointer=70)  # ceil=3, last=3
    await gas.async_daily()
    ch = next(s for m, s in added if m["statistic_id"] == STAT_ID_CH)
    assert [s["state"] for s in ch] == [3.0]
    gas._client.gas_usage.assert_awaited_once_with(3)


async def test_import_swallows_nefit_error(monkeypatch) -> None:
    from custom_components.nefit_easy.api import NefitError

    gas, added, _ = _make(monkeypatch, pages={}, pointer=1)
    gas._client.gas_usage_pointer = AsyncMock(side_effect=NefitError("boom"))
    await gas.async_backfill()  # must not raise
    assert added == []
