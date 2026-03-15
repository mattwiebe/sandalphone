from dataclasses import dataclass
from enum import Enum

from .livekit_room import LiveKitParticipant, LiveKitSessionController, RoomRole


class OutboundSessionStatus(Enum):
    DIALING = "dialing"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    CANCELED = "canceled"
    ACTIVE = "active"
    ENDED = "ended"


@dataclass(frozen=True)
class OutboundDialRequest:
    request_id: str
    trusted_identity: str
    destination_number: str
    source_number: str


@dataclass
class OutboundSession:
    room_name: str
    request: OutboundDialRequest
    participants: dict[RoomRole, LiveKitParticipant]
    controller: LiveKitSessionController
    status: OutboundSessionStatus

    def mark_busy(self) -> None:
        self.status = OutboundSessionStatus.BUSY

    def mark_canceled(self) -> None:
        self.status = OutboundSessionStatus.CANCELED


def validate_outbound_dial_request(payload: dict[str, str]) -> OutboundDialRequest:
    destination_number = payload["destination_number"]
    source_number = payload["source_number"]

    if not destination_number.startswith("+"):
        raise ValueError("destination_number must be E.164")
    if not source_number.startswith("+"):
        raise ValueError("source_number must be E.164")

    return OutboundDialRequest(
        request_id=payload["request_id"],
        trusted_identity=payload["trusted_identity"],
        destination_number=destination_number,
        source_number=source_number,
    )


def build_outbound_session(request: OutboundDialRequest) -> OutboundSession:
    room_name = f"outbound-{request.request_id}"
    controller = LiveKitSessionController(room_name=room_name)
    participants = {
        RoomRole.TRUSTED_LISTENER: LiveKitParticipant(
            identity=request.trusted_identity,
            role=RoomRole.TRUSTED_LISTENER,
        ),
        RoomRole.BOT: LiveKitParticipant(
            identity=f"bot-{request.request_id}",
            role=RoomRole.BOT,
        ),
    }

    controller.attach(participants[RoomRole.TRUSTED_LISTENER])
    controller.attach(participants[RoomRole.BOT])

    return OutboundSession(
        room_name=room_name,
        request=request,
        participants=participants,
        controller=controller,
        status=OutboundSessionStatus.DIALING,
    )
