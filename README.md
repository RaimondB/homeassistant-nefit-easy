# Nefit/Bosch Easy — Home Assistant integration

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

A **native** Home Assistant custom integration for Nefit/Bosch Easy
thermostats. This is a from-scratch Python rewrite of the functionality in
[`node-red-contrib-nefit-easy`](https://github.com/RaimondB/node-red-contrib-nefit-easy)
— not a wrapper. The Bosch cloud protocol (XMPP over TLS + AES-256-ECB body
encryption) is reimplemented in-repo; there is no third-party protocol
dependency.

> Status: **early development.** Phase 1 (climate + core sensors) is the MVP.
> Gas-usage history / Energy dashboard support is a later, opt-in phase.

## Features (target)

- **Climate**: current temperature, setpoint, manual/clock mode, fireplace
  preset, holiday (read-only); `nefit_easy.set_temperature` service for
  relative setpoint expressions (`setpoint + 1`, `in house temp - 0.5`, …).
- **Sensors**: system pressure, supply/flow temperature, outdoor temperature,
  indoor temperature, boiler status/cause code, boiler indicator.
- **Binary sensors**: holiday, powersave, boiler block/lock/maintenance,
  hot-water active.
- **Switches**: hot-water supply, fireplace mode.
- **Phase 3 (opt-in)**: daily gas-usage history into the Energy dashboard.

## Installation (HACS)

1. HACS → Integrations → ⋮ → Custom repositories → add
   `https://github.com/RaimondB/homeassistant-nefit-easy` (category:
   Integration).
2. Install **Nefit/Bosch Easy**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → *Nefit/Bosch Easy*.
4. Enter **serial number**, **access key** and **password** (the same
   credentials the Bosch/Nefit app uses).

## Notes

- The Nefit cloud throttles to roughly one request per minute; the poll
  interval has a hard 60-second floor.
- Credentials are never logged; diagnostics output is redacted.

## License

MIT — see [LICENSE](LICENSE). Protocol originally reverse-engineered by
Robert Klep; Node-RED implementation by Raimond Brookman.
