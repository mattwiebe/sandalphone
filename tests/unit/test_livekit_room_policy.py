import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.livekit_room import (
    LiveKitParticipant,
    LiveKitRoomPolicy,
    LiveKitSessionController,
    RoomRole,
)
from pipecat_app.runtime import SessionState


@pytest.mark.unit
def test_livekit_policy_creates_private_translation_permissions_for_trusted_listener() -> None:
    policy = LiveKitRoomPolicy(room_name="room-1")
    trusted = LiveKitParticipant(identity="trusted-1", role=RoomRole.TRUSTED_LISTENER)

    permissions = policy.private_translation_permissions(trusted)

    assert len(permissions) == 1
    assert permissions[0].participant_identity == "trusted-1"
    assert permissions[0].allow_all is True


@pytest.mark.unit
def test_livekit_policy_builds_publish_options_for_microphone_track() -> None:
    policy = LiveKitRoomPolicy(room_name="room-1")

    options = policy.translation_publish_options()

    assert options.source == 2  # TrackSource.SOURCE_MICROPHONE


@pytest.mark.unit
def test_session_controller_maps_identities_by_role() -> None:
    controller = LiveKitSessionController(room_name="room-1")
    caller = LiveKitParticipant(identity="caller-1", role=RoomRole.CALLER)
    trusted = LiveKitParticipant(identity="trusted-1", role=RoomRole.TRUSTED_LISTENER)
    bot = LiveKitParticipant(identity="bot-1", role=RoomRole.BOT)

    controller.attach(caller)
    controller.attach(trusted)
    controller.attach(bot)

    assert controller.identity_for(RoomRole.CALLER) == "caller-1"
    assert controller.identity_for(RoomRole.TRUSTED_LISTENER) == "trusted-1"
    assert controller.identity_for(RoomRole.BOT) == "bot-1"
    assert controller.state is SessionState.ACTIVE
