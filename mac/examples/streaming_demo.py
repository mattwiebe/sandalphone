#!/usr/bin/env python3
"""
Simple demonstration of VibeVoice streaming TTS.
Shows the difference between batch and streaming modes.
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tts.factory import create_tts_provider


def demo_streaming():
    """Demonstrate streaming TTS with visual feedback."""
    print("="*60)
    print("VIBEVOICE STREAMING TTS DEMO")
    print("="*60)

    tts = create_tts_provider()

    # Check if streaming is available
    if not hasattr(tts, 'synthesize_streaming'):
        print("❌ Streaming not available with current TTS provider")
        print("Set TTS_PROVIDER=vibevoice to enable streaming")
        return

    test_text = (
        "Welcome to the streaming text-to-speech demonstration. "
        "Notice how audio chunks arrive progressively, "
        "rather than waiting for complete generation. "
        "This significantly reduces perceived latency "
        "in real-time conversational applications."
    )

    print(f"\nText to synthesize:")
    print(f"  \"{test_text}\"\n")
    print(f"Length: {len(test_text)} characters\n")

    # Demo streaming with visual progress
    print("🎙️  Starting streaming generation...\n")
    print("Progress:")

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
            print(f"  ⚡ First chunk: {first_chunk_time*1000:.0f}ms")

        chunks.append(chunk)

        # Visual progress bar
        progress = "█" * (i + 1)
        print(f"  {progress} Chunk {i}: {len(chunk):,} bytes")

    total_time = time.time() - start

    print(f"\n✅ Complete!")
    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Total chunks:        {len(chunks)}")
    print(f"Total bytes:         {sum(len(c) for c in chunks):,}")
    print(f"Time to first chunk: {first_chunk_time*1000:.0f}ms")
    print(f"Total time:          {total_time*1000:.0f}ms")
    print(f"Average per chunk:   {(total_time / len(chunks))*1000:.0f}ms")
    print(f"{'='*60}")

    # Save combined audio
    import tempfile
    output_file = Path(tempfile.gettempdir()) / "streaming_demo_output.wav"

    with open(output_file, "wb") as f:
        for chunk in chunks:
            f.write(chunk)

    print(f"\n💾 Saved audio to: {output_file}")
    print(f"\nPlay with:")
    print(f"  afplay {output_file}")

    # Optionally play
    import subprocess
    print(f"\n▶️  Playing audio...")
    subprocess.run(["afplay", str(output_file)])


def compare_batch_vs_streaming():
    """Side-by-side comparison of batch vs streaming."""
    print("\n" + "="*60)
    print("BATCH vs STREAMING COMPARISON")
    print("="*60)

    tts = create_tts_provider()

    test_text = "This is a comparison test between batch and streaming modes."

    # Batch mode
    print("\n📦 [Batch Mode]")
    print("  Waiting for complete generation...")
    start = time.time()
    audio_file = tts.synthesize(test_text, language="en")
    batch_time = time.time() - start
    print(f"  ✓ Complete: {batch_time*1000:.0f}ms")
    print(f"  Time to hear audio: {batch_time*1000:.0f}ms")

    # Streaming mode
    if hasattr(tts, 'synthesize_streaming'):
        print("\n🌊 [Streaming Mode]")
        print("  Streaming chunks as generated...")

        start = time.time()
        first_chunk_time = None
        chunks = []

        for i, chunk in enumerate(tts.synthesize_streaming(
            text=test_text,
            language="en",
            streaming_interval=1.0
        )):
            if i == 0:
                first_chunk_time = time.time() - start
            chunks.append(chunk)

        total_time = time.time() - start

        print(f"  ✓ Complete: {total_time*1000:.0f}ms")
        print(f"  Time to hear audio: {first_chunk_time*1000:.0f}ms")

        # Calculate improvement
        improvement = ((batch_time - first_chunk_time) / batch_time) * 100

        print(f"\n{'='*60}")
        print(f"IMPROVEMENT")
        print(f"{'='*60}")
        print(f"Batch mode:    {batch_time*1000:.0f}ms to first audio")
        print(f"Streaming:     {first_chunk_time*1000:.0f}ms to first audio")
        print(f"Faster by:     {improvement:.1f}%")
        print(f"Saved time:    {(batch_time - first_chunk_time)*1000:.0f}ms")
        print(f"{'='*60}")


def main():
    """Run all demos."""
    import os

    # Check TTS provider
    provider = os.getenv("TTS_PROVIDER", "default")
    print(f"\nTTS Provider: {provider}")

    if provider != "vibevoice":
        print("\n⚠️  Warning: TTS_PROVIDER is not set to 'vibevoice'")
        print("Streaming may not be available.")
        print("\nTo enable streaming:")
        print("  export TTS_PROVIDER=vibevoice")
        print("  or")
        print("  TTS_PROVIDER=vibevoice python mac/examples/streaming_demo.py\n")

    try:
        demo_streaming()
        compare_batch_vs_streaming()

        print("\n" + "="*60)
        print("DEMO COMPLETE ✓")
        print("="*60)
        print("\nKey Takeaways:")
        print("  • Streaming reduces time-to-first-audio")
        print("  • Users hear output sooner in real-time apps")
        print("  • Particularly effective for longer text")
        print("  • No quality loss vs. batch mode")
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
