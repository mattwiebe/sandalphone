import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.operability import (
    AppConfig,
    ConfigValidationError,
    HealthReport,
    MetricsCollector,
    StructuredEventLogger,
    validate_config,
)


@pytest.mark.unit
def test_validate_config_fails_fast_for_missing_livekit_url() -> None:
    with pytest.raises(ConfigValidationError, match="livekit_url"):
        validate_config(
            AppConfig(
                livekit_url="",
                api_key="key",
                api_secret="secret",
            )
        )


@pytest.mark.unit
def test_structured_logger_emits_machine_readable_event() -> None:
    logger = StructuredEventLogger()

    event = logger.log("session.started", session_id="sess-1", room_name="room-1")

    assert event == {
        "event": "session.started",
        "session_id": "sess-1",
        "room_name": "room-1",
    }


@pytest.mark.unit
def test_metrics_collector_counts_stage_latency_and_errors() -> None:
    metrics = MetricsCollector()

    metrics.record_latency("translation_ms", 123.0)
    metrics.increment_error("transport_errors")

    assert metrics.counters["transport_errors"] == 1
    assert metrics.latencies["translation_ms"] == [123.0]


@pytest.mark.unit
def test_health_report_reflects_runtime_readiness() -> None:
    report = HealthReport(
        status="healthy",
        checks={"livekit": "ready", "pipecat": "ready"},
    )

    assert report.to_dict() == {
        "status": "healthy",
        "checks": {"livekit": "ready", "pipecat": "ready"},
    }
