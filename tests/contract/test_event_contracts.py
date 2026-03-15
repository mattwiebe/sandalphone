import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mac" / "src"))

from levi_pipeline.events import (
    SessionEndedEvent,
    SessionStartedEvent,
    TaskCreateEvent,
    TranscriptFinalEvent,
    TranscriptPartialEvent,
)


@pytest.mark.contract
def test_session_events_serialize_to_envelopes() -> None:
    started = SessionStartedEvent(session_id="sess-1", mode="call", source="system")
    ended = SessionEndedEvent(session_id="sess-1", reason="hangup", source="system")

    assert started.to_envelope()["type"] == "session.started"
    assert started.to_envelope()["payload"] == {
        "session_id": "sess-1",
        "mode": "call",
    }

    assert ended.to_envelope()["type"] == "session.ended"
    assert ended.to_envelope()["payload"] == {
        "session_id": "sess-1",
        "reason": "hangup",
    }


@pytest.mark.contract
def test_transcript_events_capture_partial_and_final_text() -> None:
    partial = TranscriptPartialEvent(
        session_id="sess-2",
        speaker="caller",
        text="hol",
        source="stt",
    )
    final = TranscriptFinalEvent(
        session_id="sess-2",
        speaker="caller",
        text="hola",
        source="stt",
    )

    assert partial.to_envelope()["type"] == "transcript.partial"
    assert final.to_envelope()["type"] == "transcript.final"
    assert final.to_envelope()["payload"]["text"] == "hola"


@pytest.mark.contract
def test_task_create_event_has_assistant_hook_shape() -> None:
    event = TaskCreateEvent(
        session_id="sess-3",
        title="Call back vendor",
        description="Follow up about pricing in Spanish",
        source="assistant",
    )

    assert event.to_envelope() == {
        "type": "task.create",
        "source": "assistant",
        "payload": {
            "session_id": "sess-3",
            "title": "Call back vendor",
            "description": "Follow up about pricing in Spanish",
        },
    }
