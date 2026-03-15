import base64
import json
import os
from pathlib import Path

import pytest
import websockets


SAMPLE_AUDIO = (
    Path(__file__).resolve().parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"
)


def _translation_url() -> str:
    return os.getenv("TEST_TRANSLATE_WS_URL", "ws://localhost:8000/ws/translate")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_translation_endpoint_returns_success_payload() -> None:
    if not SAMPLE_AUDIO.exists():
        pytest.skip(f"sample audio not found: {SAMPLE_AUDIO}")

    audio_b64 = base64.b64encode(SAMPLE_AUDIO.read_bytes()).decode("utf-8")

    async with websockets.connect(_translation_url()) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "audio": audio_b64,
                    "source_lang": "en",
                    "target_lang": "es",
                    "format": "wav",
                }
            )
        )

        response = json.loads(await websocket.recv())

    assert response["status"] == "success"
    assert isinstance(response["latency_ms"], int | float)
    assert response["latency_ms"] >= 0
    assert response["transcription"]
    assert response["translation"]

    translated_audio = base64.b64decode(response["audio"])
    assert translated_audio
