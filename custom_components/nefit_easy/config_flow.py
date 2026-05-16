"""Config, options and reauth flow for Nefit/Bosch Easy."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback

from .api import NefitAuthError, NefitError, async_create_client
from .const import (
    CONF_ACCESS_KEY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SERIAL_NUMBER,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
    URI_FIRMWARE,
)


async def _validate(
    hass: HomeAssistant, serial: str, access_key: str, password: str
) -> None:
    """Connect and do one firmware GET to prove the credentials work."""
    client = await async_create_client(hass, serial, access_key, password)
    try:
        await client.connect()
        await client.get(URI_FIRMWARE)
    finally:
        await client.disconnect()


class NefitConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the UI configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            serial = user_input[CONF_SERIAL_NUMBER]
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()
            try:
                await _validate(
                    self.hass,
                    serial,
                    user_input[CONF_ACCESS_KEY],
                    user_input[CONF_PASSWORD],
                )
            except NefitAuthError:
                errors["base"] = "invalid_auth"
            except NefitError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Nefit Easy {serial}", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_NUMBER): str,
                vol.Required(CONF_ACCESS_KEY): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> NefitOptionsFlow:
        return NefitOptionsFlow(entry)


class NefitOptionsFlow(OptionsFlow):
    """Scan-interval option with a hard 60s floor."""

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_SCAN_INTERVAL] < MIN_SCAN_INTERVAL:
                errors["base"] = "scan_interval_too_low"
            else:
                return self.async_create_entry(title="", data=user_input)

        current = self._entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
