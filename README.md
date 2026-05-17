# Nefit/Bosch Easy — Home Assistant integration

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

A **native** Home Assistant custom integration for Nefit/Bosch Easy
thermostats. This is a from-scratch Python rewrite of the functionality in
[`node-red-contrib-nefit-easy`](https://github.com/RaimondB/node-red-contrib-nefit-easy)
— not a wrapper. The Bosch cloud protocol (XMPP over TLS + AES-256-ECB body
encryption) is reimplemented in-repo; there is no third-party protocol
dependency.

> Status: **first release.** Supports most sensors and controls and allows for importing Gas-usage history in the Energy dashboard.

## Features (target)

- **Climate**: current temperature, setpoint, manual/clock mode, fireplace
  preset, holiday (read-only); `nefit_easy.set_temperature` service for
  relative setpoint expressions (`setpoint + 1`, `in house temp - 0.5`, …).
- **Sensors**: system pressure, supply/flow temperature, outdoor temperature,
  indoor temperature, boiler status/cause code, boiler indicator.
- **Binary sensors**: holiday, powersave, boiler block/lock/maintenance,
  hot-water active.
- **Switches**: hot-water supply, fireplace mode.
- **Gas Usage History**: daily gas-usage history into the Energy dashboard.

## Installation (HACS)

1. HACS → Integrations → ⋮ → Custom repositories → add
   `https://github.com/RaimondB/homeassistant-nefit-easy` (category:
   Integration).
2. Install **Nefit/Bosch Easy**, restart Home Assistant.
3. Settings → Devices & Services → Add Integration → *Nefit/Bosch Easy*.
4. Enter **serial number**, **access key** and **password** (the same
   credentials the Bosch/Nefit app uses).

## Gas-usage statistics (optional)

The boiler stores a daily gas-usage history that can be published as
four long-term statistics:

- `nefit_easy:gas_central_heating` — daily CH gas (kWh)
- `nefit_easy:gas_hot_water` — daily hot-water gas (kWh)
- `nefit_easy:gas_total` — CH + HW (kWh)
- `nefit_easy:gas_outdoor_temp` — daily mean outdoor temperature (°C)

There are two independent ways to trigger the import:

- **Option — *Import gas-usage history*** (integration *Configure*
  dialog): when enabled, the full history is back-filled once on
  setup/reload and then a daily incremental refresh keeps it current.
  This is the "set and forget" path. Disabling the option stops the
  automatic refresh but **leaves already-imported statistics in place**.
- **Service — `nefit_easy.import_gas_history`**: runs the full back-fill
  on demand, **regardless of whether the option is enabled**. Use it for
  a one-off import, or to force a re-sync. It is idempotent — re-running
  never double-counts (already-imported days are skipped).

In short: the option controls the *automatic* behaviour; the service is
an *explicit* trigger that always works. The import is paced ~5 s per
page to respect the Nefit cloud rate limit, so a full back-fill of
several years takes a few minutes (watch progress with the debug logger
below).

External statistics have no entity — they appear under
**Developer Tools → Statistics** and in *Statistics graph* dashboard
cards (using the `nefit_easy:gas_*` IDs directly), not in normal
entity History.

These statistics are **not** added to the Energy dashboard
automatically. If you want them there, add `nefit_easy:gas_total` (or
the CH/HW split) under **Settings → Energy → Gas consumption** yourself.
This is primarily useful if you do **not** have a smart gas meter — it
is not a meter replacement, but the boiler's CH-vs-HW split is an
insight a whole-house meter cannot provide.

### Units: kWh vs m³

The boiler reports gas in **kWh** and that is what is published. The
Home Assistant Energy dashboard accepts kWh gas sources directly (no m³
required), so `nefit_easy:gas_total` works there as-is. There is
intentionally **no m³ variant**: the boiler exposes no volume figure,
and converting would need a fixed calorific value that varies by region
and over time — a lossy approximation on top of the boiler's own
estimate.

If your gas is billed per m³ and you only want **cost**, you do not
need m³ at all — set the price per kWh in the Energy dashboard:

```text
price_per_kWh = price_per_m³ / calorific_value
# NL G-gas ≈ 9.769 kWh/m³, e.g. €1.45/m³ → €0.1484/kWh
```

If you genuinely need an **m³ figure** (e.g. to reconcile with the
meter), convert with a template sensor using your local calorific
value. Note external statistics have no entity, so this derives from a
kWh sensor *you* expose (or any kWh gas entity); it is approximate:

```yaml
# configuration.yaml
template:
  - sensor:
      - name: Nefit gas total m3
        unique_id: nefit_gas_total_m3
        unit_of_measurement: "m³"
        device_class: gas
        state_class: total_increasing
        # 9.769 = NL G-gas calorific value (kWh per m³) — adjust to
        # your region / energy bill.
        state: "{{ (states('sensor.nefit_gas_total_kwh') | float(0) / 9.769) | round(3) }}"
        availability: "{{ states('sensor.nefit_gas_total_kwh') not in ['unknown','unavailable'] }}"
```

That m³ template sensor can then be selected under
**Settings → Energy → Gas consumption** like any other gas entity. (For
a *rate* such as m³/h rather than a converted total, use the
[`derivative`](https://www.home-assistant.io/integrations/derivative/)
helper on the m³ sensor.)

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

The same `custom_components.nefit_easy: debug` logger also traces the
gas-usage import: option state at setup, pages fetched, days collected,
the per-statistic resume point, and a warning if the
`import_gas_history` service finds no helper. If imported statistics
look empty, check **Developer Tools → Statistics** (not entity History)
— external statistics have no entity.

For protocol-level debugging without Home Assistant, use the
[`scripts/probe`](scripts/probe) standalone tool in this repo.

## License

MIT — see [LICENSE](LICENSE). 
Protocol originally reverse-engineered by
Robert Klep; [Node-RED implementation](https://github.com/RaimondB/node-red-contrib-nefit-easy) by Raimond Brookman as an improvement to the early work done by PepijnG.
