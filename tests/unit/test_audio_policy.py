import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.audio_policy import AudioPolicy, AudioPolicyConfig, AudioMode


@pytest.mark.unit
def test_private_translation_is_default() -> None:
    policy = AudioPolicy(AudioPolicyConfig())

    decision = policy.build_mix_plan()

    assert decision.private_translation is True
    assert decision.relay_translation is False


@pytest.mark.unit
def test_relay_translation_is_opt_in() -> None:
    policy = AudioPolicy(AudioPolicyConfig(relay_translation=True))

    decision = policy.build_mix_plan()

    assert decision.private_translation is True
    assert decision.relay_translation is True


@pytest.mark.unit
def test_ducking_and_stereo_preferences_are_encoded_in_mix_plan() -> None:
    policy = AudioPolicy(
        AudioPolicyConfig(
            duck_original_audio=True,
            stereo_split=True,
        )
    )

    decision = policy.build_mix_plan()

    assert decision.duck_original_audio is True
    assert decision.stereo_split is True
