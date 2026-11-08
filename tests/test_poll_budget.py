"""A poll is uiStatus + display code; the rest is read on slower clocks."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.nefit_easy.const import (
    URI_CAUSECODE,
    URI_DISPLAYCODE,
    URI_OUTDOOR_TEMP,
    URI_PRESSURE,
    URI_SUPPLY_TEMP,
    URI_UISTATUS,
)
from custom_components.nefit_easy.coordinator import NefitDataUpdateCoordinator


class _Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


def _setup(hass, mock_client, answers=None):
    answers = answers or {}
    inner = mock_client.get.side_effect
    sent: list[str] = []

    def get(uri):
        sent.append(uri)
        return {"value": answers[uri]} if uri in answers else inner(uri)

    mock_client.get.side_effect = get
    entry = MagicMock()
    entry.data = {"serial_number": "ABC123"}
    coordinator = NefitDataUpdateCoordinator(hass, entry, mock_client, 60)
    clock = _Clock()
    coordinator.clock = clock
    return coordinator, clock, sent


async def _poll(coordinator, clock, sent, after=60.0):
    clock.now += after
    sent.clear()
    coordinator.data = await coordinator._async_update_data()
    return set(sent)


async def test_first_poll_reads_everything_then_two_a_minute(hass, mock_client) -> None:
    c, clock, sent = _setup(hass, mock_client)
    assert await _poll(c, clock, sent, after=0) == {
        URI_UISTATUS,
        URI_DISPLAYCODE,
        URI_CAUSECODE,
        URI_SUPPLY_TEMP,
        URI_OUTDOOR_TEMP,
        URI_PRESSURE,
    }
    for _ in range(3):
        assert await _poll(c, clock, sent) == {URI_UISTATUS, URI_DISPLAYCODE}
    # Slow values carry over between their reads.
    assert c.data["supplyTemperature"] == 45.0
    assert c.data["outdoorTemperature"] == 8.0
    assert c.data["pressure"] == 1.6


async def test_slow_values_come_due(hass, mock_client) -> None:
    c, clock, sent = _setup(hass, mock_client)
    await _poll(c, clock, sent, after=0)
    seen: dict[str, int] = {}
    for _ in range(15):  # 15 minutes
        for uri in await _poll(c, clock, sent):
            seen[uri] = seen.get(uri, 0) + 1
    assert seen[URI_UISTATUS] == 15
    assert seen[URI_SUPPLY_TEMP] == 3  # every 5 min
    assert seen[URI_OUTDOOR_TEMP] == 1  # every 15 min
    assert URI_CAUSECODE not in seen  # display code never changed


async def test_cause_code_read_when_display_code_changes(hass, mock_client) -> None:
    answers = {URI_DISPLAYCODE: "-H"}
    c, clock, sent = _setup(hass, mock_client, answers)
    await _poll(c, clock, sent, after=0)
    answers[URI_DISPLAYCODE] = "0Y"
    assert URI_CAUSECODE in await _poll(c, clock, sent)
    assert c.data["displayCode"] == "0Y"
    assert URI_CAUSECODE not in await _poll(c, clock, sent)


async def test_hot_water_setting_comes_from_ui_status(hass, mock_client) -> None:
    answers = {URI_UISTATUS: {"DHW": "off", "UMD": "clock"}}
    c, clock, _sent = _setup(hass, mock_client, answers)
    await _poll(c, clock, _sent, after=0)
    assert c.data["hotWaterSupply"] == "off"
    mock_client.get_hot_water_supply.assert_not_awaited()


async def test_no_pressure_sensor_is_not_asked_again(hass, mock_client) -> None:
    c, clock, sent = _setup(hass, mock_client, {URI_PRESSURE: 25.5})
    assert URI_PRESSURE in await _poll(c, clock, sent, after=0)
    assert c.data["pressure"] is None
    for _ in range(31):
        assert URI_PRESSURE not in await _poll(c, clock, sent)
    assert c.data["pressure"] is None


async def test_refresh_between_polls_sends_nothing(hass, mock_client) -> None:
    c, clock, sent = _setup(hass, mock_client)
    await _poll(c, clock, sent, after=0)
    before = c.data
    assert await _poll(c, clock, sent, after=20) == set()
    assert c.data is before
    assert await _poll(c, clock, sent, after=40) == {URI_UISTATUS, URI_DISPLAYCODE}
