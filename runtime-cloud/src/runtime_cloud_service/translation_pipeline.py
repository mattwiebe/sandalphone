from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

from pipecat.frames.frames import InterimTranscriptionFrame, TTSSpeakFrame, TranscriptionFrame, TranslationFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transcriptions.language import Language
from pipecat.transports.livekit.transport import LiveKitOutputTransportMessageFrame
from requests import Session
from loguru import logger


def _to_deepl_source_language(language: Language) -> str:
    value = str(language).replace("_", "-").upper()
    return value.split("-", 1)[0]


def _to_deepl_target_language(language: Language) -> str:
    return str(language).replace("_", "-").upper()


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


class DeepLTranslateClient:
    def __init__(
        self,
        *,
        api_key: str,
        api_url: str = "https://api-free.deepl.com/v2/translate",
        session: Session | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._session = session or Session()

    def translate(
        self,
        text: str,
        *,
        source_language: Language,
        target_language: Language,
    ) -> str:
        response = self._session.post(
            self._api_url,
            data={
                "text": text,
                "source_lang": _to_deepl_source_language(source_language),
                "target_lang": _to_deepl_target_language(target_language),
            },
            headers={"Authorization": f"DeepL-Auth-Key {self._api_key}"},
            timeout=10,
        )
        response.raise_for_status()

        payload = response.json()
        translations = payload.get("translations", [])
        if not translations or "text" not in translations[0]:
            raise ValueError("DeepL response did not include translated text")

        return str(translations[0]["text"])


def build_translation_output_frames(
    *,
    config: TranslationPipelineConfig,
    transcription: TranscriptionFrame | InterimTranscriptionFrame,
    translator: TextTranslator,
) -> list[object]:
    if isinstance(transcription, InterimTranscriptionFrame):
        return []

    translated_text = translator.translate(
        transcription.text,
        source_language=transcription.language or config.source_language,
        target_language=config.target_language,
    )
    logger.info(
        "trusted translation produced",
        speaker_identity=transcription.user_id,
        transcription=transcription.text,
        translation=translated_text,
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
