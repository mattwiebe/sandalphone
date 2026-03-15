import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mac" / "src"))

from levi_pipeline.models import AudioChunkResult, TranslationMetadata, TranslationResult
from levi_pipeline.service import BatchTranslationPipeline, StreamingTranslationPipeline


class _FakeSpeechToText:
    def __init__(self, transcript: str = "hello") -> None:
        self.transcript = transcript
        self.calls = []

    def transcribe(self, audio_file, language=None) -> str:
        self.calls.append((audio_file, language))
        return self.transcript


class _FakeTranslator:
    def __init__(self, translation: str = "hola") -> None:
        self.translation = translation
        self.calls = []

    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        self.calls.append((text, source_lang, target_lang))
        return self.translation


class _FakeSpeechSynthesizer:
    def __init__(self) -> None:
        self.calls = []

    def synthesize(self, text, output_file=None, language="en") -> Path:
        self.calls.append((text, output_file, language))
        return Path(output_file or "/tmp/fake-output.wav")


class _FakeStreamingSpeechSynthesizer(_FakeSpeechSynthesizer):
    def synthesize_streaming(self, text, language="en", streaming_interval=2.0):
        self.calls.append((text, None, language, streaming_interval))
        yield b"chunk-1"
        yield b"chunk-2"


@pytest.mark.contract
def test_batch_pipeline_returns_typed_result() -> None:
    stt = _FakeSpeechToText(transcript="how are you")
    translator = _FakeTranslator(translation="como estas")
    tts = _FakeSpeechSynthesizer()
    pipeline = BatchTranslationPipeline(stt=stt, translator=translator, tts=tts)

    result = pipeline.translate(
        input_audio="/tmp/in.wav",
        source_lang="en",
        target_lang="es",
        output_audio="/tmp/out.wav",
    )

    assert isinstance(result, TranslationResult)
    assert result.transcription == "how are you"
    assert result.translation == "como estas"
    assert result.output_audio == Path("/tmp/out.wav")
    assert result.to_dict() == {
        "transcription": "how are you",
        "translation": "como estas",
        "output_audio": "/tmp/out.wav",
    }


@pytest.mark.contract
def test_streaming_pipeline_emits_metadata_then_audio_chunks() -> None:
    pipeline = StreamingTranslationPipeline(
        stt=_FakeSpeechToText(transcript="good morning"),
        translator=_FakeTranslator(translation="buenos dias"),
        tts=_FakeStreamingSpeechSynthesizer(),
    )

    events = list(
        pipeline.translate(
            input_audio="/tmp/in.wav",
            source_lang="en",
            target_lang="es",
            streaming_interval=1.5,
        )
    )

    assert isinstance(events[0], TranslationMetadata)
    assert events[0].transcription == "good morning"
    assert events[0].translation == "buenos dias"

    assert events[1:] == [
        AudioChunkResult(data=b"chunk-1", chunk_index=0),
        AudioChunkResult(data=b"chunk-2", chunk_index=1),
    ]


@pytest.mark.contract
def test_streaming_pipeline_falls_back_to_batch_tts_when_streaming_is_unavailable(tmp_path: Path) -> None:
    pipeline = StreamingTranslationPipeline(
        stt=_FakeSpeechToText(transcript="thank you"),
        translator=_FakeTranslator(translation="gracias"),
        tts=_FakeSpeechSynthesizer(),
    )

    output_audio = tmp_path / "batch.wav"
    output_audio.write_bytes(b"batch-audio")

    pipeline.tts.synthesize = lambda text, output_file=None, language="en": output_audio

    events = list(
        pipeline.translate(
            input_audio="/tmp/in.wav",
            source_lang="en",
            target_lang="es",
        )
    )

    assert events[0] == TranslationMetadata(
        transcription="thank you",
        translation="gracias",
    )
    assert events[1] == AudioChunkResult(data=b"batch-audio", chunk_index=0)
