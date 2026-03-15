from dataclasses import dataclass
from typing import Literal


EventSource = Literal["system", "stt", "assistant", "user", "transport"]
SessionMode = Literal["call", "ambient"]
SpeakerRole = Literal["caller", "trusted_user", "assistant", "ambient"]


@dataclass(frozen=True)
class SessionStartedEvent:
    session_id: str
    mode: SessionMode
    source: EventSource = "system"

    def to_envelope(self) -> dict[str, object]:
        return {
            "type": "session.started",
            "source": self.source,
            "payload": {
                "session_id": self.session_id,
                "mode": self.mode,
            },
        }


@dataclass(frozen=True)
class SessionEndedEvent:
    session_id: str
    reason: str
    source: EventSource = "system"

    def to_envelope(self) -> dict[str, object]:
        return {
            "type": "session.ended",
            "source": self.source,
            "payload": {
                "session_id": self.session_id,
                "reason": self.reason,
            },
        }


@dataclass(frozen=True)
class TranscriptPartialEvent:
    session_id: str
    speaker: SpeakerRole
    text: str
    source: EventSource = "stt"

    def to_envelope(self) -> dict[str, object]:
        return {
            "type": "transcript.partial",
            "source": self.source,
            "payload": {
                "session_id": self.session_id,
                "speaker": self.speaker,
                "text": self.text,
            },
        }


@dataclass(frozen=True)
class TranscriptFinalEvent:
    session_id: str
    speaker: SpeakerRole
    text: str
    source: EventSource = "stt"

    def to_envelope(self) -> dict[str, object]:
        return {
            "type": "transcript.final",
            "source": self.source,
            "payload": {
                "session_id": self.session_id,
                "speaker": self.speaker,
                "text": self.text,
            },
        }


@dataclass(frozen=True)
class TaskCreateEvent:
    session_id: str
    title: str
    description: str
    source: EventSource = "assistant"

    def to_envelope(self) -> dict[str, object]:
        return {
            "type": "task.create",
            "source": self.source,
            "payload": {
                "session_id": self.session_id,
                "title": self.title,
                "description": self.description,
            },
        }
