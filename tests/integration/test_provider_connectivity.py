from __future__ import annotations

import asyncio
import json
import os
import unicodedata
from collections.abc import AsyncIterator
from urllib.parse import urlencode

import pytest
import requests
from websockets.asyncio.client import connect as websocket_connect


_SPANISH_TEXT = "hola como estas"


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
    assert "hello" in normalized or "how are you" in normalized


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
    assert "hola" in normalized
    assert "como" in normalized


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
