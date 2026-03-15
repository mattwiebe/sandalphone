from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from livekit import api


@dataclass(frozen=True)
class TwilioTerminationAuth:
    username: str
    password: str


@dataclass(frozen=True)
class LiveKitSipPlan:
    inbound_trunk_name: str
    outbound_trunk_name: str
    dispatch_rule_name: str
    inbound_phone_number: str
    room_name: str
    twilio_outbound_domain: str
    twilio_auth_username: str
    twilio_auth_password: str


@dataclass(frozen=True)
class TelephonyPlan:
    livekit: LiveKitSipPlan
    twilio_trunk_friendly_name: str
    twilio_domain_name: str
    twilio_origination_uri: str
    twilio_phone_number: str
    twilio_auth: TwilioTerminationAuth


def build_livekit_sip_uri(livekit_url: str) -> str:
    host = urlparse(livekit_url).hostname
    if not host:
        raise ValueError("LiveKit URL must include a hostname")
    project_slug = host.removesuffix(".livekit.cloud")
    return f"sip:{project_slug}.sip.livekit.cloud"


def build_trunk_domain_name(trunk_stem: str) -> str:
    if trunk_stem.endswith(".pstn.twilio.com"):
        return trunk_stem
    return f"{trunk_stem}.pstn.twilio.com"


def build_telephony_plan(
    *,
    trunk_stem: str,
    phone_number: str,
    livekit_url: str,
    room_name: str,
    twilio_auth: TwilioTerminationAuth,
) -> TelephonyPlan:
    domain_name = build_trunk_domain_name(trunk_stem)
    return TelephonyPlan(
        livekit=LiveKitSipPlan(
            inbound_trunk_name=f"{trunk_stem}-inbound",
            outbound_trunk_name=f"{trunk_stem}-outbound",
            dispatch_rule_name=f"{trunk_stem}-dispatch",
            inbound_phone_number=phone_number,
            room_name=room_name,
            twilio_outbound_domain=domain_name,
            twilio_auth_username=twilio_auth.username,
            twilio_auth_password=twilio_auth.password,
        ),
        twilio_trunk_friendly_name=trunk_stem,
        twilio_domain_name=domain_name,
        twilio_origination_uri=build_livekit_sip_uri(livekit_url),
        twilio_phone_number=phone_number,
        twilio_auth=twilio_auth,
    )


def build_livekit_inbound_trunk_request(
    plan: LiveKitSipPlan,
) -> api.CreateSIPInboundTrunkRequest:
    return api.CreateSIPInboundTrunkRequest(
        trunk=api.SIPInboundTrunkInfo(
            name=plan.inbound_trunk_name,
            numbers=[plan.inbound_phone_number],
        )
    )


def build_livekit_dispatch_request(
    plan: LiveKitSipPlan,
    *,
    trunk_id: str,
) -> api.CreateSIPDispatchRuleRequest:
    return api.CreateSIPDispatchRuleRequest(
        name=plan.dispatch_rule_name,
        trunk_ids=[trunk_id],
        rule=api.SIPDispatchRule(
            dispatch_rule_direct=api.SIPDispatchRuleDirect(room_name=plan.room_name),
        ),
    )


def build_livekit_outbound_trunk_request(
    plan: LiveKitSipPlan,
) -> api.CreateSIPOutboundTrunkRequest:
    return api.CreateSIPOutboundTrunkRequest(
        trunk=api.SIPOutboundTrunkInfo(
            name=plan.outbound_trunk_name,
            address=plan.twilio_outbound_domain,
            transport=api.SIP_TRANSPORT_TLS,
            numbers=[plan.inbound_phone_number],
            auth_username=plan.twilio_auth_username,
            auth_password=plan.twilio_auth_password,
        )
    )
