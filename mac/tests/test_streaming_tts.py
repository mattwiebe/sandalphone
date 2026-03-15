import sys
import time
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tts.factory import create_tts_provider


@pytest.fixture
def tts_provider():
    return create_tts_provider()


@pytest.mark.hardware
def test_streaming_tts_yields_non_empty_audio_chunks(tts_provider) -> None:
    if not hasattr(tts_provider, "synthesize_streaming"):
        pytest.skip("configured TTS provider does not support streaming")

    chunks = list(tts_provider.synthesize_streaming(text="Hello world", language="en"))

    assert chunks
    assert all(isinstance(chunk, bytes) for chunk in chunks)
    assert all(chunk for chunk in chunks)


@pytest.mark.hardware
def test_streaming_tts_reduces_time_to_first_audio(tts_provider) -> None:
    if not hasattr(tts_provider, "synthesize_streaming"):
        pytest.skip("configured TTS provider does not support streaming")

    text = (
        "This is a test of the streaming text-to-speech system. "
        "It should produce audio chunks before the full batch render finishes."
    )

    batch_start = time.time()
    audio_file = tts_provider.synthesize(text, language="en")
    batch_elapsed = time.time() - batch_start

    streaming_start = time.time()
    first_chunk_at = None

    for index, chunk in enumerate(
        tts_provider.synthesize_streaming(text=text, language="en", streaming_interval=1.5)
    ):
        assert chunk
        if index == 0:
            first_chunk_at = time.time() - streaming_start
            break

    assert audio_file.exists()
    assert first_chunk_at is not None
    assert first_chunk_at < batch_elapsed
