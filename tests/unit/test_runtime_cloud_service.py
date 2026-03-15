import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime-cloud" / "src"))

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
