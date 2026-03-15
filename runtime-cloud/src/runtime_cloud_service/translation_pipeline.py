from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from google.cloud import translate_v2 as translate
from pipecat.frames.frames import InterimTranscriptionFrame, TTSSpeakFrame, TranscriptionFrame, TranslationFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transcriptions.language import Language
from pipecat.transports.livekit.transport import LiveKitOutputTransportMessageFrame


class TextTranslator(Protocol):
    def translate(
        self,
        text: str,
        *,
        source_language: Language,
        target_language: Language,
    ) -> str: ...


@dataclass(frozen=True)
class TranslationPipelineConfig:
    trusted_identity: str
    source_language: Language
    target_language: Language


class GoogleTranslateClient:
    def __init__(self) -> None:
        self._client = translate.Client()

    def translate(
        self,
        text: str,
        *,
        source_language: Language,
        target_language: Language,
    ) -> str:
        result = self._client.translate(
            text,
            source_language=str(source_language),
            target_language=str(target_language),
            format_="text",
        )
        return str(result["translatedText"])


def build_translation_output_frames(
    *,
    config: TranslationPipelineConfig,
    transcription: TranscriptionFrame | InterimTranscriptionFrame,
    translator: TextTranslator,
) -> list[object]:
    if isinstance(transcription, InterimTranscriptionFrame):
        return []
    if not transcription.finalized:
        return []

    translated_text = translator.translate(
        transcription.text,
        source_language=transcription.language or config.source_language,
        target_language=config.target_language,
    )
    metadata = json.dumps(
        {
            "type": "trusted_translation",
            "speaker_identity": transcription.user_id,
            "transcription": transcription.text,
            "translation": translated_text,
            "source_language": str(transcription.language or config.source_language),
            "target_language": str(config.target_language),
            "timestamp": transcription.timestamp,
        }
    )
    return [
        TranslationFrame(
            text=translated_text,
            user_id=transcription.user_id,
            timestamp=transcription.timestamp,
            language=config.target_language,
        ),
        LiveKitOutputTransportMessageFrame(
            message=metadata,
            participant_id=config.trusted_identity,
        ),
        TTSSpeakFrame(text=translated_text),
    ]


class TranslationProcessor(FrameProcessor):
    def __init__(
        self,
        *,
        config: TranslationPipelineConfig,
        translator: TextTranslator,
    ) -> None:
        super().__init__()
        self._config = config
        self._translator = translator

    async def process_frame(self, frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if direction is not FrameDirection.DOWNSTREAM:
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame)):
            for output in build_translation_output_frames(
                config=self._config,
                transcription=frame,
                translator=self._translator,
            ):
                await self.push_frame(output, direction)
            return

        await self.push_frame(frame, direction)
