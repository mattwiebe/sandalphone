import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.livekit_room import RoomRole
from pipecat_app.livekit_sip import create_inbound_session, parse_inbound_call_context


@pytest.mark.integration
def test_inbound_session_creation_reuses_livekit_room_model() -> None:
    context = parse_inbound_call_context(
        participant_identity="sip-participant-1",
        attributes={
            "sip.callID": "call-44",
            "sip.callIDFull": "provider-call-44",
            "sip.callStatus": "active",
            "sip.phoneNumber": "+15550000044",
            "sip.ruleID": "rule-1",
            "sip.trunkID": "trunk-1",
            "sip.trunkPhoneNumber": "+15105550100",
        },
    )

    session = create_inbound_session(context)

    assert session.controller.identity_for(RoomRole.CALLER) == "sip-participant-1"
    assert session.controller.identity_for(RoomRole.BOT) == "bot-call-44"
    assert session.controller.state.value == "connecting"
