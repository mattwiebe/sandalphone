import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.livekit_outbound import (
    OutboundSessionStatus,
    build_outbound_session,
    validate_outbound_dial_request,
)
from pipecat_app.livekit_room import RoomRole
from pipecat_app.runtime import SessionState


@pytest.mark.integration
def test_outbound_session_tracks_busy_and_cancel_states() -> None:
    request = validate_outbound_dial_request(
        {
            "request_id": "req-1",
            "trusted_identity": "trusted-1",
            "destination_number": "+15550000002",
            "source_number": "+15105550100",
        }
    )

    session = build_outbound_session(request)
    assert session.controller.identity_for(RoomRole.TRUSTED_LISTENER) == "trusted-1"
    assert session.controller.state is SessionState.CONNECTING

    session.mark_busy()
    assert session.status is OutboundSessionStatus.BUSY

    session.mark_canceled()
    assert session.status is OutboundSessionStatus.CANCELED
