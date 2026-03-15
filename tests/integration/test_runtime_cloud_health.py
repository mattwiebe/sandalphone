import sys
from pathlib import Path

from fastapi.testclient import TestClient
import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime-cloud" / "src"))

from runtime_cloud_service.app import app


@pytest.mark.integration
def test_runtime_cloud_health_reports_missing_livekit_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVEKIT_URL", raising=False)
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@pytest.mark.integration
def test_trusted_page_is_served() -> None:
    client = TestClient(app)
    response = client.get("/trusted")

    assert response.status_code == 200
    assert "Trusted Leg" in response.text
    assert "livekit-client.umd.min.js" in response.text
