"""Constants for the Nefit/Bosch Easy integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "nefit_easy"

# --- Configuration keys ---------------------------------------------------
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_ACCESS_KEY: Final = "access_key"
CONF_PASSWORD: Final = "password"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Nefit cloud enforces a ~60s minimum poll interval. This is a hard floor.
MIN_SCAN_INTERVAL: Final = 60
DEFAULT_SCAN_INTERVAL: Final = 60

# --- Bosch cloud protocol -------------------------------------------------
DEFAULT_HOST: Final = "wa2-mz36-qrmzh6.bosch.de"
DEFAULT_PORT: Final = 5222

ACCESSKEY_PREFIX: Final = "Ct7ZR03b_"
RRC_CONTACT_PREFIX: Final = "rrccontact_"
RRC_GATEWAY_PREFIX: Final = "rrcgateway_"

# Magic key used in AES-256-ECB key derivation (from nefit-easy-core).
MAGIC_HEX: Final = "58f18d70f667c9c79ef7de435bf0f9b1553bbb6e61816212ab80e5b0d351fbb1"

# --- Endpoints (GET) ------------------------------------------------------
URI_UISTATUS: Final = "/ecus/rrc/uiStatus"
URI_OUTDOOR_TEMP: Final = "/system/sensors/temperatures/outdoor_t1"
URI_PRESSURE: Final = "/system/appliance/systemPressure"
URI_SUPPLY_TEMP: Final = "/heatingCircuits/hc1/actualSupplyTemperature"
URI_USERMODE: Final = "/heatingCircuits/hc1/usermode"
URI_DISPLAYCODE: Final = "/system/appliance/displaycode"
URI_CAUSECODE: Final = "/system/appliance/causecode"
URI_LATITUDE: Final = "/system/location/latitude"
URI_LONGITUDE: Final = "/system/location/longitude"
URI_DHW_CLOCK: Final = "/dhwCircuits/dhwA/dhwOperationClockMode"
URI_DHW_MANUAL: Final = "/dhwCircuits/dhwA/dhwOperationManualMode"
URI_FIRMWARE: Final = "/gateway/versionFirmware"

# --- Endpoints (PUT) ------------------------------------------------------
URI_TEMP_ROOM_MANUAL: Final = "/heatingCircuits/hc1/temperatureRoomManual"
URI_TEMP_OVERRIDE_STATUS: Final = "/heatingCircuits/hc1/manualTempOverride/status"
URI_TEMP_OVERRIDE_TEMP: Final = "/heatingCircuits/hc1/manualTempOverride/temperature"
URI_FIREPLACE: Final = "/ecus/rrc/userprogram/fireplacefunction"

# --- Phase 3 (gas usage, deferred) ---------------------------------------
URI_GASUSAGE_POINTER: Final = "/ecus/rrc/recordings/gasusagePointer"
URI_GASUSAGE_PAGE: Final = "/ecus/rrc/recordings/gasusage?page={page}"
