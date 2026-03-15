import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mac" / "src"))

from levi_pipeline.models import TranslationResult
from streaming_translation_service import StreamingTranslationService
from translation_service import TranslationService


class _FakeSpeechToText:
    def transcribe(self, audio_file, language=None) -> str:
        return "hello"


class _FakeTranslator:
    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        return "hola"


class _FakeSpeechSynthesizer:
    def synthesize(self, text, output_file=None, language="en") -> Path:
        return Path(output_file or "/tmp/out.wav")


class _FakeStreamingSpeechSynthesizer(_FakeSpeechSynthesizer):
    def synthesize_streaming(self, text, language="en", streaming_interval=2.0):
        yield b"chunk-1"
        yield b"chunk-2"


@pytest.mark.unit
def test_translation_service_returns_translation_result() -> None:
    service = TranslationService(
        stt=_FakeSpeechToText(),
        translator=_FakeTranslator(),
        tts=_FakeSpeechSynthesizer(),
    )

    result = service.translate_audio(
        input_audio="/tmp/in.wav",
        source_lang="en",
        target_lang="es",
        output_audio="/tmp/out.wav",
    )

    assert result == TranslationResult(
        transcription="hello",
        translation="hola",
        output_audio=Path("/tmp/out.wav"),
    )


@pytest.mark.unit
def test_streaming_translation_service_returns_legacy_dict_shape() -> None:
    service = StreamingTranslationService(
        stt=_FakeSpeechToText(),
        translator=_FakeTranslator(),
        tts=_FakeStreamingSpeechSynthesizer(),
    )

    results = list(
        service.translate_audio_streaming(
            input_audio="/tmp/in.wav",
            source_lang="en",
            target_lang="es",
            streaming_interval=1.5,
        )
    )

    assert results == [
        {
            "type": "metadata",
            "transcription": "hello",
            "translation": "hola",
        },
        {
            "type": "audio_chunk",
            "data": b"chunk-1",
            "chunk_index": 0,
        },
        {
            "type": "audio_chunk",
            "data": b"chunk-2",
            "chunk_index": 1,
        },
    ]
