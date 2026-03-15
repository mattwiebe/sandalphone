import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mac" / "src"))

from levi_pipeline.profiling import BenchmarkCase, ProviderProfiler


class _FakeTranslator:
    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        return f"{text}:{source_lang}->{target_lang}"


class _FakeSpeechSynthesizer:
    def synthesize(self, text, output_file=None, language="en") -> Path:
        output_path = Path(output_file or "/tmp/fake.wav")
        output_path.write_bytes(text.encode("utf-8"))
        return output_path


@pytest.mark.unit
def test_profiler_records_translation_provider_result(tmp_path: Path) -> None:
    profiler = ProviderProfiler()
    case = BenchmarkCase(
        provider_kind="translation",
        provider_name="fake-translator",
        input_payload="hola",
        source_lang="es",
        target_lang="en",
    )

    result = profiler.profile_translation(_FakeTranslator(), case)

    assert result.provider_name == "fake-translator"
    assert result.success is True
    assert result.output_payload == "hola:es->en"
    assert result.latency_ms >= 0


@pytest.mark.unit
def test_profiler_records_tts_provider_result(tmp_path: Path) -> None:
    profiler = ProviderProfiler()
    case = BenchmarkCase(
        provider_kind="tts",
        provider_name="fake-tts",
        input_payload="hello",
        source_lang="en",
        target_lang="en",
        output_path=tmp_path / "tts.wav",
    )

    result = profiler.profile_tts(_FakeSpeechSynthesizer(), case)

    assert result.provider_name == "fake-tts"
    assert result.success is True
    assert result.output_path == tmp_path / "tts.wav"
    assert result.output_size_bytes == len(b"hello")
