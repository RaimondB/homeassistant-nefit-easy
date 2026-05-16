#!/usr/bin/env python3
"""Standalone Nefit/Bosch Easy client probe — no Home Assistant required.

Exercises the real protocol client (XMPP + SCRAM-SHA-1 + AES) against your
actual device so the transport/crypto can be validated independently of the
Home Assistant runtime.

Credentials come from the environment (never hard-code / commit them):

    NEFIT_SERIAL, NEFIT_ACCESS_KEY, NEFIT_PASSWORD

or a gitignored ./.nefit.env file with KEY=VALUE lines.

Usage:
    scripts/probe                 # connect + read a few endpoints
    scripts/probe --debug         # + full slixmpp wire log (diagnose setup)
    scripts/probe --get /system/appliance/systemPressure
    scripts/probe --get /ecus/rrc/uiStatus --get /gateway/versionFirmware
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import pathlib
import sys
import types

# --- Import the api package WITHOUT running custom_components/nefit_easy/
# __init__.py (which imports Home Assistant). Inject stub parent packages
# so `from ..const import ...` still resolves to the HA-free const module.
_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _name, _path in (
    ("custom_components", _ROOT / "custom_components"),
    ("custom_components.nefit_easy", _ROOT / "custom_components" / "nefit_easy"),
):
    _stub = types.ModuleType(_name)
    _stub.__path__ = [str(_path)]
    sys.modules[_name] = _stub

from custom_components.nefit_easy.api.client import NefitClient  # noqa: E402
from custom_components.nefit_easy.api.errors import NefitError  # noqa: E402
from custom_components.nefit_easy.const import (  # noqa: E402
    URI_FIRMWARE,
    URI_PRESSURE,
    URI_UISTATUS,
)


def _load_creds() -> tuple[str, str, str]:
    # Look for .nefit.env next to this script, at the repo root, and in CWD.
    _here = pathlib.Path(__file__).resolve().parent
    for env_file in (
        _here / ".nefit.env",
        _ROOT / ".nefit.env",
        pathlib.Path.cwd() / ".nefit.env",
    ):
        if env_file.exists():
            print(f"==> Loading credentials from {env_file}")
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            break
    try:
        return (
            os.environ["NEFIT_SERIAL"],
            os.environ["NEFIT_ACCESS_KEY"],
            os.environ["NEFIT_PASSWORD"],
        )
    except KeyError as err:
        sys.exit(
            f"Missing credential env var {err}. Set NEFIT_SERIAL, "
            "NEFIT_ACCESS_KEY, NEFIT_PASSWORD (or create ./.nefit.env)."
        )


async def _run(
    endpoints: list[str],
    timeout: float,  # noqa: ASYNC109
    set_temp: float | None,
) -> int:
    serial, access_key, password = _load_creds()
    client = NefitClient(serial, access_key, password)
    print(f"==> Connecting (serial {serial[:3]}***, timeout {timeout}s) ...")
    try:
        async with asyncio.timeout(timeout):
            await client.connect()
    except NefitError as err:
        print(f"!! connect failed: {type(err).__name__}: {err}")
        return 2
    except TimeoutError:
        print("!! connect timed out (no XMPP session). Try --debug.")
        return 2
    print("==> Connected.")

    rc = 0
    try:
        for uri in endpoints:
            try:
                result = await client.get(uri)
                print(f"\n--- GET {uri} ---")
                print(json.dumps(result, indent=2, default=str))
            except NefitError as err:
                rc = 3
                print(f"\n--- GET {uri} FAILED: {type(err).__name__}: {err}")
        if set_temp is not None:
            try:
                print(f"\n--- set_temperature({set_temp}) ---")
                print(json.dumps(await client.set_temperature(set_temp)))
            except NefitError as err:
                rc = 3
                print(f"set_temperature FAILED: {type(err).__name__}: {err}")
    finally:
        await client.disconnect()
        print("\n==> Disconnected.")
    return rc


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe a Nefit/Bosch Easy device.")
    parser.add_argument(
        "--get",
        dest="endpoints",
        action="append",
        help="endpoint URI to GET (repeatable). Default: firmware, uiStatus, pressure",
    )
    parser.add_argument(
        "--set-temp",
        type=float,
        default=None,
        help="set the manual room setpoint (°C) — WRITES to the device",
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument(
        "--debug", action="store_true", help="enable full slixmpp wire logging"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not args.debug:
        logging.getLogger("slixmpp").setLevel(logging.WARNING)

    endpoints = args.endpoints or [URI_FIRMWARE, URI_UISTATUS, URI_PRESSURE]
    raise SystemExit(asyncio.run(_run(endpoints, args.timeout, args.set_temp)))


if __name__ == "__main__":
    main()
