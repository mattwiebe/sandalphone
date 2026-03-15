import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.operability import AppConfig, build_health_report


@pytest.mark.integration
def test_health_report_marks_missing_secret_as_degraded() -> None:
    report = build_health_report(
        AppConfig(
            livekit_url="wss://example.livekit.cloud",
            api_key="key",
            api_secret="",
        )
    )

    assert report.status == "degraded"
    assert report.checks["api_secret"] == "missing"
