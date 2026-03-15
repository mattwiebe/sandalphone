from __future__ import annotations

import asyncio
import json
import os
import unicodedata
import wave
from asyncio import Queue
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import urlencode

import pytest
import requests
from pipecat.frames.frames import EndFrame, Frame, TTSAudioRawFrame, TTSStoppedFrame, UserAudioRawFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.tests.utils import QueuedFrameProcessor, SleepFrame
from pipecat.transcriptions.language import Language
from pipecat.transports.livekit.transport import LiveKitOutputTransportMessageFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.assemblyai.stt import AssemblyAISTTService, AssemblyAISTTSettings
from pipecat.services.cartesia.tts import CartesiaTTSService, CartesiaTTSSettings
from websockets.asyncio.client import connect as websocket_connect

from runtime_cloud_service.translation_pipeline import DeepLTranslateClient, TranslationPipelineConfig, TranslationProcessor


_SPANISH_TEXT = "hola como estas necesito ayuda con una traduccion"
_FIXTURE_AUDIO = Path(__file__).resolve().parents[1] / "fixtures" / "spanish_hola_como_estas.wav"


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is required for provider integration tests")
    return value


def _normalize_text(value: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in ascii_text.lower() if ch.isalnum() or ch.isspace()).strip()


def _chunk_bytes(data: bytes, chunk_size: int) -> AsyncIterator[bytes]:
    async def _iterator() -> AsyncIterator[bytes]:
        for index in range(0, len(data), chunk_size):
            yield data[index : index + chunk_size]
            await asyncio.sleep(0.05)

    return _iterator()


