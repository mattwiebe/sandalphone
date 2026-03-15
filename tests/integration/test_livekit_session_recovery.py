import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.livekit_room import LiveKitParticipant, LiveKitSessionController, RoomRole
from pipecat_app.runtime import SessionState


@pytest.mark.integration
def test_session_recovery_returns_to_active_when_required_roles_rejoin() -> None:
    controller = LiveKitSessionController(room_name="room-1")

    controller.attach(LiveKitParticipant(identity="caller-1", role=RoomRole.CALLER))
    controller.attach(LiveKitParticipant(identity="trusted-1", role=RoomRole.TRUSTED_LISTENER))
    controller.attach(LiveKitParticipant(identity="bot-1", role=RoomRole.BOT))

    controller.handle_disconnect(RoomRole.CALLER)
    assert controller.state is SessionState.DEGRADED

    controller.attach(LiveKitParticipant(identity="caller-1b", role=RoomRole.CALLER))
    assert controller.state is SessionState.ACTIVE


@pytest.mark.integration
def test_session_without_trusted_listener_stays_connecting() -> None:
    controller = LiveKitSessionController(room_name="room-2")

    controller.attach(LiveKitParticipant(identity="caller-1", role=RoomRole.CALLER))
    controller.attach(LiveKitParticipant(identity="bot-1", role=RoomRole.BOT))

    assert controller.state is SessionState.CONNECTING
