"""Shared test fixtures. Network is never touched — the client is mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of the custom integration in every test."""
    yield


@pytest.fixture
def mock_client() -> AsyncMock:
    """A mocked NefitClient returning canned endpoint payloads."""
    client = AsyncMock()
    client.get.side_effect = lambda uri: {
        "/ecus/rrc/uiStatus": {"value": {"IHT": 19.5, "TSP": 21.0, "UMD": "manual"}},
        "/system/appliance/systemPressure": {"value": 1.6},
        "/heatingCircuits/hc1/actualSupplyTemperature": {"value": 45.0},
        "/system/sensors/temperatures/outdoor_t1": {"value": 8.0},
        "/gateway/versionFirmware": {"value": "1.2.3"},
        "/system/appliance/displaycode": {"value": "-H"},
        "/system/appliance/causecode": {"value": 200},
    }[uri]
    client.put.return_value = {"status": "ok"}
    client.get_hot_water_supply.return_value = "on"
    return client
