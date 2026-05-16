"""Import every integration module under a real Home Assistant.

This catches renamed/moved HA imports (e.g. DeviceInfo) that unit tests
focused on logic would otherwise miss, because HA only resolves a
platform's imports when it loads that platform.
"""

from __future__ import annotations

import importlib

import pytest

MODULES = [
    "custom_components.nefit_easy",
    "custom_components.nefit_easy.config_flow",
    "custom_components.nefit_easy.coordinator",
    "custom_components.nefit_easy.entity",
    "custom_components.nefit_easy.climate",
    "custom_components.nefit_easy.sensor",
    "custom_components.nefit_easy.api",
    "custom_components.nefit_easy.api.client",
    "custom_components.nefit_easy.api.xmpp",
    "custom_components.nefit_easy.api.crypto",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports(module: str) -> None:
    importlib.import_module(module)
