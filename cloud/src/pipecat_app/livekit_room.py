from dataclasses import dataclass
from enum import Enum

from livekit import rtc

from .runtime import SessionState


class RoomRole(Enum):
    CALLER = "caller"
    TRUSTED_LISTENER = "trusted_listener"
    BOT = "bot"


@dataclass(frozen=True)
class LiveKitParticipant:
    identity: str
    role: RoomRole


class LiveKitRoomPolicy:
    def __init__(self, room_name: str) -> None:
        self.room_name = room_name

    def private_translation_permissions(
        self, trusted_listener: LiveKitParticipant
    ) -> list[rtc.ParticipantTrackPermission]:
        permission = rtc.ParticipantTrackPermission()
        permission.participant_identity = trusted_listener.identity
        permission.allow_all = True
        return [permission]

    def translation_publish_options(self) -> rtc.TrackPublishOptions:
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        return options


class LiveKitSessionController:
    def __init__(self, room_name: str) -> None:
        self.room_name = room_name
        self.state = SessionState.IDLE
        self._participants_by_role: dict[RoomRole, LiveKitParticipant] = {}

    def attach(self, participant: LiveKitParticipant) -> None:
        self._participants_by_role[participant.role] = participant
        self._recompute_state()

    def handle_disconnect(self, role: RoomRole) -> None:
        self._participants_by_role.pop(role, None)
        if self.state is not SessionState.ENDED:
            self.state = SessionState.DEGRADED

    def identity_for(self, role: RoomRole) -> str | None:
        participant = self._participants_by_role.get(role)
        return participant.identity if participant else None

    def _recompute_state(self) -> None:
        required = {
            RoomRole.CALLER,
            RoomRole.TRUSTED_LISTENER,
            RoomRole.BOT,
        }
        attached = set(self._participants_by_role)

        if required.issubset(attached):
            self.state = SessionState.ACTIVE
            return

        if attached:
            self.state = SessionState.CONNECTING
            return

        self.state = SessionState.IDLE
