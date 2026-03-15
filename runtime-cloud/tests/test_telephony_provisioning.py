from livekit import api

from runtime_cloud_service.telephony_provisioning import (
    LiveKitSipPlan,
    TelephonyPlan,
    TwilioTerminationAuth,
    build_livekit_sip_uri,
    build_livekit_dispatch_request,
    build_livekit_inbound_trunk_request,
    build_livekit_outbound_trunk_request,
    build_telephony_plan,
    build_trunk_domain_name,
)


def test_build_livekit_sip_uri_uses_project_slug() -> None:
    assert (
        build_livekit_sip_uri("wss://ophaniel-ipch23c5.livekit.cloud")
        == "sip:ophaniel-ipch23c5.sip.livekit.cloud"
    )


def test_build_trunk_domain_name_normalizes_suffix() -> None:
    assert build_trunk_domain_name("levi-main") == "levi-main.pstn.twilio.com"
    assert (
        build_trunk_domain_name("levi-main.pstn.twilio.com")
        == "levi-main.pstn.twilio.com"
    )


def test_build_telephony_plan_creates_direct_room_dispatch() -> None:
    plan = build_telephony_plan(
        trunk_stem="levi-main",
        phone_number="+523223080230",
        livekit_url="wss://ophaniel-ipch23c5.livekit.cloud",
        room_name="call-main",
        twilio_auth=TwilioTerminationAuth(
            username="levi-outbound",
            password="secret-value",
        ),
    )

    assert plan == TelephonyPlan(
        livekit=LiveKitSipPlan(
            inbound_trunk_name="levi-main-inbound",
            outbound_trunk_name="levi-main-outbound",
            dispatch_rule_name="levi-main-dispatch",
            inbound_phone_number="+523223080230",
            room_name="call-main",
            twilio_outbound_domain="levi-main.pstn.twilio.com",
            twilio_auth_username="levi-outbound",
            twilio_auth_password="secret-value",
        ),
        twilio_trunk_friendly_name="levi-main",
        twilio_domain_name="levi-main.pstn.twilio.com",
        twilio_origination_uri="sip:ophaniel-ipch23c5.sip.livekit.cloud",
        twilio_phone_number="+523223080230",
        twilio_auth=TwilioTerminationAuth(
            username="levi-outbound",
            password="secret-value",
        ),
    )


def test_build_livekit_inbound_trunk_request_uses_phone_number() -> None:
    request = build_livekit_inbound_trunk_request(
        LiveKitSipPlan(
            inbound_trunk_name="levi-main-inbound",
            outbound_trunk_name="levi-main-outbound",
            dispatch_rule_name="levi-main-dispatch",
            inbound_phone_number="+523223080230",
            room_name="call-main",
            twilio_outbound_domain="levi-main.pstn.twilio.com",
            twilio_auth_username="levi-outbound",
            twilio_auth_password="secret-value",
        )
    )

    assert request.trunk.name == "levi-main-inbound"
    assert list(request.trunk.numbers) == ["+523223080230"]


def test_build_livekit_dispatch_request_targets_a_direct_room() -> None:
    request = build_livekit_dispatch_request(
        LiveKitSipPlan(
            inbound_trunk_name="levi-main-inbound",
            outbound_trunk_name="levi-main-outbound",
            dispatch_rule_name="levi-main-dispatch",
            inbound_phone_number="+523223080230",
            room_name="call-main",
            twilio_outbound_domain="levi-main.pstn.twilio.com",
            twilio_auth_username="levi-outbound",
            twilio_auth_password="secret-value",
        ),
        trunk_id="ST_livekit_inbound",
    )

    assert request.name == "levi-main-dispatch"
    assert list(request.trunk_ids) == ["ST_livekit_inbound"]
    assert request.rule.dispatch_rule_direct.room_name == "call-main"


def test_build_livekit_outbound_trunk_request_targets_twilio_domain() -> None:
    request = build_livekit_outbound_trunk_request(
        LiveKitSipPlan(
            inbound_trunk_name="levi-main-inbound",
            outbound_trunk_name="levi-main-outbound",
            dispatch_rule_name="levi-main-dispatch",
            inbound_phone_number="+523223080230",
            room_name="call-main",
            twilio_outbound_domain="levi-main.pstn.twilio.com",
            twilio_auth_username="levi-outbound",
            twilio_auth_password="secret-value",
        )
    )

    assert request.trunk.name == "levi-main-outbound"
    assert request.trunk.address == "levi-main.pstn.twilio.com"
    assert request.trunk.transport == api.SIP_TRANSPORT_TLS
    assert request.trunk.auth_username == "levi-outbound"
    assert request.trunk.auth_password == "secret-value"
