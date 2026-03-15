from dataclasses import dataclass
from enum import Enum
from importlib.util import find_spec
from typing import Iterable, Literal


class SessionState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    ACTIVE = "active"
    DEGRADED = "degraded"
    ENDED = "ended"


class AudioSource(Enum):
    CALL = "call"
    AMBIENT = "ambient"


ParticipantRole = Literal["caller", "trusted_listener", "assistant", "ambient_source"]
PublicationKind = Literal["metadata", "audio"]


class PipecatDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Participant:
    participant_id: str
    role: ParticipantRole


@dataclass(frozen=True)
class TrackPublication:
    publication_kind: PublicationKind
    track_name: str
    allowed_participant_ids: tuple[str, ...]
    payload: object
    audio_source: AudioSource


class PipecatRuntimeFactory:
    def ensure_dependency(self) -> None:
        if find_spec("pipecat") is None:
            raise PipecatDependencyError(
                "pipecat-ai is not available in the current Python 3.13 environment"
            )


class PrivateTranslationRuntime:
    def __init__(self, streaming_translator) -> None:
        self.streaming_translator = streaming_translator
        self.state = SessionState.IDLE

    def start_session(self) -> None:
        self.state = SessionState.CONNECTING

    def mark_active(self) -> None:
        self.state = SessionState.ACTIVE

    def mark_degraded(self) -> None:
        self.state = SessionState.DEGRADED

    def end_session(self) -> None:
        self.state = SessionState.ENDED

    def translate_for_listener(
        self,
        audio_source: AudioSource,
        input_audio: str,
        source_lang: str,
        target_lang: str,
        speaker: Participant,
        listener: Participant,
        streaming_interval: float = 2.0,
    ) -> Iterable[TrackPublication]:
        if listener.role != "trusted_listener":
            raise ValueError("private translation requires a trusted listener")

        for event in self.streaming_translator.translate_audio_streaming(
            input_audio=input_audio,
            source_lang=source_lang,
            target_lang=target_lang,
            streaming_interval=streaming_interval,
        ):
            if event["type"] == "metadata":
                yield TrackPublication(
                    publication_kind="metadata",
                    track_name="private_translation_metadata",
                    allowed_participant_ids=(listener.participant_id,),
                    payload={
                        "speaker": speaker.role,
                        "transcription": event["transcription"],
                        "translation": event["translation"],
                    },
                    audio_source=audio_source,
                )
            elif event["type"] == "audio_chunk":
                yield TrackPublication(
                    publication_kind="audio",
                    track_name="private_translation",
                    allowed_participant_ids=(listener.participant_id,),
                    payload=event["data"],
                    audio_source=audio_source,
                )
            else:
                raise ValueError(f"unexpected event type: {event['type']}")
