import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.livekit_room import RoomRole
from pipecat_app.livekit_sip import (
    InboundCallContext,
    InboundSipConfig,
    create_inbound_session,
    parse_inbound_call_context,
    parse_inbound_sip_config,
)


@pytest.mark.contract
def test_parse_inbound_sip_config_keeps_provider_at_the_edge() -> None:
    config = parse_inbound_sip_config(
        {
            "provider": "twilio",
            "trunk_id": "trunk-1",
            "dispatch_rule_id": "rule-1",
            "numbers": ["+15105550100"],
            "headers_to_attributes": {"X-Account": "account_id"},
        }
    )

    assert config == InboundSipConfig(
        provider="twilio",
        trunk_id="trunk-1",
        dispatch_rule_id="rule-1",
        numbers=("+15105550100",),
        headers_to_attributes={"X-Account": "account_id"},
    )


@pytest.mark.contract
def test_parse_inbound_call_context_maps_livekit_sip_attributes() -> None:
    context = parse_inbound_call_context(
        participant_identity="sip-participant-1",
        attributes={
            "sip.callID": "call-1",
            "sip.callIDFull": "provider-call-1",
            "sip.callStatus": "ringing",
            "sip.phoneNumber": "+15550000001",
            "sip.ruleID": "rule-1",
            "sip.trunkID": "trunk-1",
            "sip.trunkPhoneNumber": "+15105550100",
            "account_id": "acct-123",
        },
    )

    assert context == InboundCallContext(
        participant_identity="sip-participant-1",
        call_id="call-1",
        provider_call_id="provider-call-1",
        call_status="ringing",
        from_number="+15550000001",
        to_number="+15105550100",
        trunk_id="trunk-1",
        dispatch_rule_id="rule-1",
        custom_attributes={"account_id": "acct-123"},
    )


@pytest.mark.contract
def test_create_inbound_session_defaults_to_private_translation() -> None:
    context = InboundCallContext(
        participant_identity="sip-participant-1",
        call_id="call-1",
        provider_call_id="provider-call-1",
        call_status="ringing",
        from_number="+15550000001",
        to_number="+15105550100",
        trunk_id="trunk-1",
        dispatch_rule_id="rule-1",
        custom_attributes={},
    )

    session = create_inbound_session(context)

    assert session.room_name == "call-call-1"
    assert session.private_translation is True
    assert session.participants[RoomRole.CALLER].identity == "sip-participant-1"
