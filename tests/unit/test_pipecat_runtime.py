import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.runtime import (
    AudioSource,
    Participant,
    PipecatDependencyError,
    PipecatRuntimeFactory,
    PrivateTranslationRuntime,
    SessionState,
)


class _FakeStreamingTranslator:
    def translate_audio_streaming(
        self,
        input_audio,
        source_lang="es",
        target_lang="en",
        streaming_interval=2.0,
    ):
        yield {"type": "metadata", "transcription": "hello", "translation": "hola"}
        yield {"type": "audio_chunk", "data": b"chunk-1", "chunk_index": 0}
        yield {"type": "audio_chunk", "data": b"chunk-2", "chunk_index": 1}


@pytest.mark.unit
def test_runtime_tracks_session_state_transitions() -> None:
    runtime = PrivateTranslationRuntime(streaming_translator=_FakeStreamingTranslator())

    assert runtime.state is SessionState.IDLE

    runtime.start_session()
    assert runtime.state is SessionState.CONNECTING

    runtime.mark_active()
    assert runtime.state is SessionState.ACTIVE

    runtime.mark_degraded()
    assert runtime.state is SessionState.DEGRADED

    runtime.end_session()
    assert runtime.state is SessionState.ENDED


@pytest.mark.unit
def test_runtime_enforces_private_publication_to_trusted_listener() -> None:
    runtime = PrivateTranslationRuntime(streaming_translator=_FakeStreamingTranslator())
    caller = Participant(participant_id="caller-1", role="caller")
    trusted = Participant(participant_id="trusted-1", role="trusted_listener")

    publications = list(
        runtime.translate_for_listener(
            audio_source=AudioSource.CALL,
            input_audio="/tmp/in.wav",
            source_lang="en",
            target_lang="es",
            speaker=caller,
            listener=trusted,
        )
    )

    assert publications[0].publication_kind == "metadata"
    assert publications[0].allowed_participant_ids == ("trusted-1",)
    assert publications[1].track_name == "private_translation"
    assert publications[1].allowed_participant_ids == ("trusted-1",)
    assert publications[1].payload == b"chunk-1"


@pytest.mark.unit
def test_runtime_factory_raises_clear_error_when_pipecat_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipecat_app.runtime.find_spec", lambda _: None)

    with pytest.raises(PipecatDependencyError, match="pipecat-ai"):
        PipecatRuntimeFactory().ensure_dependency()
