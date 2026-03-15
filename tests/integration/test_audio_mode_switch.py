import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.audio_policy import AudioMode, AudioPolicy, AudioPolicyConfig
from pipecat_app.runtime import SessionState


@pytest.mark.integration
def test_mode_switch_updates_audio_mode_without_ending_session() -> None:
    policy = AudioPolicy(AudioPolicyConfig(mode=AudioMode.CALL))
    policy.start_session()

    policy.set_mode(AudioMode.AMBIENT)

    assert policy.mode is AudioMode.AMBIENT
    assert policy.session_state is SessionState.ACTIVE
