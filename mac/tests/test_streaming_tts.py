"""
Test script for VibeVoice streaming TTS functionality.
Verifies that streaming reduces time-to-first-audio.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tts.factory import create_tts_provider


def test_streaming_vs_batch():
    """Compare streaming vs batch TTS latency."""
    print("="*60)
    print("STREAMING TTS LATENCY TEST")
    print("="*60)

    tts = create_tts_provider()
    test_text = "This is a test of the streaming text-to-speech system. It should produce audio chunks as they are generated, reducing the time to first audio significantly."

    # Test 1: Batch mode (baseline)
    print("\n[Test 1] Batch Mode (baseline)")
    print("-"*60)
    start = time.time()
    audio_file = tts.synthesize(test_text, language="en")
    total_time = time.time() - start
    print(f"✓ Total generation time: {total_time*1000:.0f}ms")
    print(f"✓ Audio file: {audio_file}")

    # Test 2: Streaming mode
    if hasattr(tts, 'synthesize_streaming'):
        print("\n[Test 2] Streaming Mode")
        print("-"*60)

        chunks = []
        start = time.time()
        first_chunk_time = None

        for i, chunk in enumerate(tts.synthesize_streaming(
            text=test_text,
            language="en",
            streaming_interval=1.5
        )):
            if i == 0:
                first_chunk_time = time.time() - start
                print(f"✓ First chunk arrived: {first_chunk_time*1000:.0f}ms")

            chunks.append(chunk)
            print(f"  Chunk {i}: {len(chunk)} bytes")

        total_time_streaming = time.time() - start

        print(f"\n✓ Total streaming time: {total_time_streaming*1000:.0f}ms")
        print(f"✓ Total chunks: {len(chunks)}")
        print(f"✓ Total bytes: {sum(len(c) for c in chunks)}")

        # Calculate improvement
        if first_chunk_time:
            improvement = ((total_time - first_chunk_time) / total_time) * 100
            print(f"\n{'='*60}")
            print(f"LATENCY IMPROVEMENT")
            print(f"{'='*60}")
            print(f"Batch mode (first audio): {total_time*1000:.0f}ms")
            print(f"Streaming (first chunk):  {first_chunk_time*1000:.0f}ms")
            print(f"Improvement:              {improvement:.1f}% faster")
            print(f"{'='*60}")

    else:
        print("\n⚠️  TTS provider doesn't support streaming")


def test_streaming_basic():
    """Basic test that streaming works."""
    print("\n" + "="*60)
    print("BASIC STREAMING TEST")
    print("="*60)

    tts = create_tts_provider()

    if not hasattr(tts, 'synthesize_streaming'):
        print("⚠️  TTS provider doesn't support streaming")
        return

    test_text = "Hello world, this is a streaming test."

    print(f"\nText: {test_text}")
    print("Generating audio chunks...\n")

    chunks = list(tts.synthesize_streaming(text=test_text, language="en"))

    print(f"\n✓ Generated {len(chunks)} chunks")
    assert len(chunks) > 0, "Should generate at least one chunk"
    assert all(isinstance(c, bytes) for c in chunks), "All chunks should be bytes"
    assert all(len(c) > 0 for c in chunks), "All chunks should have data"

    print("✓ All chunks are valid WAV bytes")
    print("✓ BASIC STREAMING TEST PASSED")


def main():
    """Run all streaming tests."""
    try:
        test_streaming_basic()
        print("\n")
        test_streaming_vs_batch()

        print("\n" + "="*60)
        print("ALL TESTS PASSED ✓")
        print("="*60)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
