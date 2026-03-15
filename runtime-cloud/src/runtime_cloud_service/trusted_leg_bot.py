from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Protocol

from livekit import api, rtc
from pipecat.frames.frames import (
    Frame,
    InterimTranscriptionFrame,
    TTSSpeakFrame,
    TranscriptionFrame,
    TranslationFrame,
    UserAudioRawFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.assemblyai.stt import AssemblyAISTTService, AssemblyAISTTSettings
from pipecat.services.cartesia.tts import CartesiaTTSService, CartesiaTTSSettings
from pipecat.transcriptions.language import Language
from pipecat.transports.livekit.transport import LiveKitOutputTransportMessageFrame
from pipecat.transports.livekit.transport import LiveKitTransport

from .translation_pipeline import DeepLTranslateClient, TranslationPipelineConfig, TranslationProcessor


class TextTranslator(Protocol):
    def translate(
        self,
        text: str,
        *,
        source_language: Language,
        target_language: Language,
    ) -> str: ...


class PassthroughTranslator:
    def translate(
        self,
        text: str,
        *,
        source_language: Language,
        target_language: Language,
    ) -> str:
        return text


@dataclass(frozen=True)
class ProviderBundle:
    assemblyai_api_key: str
    deepl_api_key: str
    cartesia_api_key: str
    cartesia_voice_id: str


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def build_provider_bundle_from_env() -> ProviderBundle:
    return ProviderBundle(
        assemblyai_api_key=_require_env("ASSEMBLYAI_API_KEY"),
        deepl_api_key=_require_env("DEEPL_API_KEY"),
        cartesia_api_key=_require_env("CARTESIA_API_KEY"),
        cartesia_voice_id=_require_env("CARTESIA_VOICE_ID"),
    )


@dataclass(frozen=True)
class TrustedLegBotConfig:
    room_name: str
    trusted_identity: str
    source_language: Language = Language.ES_MX
    target_language: Language = Language.EN_US
    bot_identity: str = "levi-trusted-leg-bot"
    bot_name: str = "Levi Trusted Leg"


class DropInputFramesProcessor(FrameProcessor):
    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if direction is FrameDirection.DOWNSTREAM and isinstance(
            frame,
            (UserAudioRawFrame, TranscriptionFrame, InterimTranscriptionFrame),
        ):
            return
        await self.push_frame(frame, direction)


def issue_bot_token(
    *,
    room_name: str,
    bot_identity: str,
    bot_name: str,
    api_key: str,
    api_secret: str,
) -> str:
    token = (
        api.AccessToken(api_key, api_secret)
        .with_identity(bot_identity)
        .with_name(bot_name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                agent=True,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
    )
    return token.to_jwt()


def build_private_audio_permissions(
    trusted_identity: str,
) -> list[rtc.ParticipantTrackPermission]:
    return [
        rtc.ParticipantTrackPermission(
            participant_identity=trusted_identity,
            allow_all=True,
        )
    ]


def build_trusted_translation_frames(
    *,
    config: TrustedLegBotConfig,
    transcription: TranscriptionFrame,
    translated_text: str,
) -> list[object]:
    metadata = {
        "type": "trusted_translation",
        "speaker_identity": transcription.user_id,
        "source_language": str(transcription.language or config.source_language),
        "target_language": str(config.target_language),
        "transcription": transcription.text,
        "translation": translated_text,
        "timestamp": transcription.timestamp,
    }
    return [
        TranslationFrame(
            text=translated_text,
            user_id=transcription.user_id,
            timestamp=transcription.timestamp,
            language=config.target_language,
        ),
        LiveKitOutputTransportMessageFrame(
            message=json.dumps(metadata),
            participant_id=config.trusted_identity,
        ),
        TTSSpeakFrame(text=translated_text),
    ]


class TrustedLegPipecatBot:
    def __init__(
        self,
        *,
        livekit_url: str,
        api_key: str,
        api_secret: str,
        config: TrustedLegBotConfig,
    ) -> None:
        self._livekit_url = livekit_url
        self._api_key = api_key
        self._api_secret = api_secret
        self._config = config
        self._task: PipelineTask | None = None

    async def run(self) -> None:
        providers = build_provider_bundle_from_env()
        token = issue_bot_token(
            room_name=self._config.room_name,
            bot_identity=self._config.bot_identity,
            bot_name=self._config.bot_name,
            api_key=self._api_key,
            api_secret=self._api_secret,
        )
        transport = LiveKitTransport(
            self._livekit_url,
            token,
            self._config.room_name,
        )
        stt = AssemblyAISTTService(
            api_key=providers.assemblyai_api_key,
            sample_rate=16000,
            settings=AssemblyAISTTSettings(language=self._config.source_language),
        )
        tts = CartesiaTTSService(
            api_key=providers.cartesia_api_key,
            sample_rate=24000,
            settings=CartesiaTTSSettings(
                voice=providers.cartesia_voice_id,
                model=os.getenv("CARTESIA_MODEL") or "sonic-3",
            ),
        )
        translator = DeepLTranslateClient(api_key=providers.deepl_api_key)

        @transport.event_handler("on_connected")
        async def on_connected(_transport: LiveKitTransport) -> None:
            local_participant = _transport._client.room.local_participant  # noqa: SLF001
            local_participant.set_track_subscription_permissions(
                allow_all_participants=False,
                participant_permissions=build_private_audio_permissions(
                    self._config.trusted_identity
                ),
            )
            await _transport.send_message(
                json.dumps(
                    {
                        "type": "trusted_leg_bot_connected",
                        "room_name": self._config.room_name,
                        "bot_identity": self._config.bot_identity,
                    }
                ),
                participant_id=self._config.trusted_identity,
            )

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                TranslationProcessor(
                    config=TranslationPipelineConfig(
                        trusted_identity=self._config.trusted_identity,
                        source_language=self._config.source_language,
                        target_language=self._config.target_language,
                    ),
                    translator=translator,
                ),
                tts,
                DropInputFramesProcessor(),
                transport.output(),
            ]
        )
        self._task = PipelineTask(pipeline)
        runner = PipelineRunner(handle_sigint=False, handle_sigterm=False)
        await runner.run(self._task)

    async def stop(self) -> None:
        if self._task is not None:
            await self._task.cancel()
