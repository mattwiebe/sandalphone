import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.livekit_outbound import (
    OutboundDialRequest,
    OutboundSession,
    OutboundSessionStatus,
    build_outbound_session,
    validate_outbound_dial_request,
)
from pipecat_app.livekit_room import RoomRole


@pytest.mark.contract
def test_validate_outbound_dial_request_rejects_missing_e164_numbers() -> None:
    with pytest.raises(ValueError, match="destination_number"):
        validate_outbound_dial_request(
            {
                "request_id": "req-1",
                "trusted_identity": "trusted-1",
                "destination_number": "5550100",
                "source_number": "+15105550100",
            }
        )


@pytest.mark.contract
def test_build_outbound_session_uses_same_room_model_as_inbound() -> None:
    request = OutboundDialRequest(
        request_id="req-1",
        trusted_identity="trusted-1",
        destination_number="+15550000002",
        source_number="+15105550100",
    )

    session = build_outbound_session(request)

    assert isinstance(session, OutboundSession)
    assert session.room_name == "outbound-req-1"
    assert session.participants[RoomRole.TRUSTED_LISTENER].identity == "trusted-1"
    assert session.participants[RoomRole.BOT].identity == "bot-req-1"
    assert session.status is OutboundSessionStatus.DIALING
