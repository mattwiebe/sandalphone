import base64
import json
import os
from pathlib import Path

import pytest
import websockets


SAMPLE_AUDIO = (
    Path(__file__).resolve().parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"
)


def _stream_url() -> str:
    return os.getenv("TEST_STREAM_WS_URL", "ws://localhost:8000/ws/stream")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_streaming_endpoint_emits_metadata_chunks_and_complete() -> None:
    if not SAMPLE_AUDIO.exists():
        pytest.skip(f"sample audio not found: {SAMPLE_AUDIO}")

    audio_b64 = base64.b64encode(SAMPLE_AUDIO.read_bytes()).decode("utf-8")

    metadata = None
    chunks = []
    complete = None

    async with websockets.connect(_stream_url()) as websocket:
        await websocket.send(
            json.dumps(
                {
                    "audio": audio_b64,
                    "source_lang": "en",
                    "target_lang": "es",
                    "format": "wav",
                    "streaming_interval": 1.5,
                }
            )
        )

        while True:
            response = json.loads(await websocket.recv())
            response_type = response["type"]

            if response_type == "metadata":
                metadata = response
            elif response_type == "audio_chunk":
                chunks.append(base64.b64decode(response["data"]))
            elif response_type == "complete":
                complete = response
                break
            elif response_type == "error":
                pytest.fail(response["error"])
            else:
                pytest.fail(f"unexpected response type: {response_type}")

    assert metadata is not None
    assert metadata["transcription"]
    assert metadata["translation"]

    assert chunks
    assert all(chunks)

    assert complete is not None
    assert complete["total_chunks"] == len(chunks)
    assert complete["latency_ms"] >= 0
