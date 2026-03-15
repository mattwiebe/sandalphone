from __future__ import annotations

import audioop
import json
import os
from dataclasses import dataclass
from typing import Protocol

from livekit import api, rtc
from loguru import logger
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
from pipecat.transports.livekit.transport import LiveKitParams
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
    assemblyai_sample_rate: int
    assemblyai_speech_model: str
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
        assemblyai_sample_rate=int(os.getenv("ASSEMBLYAI_SAMPLE_RATE", "16000")),
        assemblyai_speech_model=os.getenv(
            "ASSEMBLYAI_SPEECH_MODEL",
            "universal-streaming-multilingual",
        ),
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


def normalize_audio_for_stt(
    *,
    audio: bytes,
    num_channels: int,
    sample_rate: int,
    target_sample_rate: int,
) -> bytes:
    normalized = audio
    if num_channels > 1:
        normalized = audioop.tomono(normalized, 2, 0.5, 0.5)
    if sample_rate != target_sample_rate:
        normalized, _ = audioop.ratecv(normalized, 2, 1, sample_rate, target_sample_rate, None)
    return normalized


class AudioNormalizeForSTTProcessor(FrameProcessor):
    def __init__(self, *, target_sample_rate: int) -> None:
        super().__init__()
        self._target_sample_rate = target_sample_rate
        self._debug_frames_remaining = int(os.getenv("STT_DEBUG_FRAME_LOGS", "8"))

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if direction is FrameDirection.DOWNSTREAM and isinstance(frame, UserAudioRawFrame):
            normalized = normalize_audio_for_stt(
                audio=frame.audio,
                num_channels=frame.num_channels,
                sample_rate=frame.sample_rate,
                target_sample_rate=self._target_sample_rate,
            )
            if self._debug_frames_remaining > 0:
                source_rms = audioop.rms(frame.audio, 2) if frame.audio else 0
                normalized_rms = audioop.rms(normalized, 2) if normalized else 0
                logger.info(
                    "stt normalize frame user={} src_bytes={} src_rate={} src_channels={} "
                    "src_rms={} out_bytes={} out_rate={} out_channels=1 out_rms={}",
                    frame.user_id,
                    len(frame.audio),
                    frame.sample_rate,
                    frame.num_channels,
                    source_rms,
                    len(normalized),
                    self._target_sample_rate,
                    normalized_rms,
                )
                self._debug_frames_remaining -= 1
            await self.push_frame(
                UserAudioRawFrame(
                    user_id=frame.user_id,
                    audio=normalized,
                    sample_rate=self._target_sample_rate,
                    num_channels=1,
                ),
                direction,
            )
            return

        await self.push_frame(frame, direction)


class DebugAssemblyAISTTService(AssemblyAISTTService):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._debug_chunks_remaining = int(os.getenv("STT_DEBUG_CHUNK_LOGS", "8"))

    async def run_stt(self, audio: bytes):
        if self._debug_chunks_remaining > 0:
            logger.info(
                "assembly enqueue bytes={} buffer_before={} chunk_size={} sample_rate={}",
                len(audio),
                len(self._audio_buffer),
                self._chunk_size_bytes,
                self.sample_rate,
            )
            self._debug_chunks_remaining -= 1
        async for frame in super().run_stt(audio):
            yield frame


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
            params=LiveKitParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=providers.assemblyai_sample_rate,
                audio_out_sample_rate=24000,
            ),
        )
        stt = DebugAssemblyAISTTService(
            api_key=providers.assemblyai_api_key,
            sample_rate=providers.assemblyai_sample_rate,
            settings=AssemblyAISTTSettings(
                language=self._config.source_language,
                model=providers.assemblyai_speech_model,
                language_detection=True,
            ),
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
                AudioNormalizeForSTTProcessor(
                    target_sample_rate=providers.assemblyai_sample_rate
                ),
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