def _synthesize_cartesia_pcm16() -> bytes:
    api_key = _require_env("CARTESIA_API_KEY")
    voice_id = _require_env("CARTESIA_VOICE_ID")

    response = requests.post(
        "https://api.cartesia.ai/tts/bytes",
        headers={
            "Cartesia-Version": "2025-04-16",
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "model_id": os.getenv("CARTESIA_MODEL", "sonic-2"),
            "transcript": _SPANISH_TEXT,
            "voice": {"mode": "id", "id": voice_id},
            "language": "es",
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 16000,
            },
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.content


def _load_fixture_pcm16() -> bytes:
    with wave.open(str(_FIXTURE_AUDIO), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 16000
        return wav_file.readframes(wav_file.getnframes())


@pytest.mark.integration
def test_deepl_translates_spanish_text() -> None:
    api_key = _require_env("DEEPL_API_KEY")

    response = requests.post(
        "https://api-free.deepl.com/v2/translate",
        data={
            "text": _SPANISH_TEXT,
            "source_lang": "ES",
            "target_lang": "EN-US",
        },
        headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
        timeout=10,
    )
    response.raise_for_status()

    payload = response.json()
    translated_text = payload["translations"][0]["text"]

    normalized = _normalize_text(translated_text)
    assert normalized
    assert normalized != _normalize_text(_SPANISH_TEXT)
    assert "hello" in normalized or "translation" in normalized or "help" in normalized


@pytest.mark.integration
def test_cartesia_synthesizes_spanish_pcm_audio() -> None:
    audio = _synthesize_cartesia_pcm16()

    assert audio
    assert len(audio) > 3200


@pytest.mark.integration
def test_assemblyai_streaming_transcribes_spanish_audio() -> None:
    transcript = asyncio.run(_stream_audio_to_assemblyai(_synthesize_cartesia_pcm16()))

    normalized = _normalize_text(transcript)
    assert normalized
    assert "hola" in normalized or "ola" in normalized
    assert "como" in normalized


@pytest.mark.integration
def test_live_provider_pipeline_translates_and_synthesizes_spanish_fixture() -> None:
    frames = asyncio.run(_run_live_provider_pipeline(_load_fixture_pcm16()))

    metadata_frames = [
        frame for frame in frames if isinstance(frame, LiveKitOutputTransportMessageFrame)
    ]
    tts_audio_frames = [frame for frame in frames if isinstance(frame, TTSAudioRawFrame)]

    assert metadata_frames
    assert tts_audio_frames
    assert any(isinstance(frame, TTSStoppedFrame) for frame in frames)

    translated_text = _normalize_text(json.loads(metadata_frames[-1].message)["translation"])
    assert "hello" in translated_text or "translation" in translated_text or "help" in translated_text
    assert metadata_frames[-1].participant_id == "trusted-matt"
    assert sum(len(frame.audio) for frame in tts_audio_frames) > 3200


async def _stream_audio_to_assemblyai(audio: bytes) -> str:
    api_key = _require_env("ASSEMBLYAI_API_KEY")
    query = urlencode(
        {
            "sample_rate": 16000,
            "encoding": "pcm_s16le",
            "speech_model": "universal-streaming-multilingual",
            "language_detection": "true",
        }
    )
    transcript_parts: list[str] = []

    async with websocket_connect(
        f"wss://streaming.assemblyai.com/v3/ws?{query}",
        additional_headers={"Authorization": api_key},
    ) as websocket:
        await _wait_for_message_type(websocket, "Begin")

        async for chunk in _chunk_bytes(audio, 1600):
            await websocket.send(chunk)

        await websocket.send(json.dumps({"type": "Terminate"}))

        while True:
            message = json.loads(await websocket.recv())
            if message.get("type") == "Turn" and message.get("transcript"):
                transcript_parts.append(str(message["transcript"]))
            if message.get("type") == "Termination":
                break

    return " ".join(transcript_parts)


async def _wait_for_message_type(websocket, expected_type: str) -> dict[str, object]:
    while True:
        message = json.loads(await websocket.recv())
        if message.get("type") == expected_type:
            return message


async def _run_live_provider_pipeline(audio: bytes) -> list[Frame]:
    received_down: Queue[Frame] = Queue()
    source = QueuedFrameProcessor(queue=Queue(), queue_direction=FrameDirection.UPSTREAM)
    sink = QueuedFrameProcessor(queue=received_down, queue_direction=FrameDirection.DOWNSTREAM)

    stt = AssemblyAISTTService(
        api_key=_require_env("ASSEMBLYAI_API_KEY"),
        sample_rate=16000,
        settings=AssemblyAISTTSettings(
            language=Language.ES_MX,
            model="universal-streaming-multilingual",
            language_detection=True,
        ),
    )
    translation = TranslationProcessor(
        config=TranslationPipelineConfig(
            trusted_identity="trusted-matt",
            source_language=Language.ES_MX,
            target_language=Language.EN_US,
        ),
        translator=DeepLTranslateClient(api_key=_require_env("DEEPL_API_KEY")),
    )
    tts = CartesiaTTSService(
        api_key=_require_env("CARTESIA_API_KEY"),
        sample_rate=24000,
        settings=CartesiaTTSSettings(
            voice=_require_env("CARTESIA_VOICE_ID"),
            model=os.getenv("CARTESIA_MODEL", "sonic-2"),
        ),
    )

    pipeline = Pipeline([source, stt, translation, tts, sink])
    task = PipelineTask(pipeline, cancel_on_idle_timeout=False)
    runner = PipelineRunner()

    async def push_frames() -> None:
        await asyncio.sleep(0.01)
        for chunk in _chunk_audio_frames(audio, chunk_size=1600):
            await task.queue_frame(
                UserAudioRawFrame(
                    user_id="fixture-caller",
                    audio=chunk,
                    sample_rate=16000,
                    num_channels=1,
                )
            )
            await task.queue_frame(SleepFrame(sleep=0.05))
        await task.queue_frame(SleepFrame(sleep=6.0))
        await task.queue_frame(EndFrame())

    await asyncio.gather(runner.run(task), push_frames())

    frames: list[Frame] = []
    while not received_down.empty():
        frame = await received_down.get()
        if not isinstance(frame, EndFrame):
            frames.append(frame)
    return frames


def _chunk_audio_frames(audio: bytes, *, chunk_size: int) -> list[bytes]:
    return [audio[index : index + chunk_size] for index in range(0, len(audio), chunk_size)]
