from dataclasses import dataclass

from .livekit_room import LiveKitParticipant, LiveKitSessionController, RoomRole


_LIVEKIT_SIP_ATTRIBUTE_KEYS = {
    "sip.callID",
    "sip.callIDFull",
    "sip.callStatus",
    "sip.phoneNumber",
    "sip.ruleID",
    "sip.trunkID",
    "sip.trunkPhoneNumber",
}


@dataclass(frozen=True)
class InboundSipConfig:
    provider: str
    trunk_id: str
    dispatch_rule_id: str
    numbers: tuple[str, ...]
    headers_to_attributes: dict[str, str]


@dataclass(frozen=True)
class InboundCallContext:
    participant_identity: str
    call_id: str
    provider_call_id: str
    call_status: str
    from_number: str
    to_number: str
    trunk_id: str
    dispatch_rule_id: str
    custom_attributes: dict[str, str]


@dataclass(frozen=True)
class InboundSession:
    room_name: str
    private_translation: bool
    participants: dict[RoomRole, LiveKitParticipant]
    controller: LiveKitSessionController


def parse_inbound_sip_config(config: dict[str, object]) -> InboundSipConfig:
    return InboundSipConfig(
        provider=str(config["provider"]),
        trunk_id=str(config["trunk_id"]),
        dispatch_rule_id=str(config["dispatch_rule_id"]),
        numbers=tuple(config.get("numbers", [])),
        headers_to_attributes=dict(config.get("headers_to_attributes", {})),
    )


def parse_inbound_call_context(
    participant_identity: str,
    attributes: dict[str, str],
) -> InboundCallContext:
    custom_attributes = {
        key: value for key, value in attributes.items() if key not in _LIVEKIT_SIP_ATTRIBUTE_KEYS
    }

    return InboundCallContext(
        participant_identity=participant_identity,
        call_id=attributes["sip.callID"],
        provider_call_id=attributes["sip.callIDFull"],
        call_status=attributes["sip.callStatus"],
        from_number=attributes["sip.phoneNumber"],
        to_number=attributes["sip.trunkPhoneNumber"],
        trunk_id=attributes["sip.trunkID"],
        dispatch_rule_id=attributes["sip.ruleID"],
        custom_attributes=custom_attributes,
    )


def create_inbound_session(context: InboundCallContext) -> InboundSession:
    room_name = f"call-{context.call_id}"
    controller = LiveKitSessionController(room_name=room_name)

    participants = {
        RoomRole.CALLER: LiveKitParticipant(
            identity=context.participant_identity,
            role=RoomRole.CALLER,
        ),
        RoomRole.BOT: LiveKitParticipant(
            identity=f"bot-{context.call_id}",
            role=RoomRole.BOT,
        ),
    }

    controller.attach(participants[RoomRole.CALLER])
    controller.attach(participants[RoomRole.BOT])

    return InboundSession(
        room_name=room_name,
        private_translation=True,
        participants=participants,
        controller=controller,
    )
