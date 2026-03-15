from dataclasses import dataclass
from enum import Enum

from .runtime import SessionState


class AudioMode(Enum):
    CALL = "call"
    AMBIENT = "ambient"


@dataclass(frozen=True)
class AudioPolicyConfig:
    mode: AudioMode = AudioMode.CALL
    relay_translation: bool = False
    duck_original_audio: bool = False
    stereo_split: bool = False


@dataclass(frozen=True)
class MixPlan:
    private_translation: bool
    relay_translation: bool
    duck_original_audio: bool
    stereo_split: bool


class AudioPolicy:
    def __init__(self, config: AudioPolicyConfig) -> None:
        self._config = config
        self.mode = config.mode
        self.session_state = SessionState.IDLE

    def start_session(self) -> None:
        self.session_state = SessionState.ACTIVE

    def set_mode(self, mode: AudioMode) -> None:
        self.mode = mode
        if self.session_state is SessionState.IDLE:
            self.session_state = SessionState.CONNECTING

    def build_mix_plan(self) -> MixPlan:
        return MixPlan(
            private_translation=True,
            relay_translation=self._config.relay_translation,
            duck_original_audio=self._config.duck_original_audio,
            stereo_split=self._config.stereo_split,
        )
