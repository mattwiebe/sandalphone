import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "cloud" / "src"))

from pipecat_app.runtime import AudioSource, Participant, PrivateTranslationRuntime


class _FakeStreamingTranslator:
    def translate_audio_streaming(
        self,
        input_audio,
        source_lang="es",
        target_lang="en",
        streaming_interval=2.0,
    ):
        yield {"type": "metadata", "transcription": "ambient english", "translation": "ambient spanish"}
        yield {"type": "audio_chunk", "data": b"ambient-1", "chunk_index": 0}


@pytest.mark.integration
def test_local_runtime_harness_supports_ambient_mode_without_changing_pipeline_shape() -> None:
    runtime = PrivateTranslationRuntime(streaming_translator=_FakeStreamingTranslator())
    ambient_speaker = Participant(participant_id="ambient-1", role="ambient_source")
    trusted = Participant(participant_id="trusted-1", role="trusted_listener")

    emissions = list(
        runtime.translate_for_listener(
            audio_source=AudioSource.AMBIENT,
            input_audio="/tmp/ambient.wav",
            source_lang="en",
            target_lang="es",
            speaker=ambient_speaker,
            listener=trusted,
        )
    )

    assert [emission.audio_source for emission in emissions] == [
        AudioSource.AMBIENT,
        AudioSource.AMBIENT,
    ]
    assert all(emission.allowed_participant_ids == ("trusted-1",) for emission in emissions)
