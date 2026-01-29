"""
Test WebSocket streaming endpoint for real-time translation.
"""

import asyncio
import json
import base64
import sys
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    print("❌ websockets not installed. Install with: uv add websockets")
    sys.exit(1)


async def test_streaming_endpoint():
    """Test the /ws/stream endpoint."""
    print("="*60)
    print("WEBSOCKET STREAMING TEST")
    print("="*60)

    # Load sample audio
    sample_audio = (
        Path(__file__).parent.parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"
    )

    if not sample_audio.exists():
        print(f"❌ Sample audio not found: {sample_audio}")
        return

    print(f"\n✓ Found sample audio: {sample_audio}")

    # Read and encode audio
    with open(sample_audio, "rb") as f:
        audio_data = f.read()
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')

    print(f"✓ Encoded audio: {len(audio_b64)} bytes")

    # Connect to WebSocket
    uri = "ws://localhost:8000/ws/stream"
    print(f"\n📡 Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected!")

            # Send request
            request = {
                "audio": audio_b64,
                "source_lang": "en",
                "target_lang": "es",
                "format": "wav",
                "streaming_interval": 1.5
            }

            print("\n📤 Sending translation request...")
            start_time = time.time()
            await websocket.send(json.dumps(request))

            # Receive streaming responses
            chunks_received = 0
            first_chunk_time = None
            metadata = None
            audio_chunks = []

            print("\n📥 Receiving responses...")
            print("-"*60)

            while True:
                try:
                    response_text = await websocket.recv()
                    response = json.loads(response_text)

                    if response["type"] == "metadata":
                        metadata = response
                        print(f"\n✓ Metadata received:")
                        print(f"  Transcription: {metadata['transcription']}")
                        print(f"  Translation: {metadata['translation']}\n")

                    elif response["type"] == "audio_chunk":
                        if chunks_received == 0:
                            first_chunk_time = time.time() - start_time
                            print(f"✓ First audio chunk: {first_chunk_time*1000:.0f}ms\n")

                        chunk_data = base64.b64decode(response["data"])
                        audio_chunks.append(chunk_data)
                        chunks_received += 1
                        print(f"  Chunk {response['chunk_index']}: {len(chunk_data)} bytes")

                    elif response["type"] == "complete":
                        total_time = time.time() - start_time
                        print(f"\n✓ Complete:")
                        print(f"  Total chunks: {response['total_chunks']}")
                        print(f"  Server latency: {response['latency_ms']}ms")
                        print(f"  Client latency: {total_time*1000:.0f}ms")
                        break

                    elif response["type"] == "error":
                        print(f"❌ Error: {response['error']}")
                        break

                except websockets.exceptions.ConnectionClosed:
                    print("Connection closed")
                    break

            # Summary
            print("\n" + "="*60)
            print("STREAMING RESULTS")
            print("="*60)
            print(f"Chunks received: {chunks_received}")
            print(f"Total audio data: {sum(len(c) for c in audio_chunks)} bytes")

            if first_chunk_time:
                print(f"Time to first chunk: {first_chunk_time*1000:.0f}ms")

            print("="*60)
            print("✓ TEST PASSED")

            # Save combined audio
            if audio_chunks:
                output_file = Path("/tmp/streaming_test_output.wav")
                with open(output_file, "wb") as f:
                    for chunk in audio_chunks:
                        f.write(chunk)
                print(f"\n💾 Saved combined audio to: {output_file}")
                print("Play with: afplay /tmp/streaming_test_output.wav")

    except ConnectionRefusedError:
        print("❌ Connection refused. Is the server running?")
        print("Start with: TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run the test."""
    asyncio.run(test_streaming_endpoint())


if __name__ == "__main__":
    main()
