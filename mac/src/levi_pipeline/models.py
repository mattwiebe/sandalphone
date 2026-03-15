from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranslationResult:
    transcription: str
    translation: str
    output_audio: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "transcription": self.transcription,
            "translation": self.translation,
            "output_audio": str(self.output_audio),
        }


@dataclass(frozen=True)
class TranslationMetadata:
    transcription: str
    translation: str

    def to_dict(self) -> dict[str, str]:
        return {
            "type": "metadata",
            "transcription": self.transcription,
            "translation": self.translation,
        }


@dataclass(frozen=True)
class AudioChunkResult:
    data: bytes
    chunk_index: int

    def to_dict(self) -> dict[str, bytes | int | str]:
        return {
            "type": "audio_chunk",
            "data": self.data,
            "chunk_index": self.chunk_index,
        }
