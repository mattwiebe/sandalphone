from pathlib import Path
from typing import Generator, Protocol, runtime_checkable


@runtime_checkable
class SpeechToText(Protocol):
    def transcribe(self, audio_file: str | Path, language: str | None = None) -> str:
        """Transcribe input audio into text."""


@runtime_checkable
class Translator(Protocol):
    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        """Translate text between supported languages."""


@runtime_checkable
class SpeechSynthesizer(Protocol):
    def synthesize(
        self,
        text: str,
        output_file: str | Path | None = None,
        language: str = "en",
    ) -> Path:
        """Synthesize speech and return the output audio path."""


@runtime_checkable
class StreamingSpeechSynthesizer(SpeechSynthesizer, Protocol):
    def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
        streaming_interval: float = 2.0,
    ) -> Generator[bytes, None, None]:
        """Yield synthesized audio chunks."""
