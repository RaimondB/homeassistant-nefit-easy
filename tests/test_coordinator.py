"""Coordinator data-mapping and error-translation tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.nefit_easy.api import NefitAuthError, NefitConnectionError
from custom_components.nefit_easy.coordinator import NefitDataUpdateCoordinator


def _coordinator(hass, client) -> NefitDataUpdateCoordinator:
    entry = MagicMock()
    entry.data = {"serial_number": "ABC123"}
    return NefitDataUpdateCoordinator(hass, entry, client, scan_interval=60)


async def test_update_merges_endpoints(hass, mock_client) -> None:
    coordinator = _coordinator(hass, mock_client)
    data = await coordinator._async_update_data()
    assert data["uiStatus"]["IHT"] == 19.5
    assert data["pressure"] == 1.6
    assert data["supplyTemperature"] == 45.0
    assert data["outdoorTemperature"] == 8.0


async def test_auth_error_maps_to_config_entry_auth_failed(hass) -> None:
    client = AsyncMock()
    client.get.side_effect = NefitAuthError("bad creds")
    coordinator = _coordinator(hass, client)
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_connection_error_maps_to_update_failed(hass) -> None:
    client = AsyncMock()
    client.get.side_effect = NefitConnectionError("xmpp down")
    coordinator = _coordinator(hass, client)
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
