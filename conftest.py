import os
from typing import Final

import pytest


_TRUTHY: Final = {"1", "true", "yes", "on"}


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in _TRUTHY


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_integration = _env_flag("RUN_INTEGRATION_TESTS")
    run_hardware = _env_flag("RUN_HARDWARE_TESTS")

    skip_integration = pytest.mark.skip(
        reason="integration test; set RUN_INTEGRATION_TESTS=1 to enable"
    )
    skip_hardware = pytest.mark.skip(
        reason="hardware test; set RUN_HARDWARE_TESTS=1 to enable"
    )

    for item in items:
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)
        if "hardware" in item.keywords and not run_hardware:
            item.add_marker(skip_hardware)
