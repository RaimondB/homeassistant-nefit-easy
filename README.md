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

## Gas-usage statistics (optional)

The boiler stores a daily gas-usage history. Enabling **Import gas-usage
history** in the integration options publishes four long-term statistics:

- `nefit_easy:gas_central_heating` — daily CH gas (kWh)
- `nefit_easy:gas_hot_water` — daily hot-water gas (kWh)
- `nefit_easy:gas_total` — CH + HW (kWh)
- `nefit_easy:gas_outdoor_temp` — daily mean outdoor temperature (°C)

On first enable the full history is back-filled, paced ~5 s per page to
respect the cloud rate limit, then refreshed daily. The
`nefit_easy.import_gas_history` service re-runs the full import on
demand (idempotent). Disabling the option leaves already-imported
statistics in place.

These statistics are **not** added to the Energy dashboard
automatically. If you want them there, add `nefit_easy:gas_total` (or
the CH/HW split) under **Settings → Energy → Gas consumption** yourself.
This is primarily useful if you do **not** have a smart gas meter — it
is not a meter replacement, but the boiler's CH-vs-HW split is an
insight a whole-house meter cannot provide.

## Notes

- The Nefit cloud throttles to roughly one request per minute; the poll
  interval has a hard 60-second floor.
- Credentials are never logged; diagnostics output is redacted.

## Troubleshooting

If setup fails with *"Could not connect to the Nefit cloud"*, enable debug
logging to see the real reason (DNS failure, connection refused, TLS,
auth, timeout). Add to `configuration.yaml` and restart:

```yaml
logger:
  default: info
  logs:
    custom_components.nefit_easy: debug
    slixmpp: debug
```

Connection errors are logged at **ERROR** level (visible without debug);
`slixmpp: debug` additionally shows the full XMPP wire trace.

Common cause: the **Home Assistant host cannot resolve or reach**
`wa2-mz36-qrmzh6.bosch.de:5222` (container DNS, firewall, or network
egress) even when another machine on the LAN can. Verify from the HA
host/container itself.

For protocol-level debugging without Home Assistant, use the
[`scripts/probe`](scripts/probe) standalone tool in this repo.

## License

MIT — see [LICENSE](LICENSE). Protocol originally reverse-engineered by
Robert Klep; Node-RED implementation by Raimond Brookman.
