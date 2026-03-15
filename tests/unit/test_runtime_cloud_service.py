import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime-cloud" / "src"))

from runtime_cloud_service.app import app
from runtime_cloud_service.config import RuntimeCloudConfig
from runtime_cloud_service.tokens import issue_trusted_leg_token


@pytest.mark.unit
def test_issue_trusted_leg_token_returns_jwt() -> None:
    token = issue_trusted_leg_token(
        config=RuntimeCloudConfig(
            livekit_url="wss://example.livekit.cloud",
            livekit_api_key="key",
            livekit_api_secret="secret",
        ),
        room_name="call-123",
        identity="trusted-1",
    )

    assert isinstance(token, str)
    assert token.count(".") == 2


@pytest.mark.unit
def test_trusted_credentials_endpoint_returns_livekit_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIVEKIT_URL", "wss://example.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "secret")

    client = TestClient(app)
    response = client.post(
        "/trusted/credentials",
        json={"room_name": "call-main", "identity": "trusted-matt"},
    )

    assert response.status_code == 200
    assert response.json()["serverUrl"] == "wss://example.livekit.cloud"
    assert response.json()["participantName"] == "trusted-matt"
    assert response.json()["roomName"] == "call-main"
    assert response.json()["participantToken"].count(".") == 2
