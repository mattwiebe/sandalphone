"""
Test client for WebSocket translation server.
"""
import asyncio
import websockets
import json
import base64
from pathlib import Path


async def test_translation():
    """Test the WebSocket translation endpoint."""
    uri = "ws://localhost:8000/ws/translate"

    # Load sample audio
    sample_audio = Path(__file__).parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"

    if not sample_audio.exists():
        print(f"Sample audio not found: {sample_audio}")
        return

    # Read and encode audio
    with open(sample_audio, "rb") as f:
        audio_data = f.read()

    audio_b64 = base64.b64encode(audio_data).decode('utf-8')

    print("🔌 Connecting to WebSocket server...")

    async with websockets.connect(uri) as websocket:
        print("✅ Connected!")

        # Send translation request
        request = {
            "audio": audio_b64,
            "source_lang": "en",
            "target_lang": "es",
            "format": "wav"
        }

        print("\n📤 Sending translation request (EN → ES)...")
        await websocket.send(json.dumps(request))

        # Receive response
        print("⏳ Waiting for response...")
        response_str = await websocket.recv()
        response = json.loads(response_str)

        print("\n📥 Response received!")
        print(f"   Status: {response['status']}")

        if response['status'] == 'success':
            print(f"   Latency: {response['latency_ms']}ms")
            print(f"   Original (EN): {response['transcription']}")
            print(f"   Translation (ES): {response['translation']}")
            print(f"   Audio size: {len(response['audio'])} bytes (base64)")

            # Optionally save translated audio
            audio_data = base64.b64decode(response['audio'])
            output_file = Path("/tmp/translated_output.wav")
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"\n💾 Saved translated audio to: {output_file}")
            print(f"   Play with: afplay {output_file}")

        else:
            print(f"   Error: {response.get('error')}")


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         WebSocket Translation Server Test Client         ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    asyncio.run(test_translation())
