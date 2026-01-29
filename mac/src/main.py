"""
Main FastAPI server for Levi translation service.
Exposes WebSocket endpoint for remote access via Cloudflare Tunnel.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import asyncio
import json
import tempfile
from pathlib import Path
import base64
from datetime import datetime

from translation_service import TranslationService
from streaming_translation_service import StreamingTranslationService

app = FastAPI(title="Levi Translation Service")

# Initialize translation services (singletons)
translation_service = None
streaming_translation_service = None


@app.on_event("startup")
async def startup_event():
    """Initialize the translation services on startup."""
    global translation_service, streaming_translation_service
    print("🚀 Starting Levi Translation Service...")
    translation_service = TranslationService()
    streaming_translation_service = StreamingTranslationService()
    print("✅ Service ready!")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Levi Translation Service",
        "status": "running",
        "version": "0.1.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "translation_service": "ready" if translation_service else "not initialized",
        "streaming_service": "ready" if streaming_translation_service else "not initialized",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.websocket("/ws/translate")
async def websocket_translate(websocket: WebSocket):
    """
    WebSocket endpoint for real-time translation.

    Protocol:
    Client sends: {
        "audio": "<base64-encoded audio data>",
        "source_lang": "es" | "en",
        "target_lang": "en" | "es",
        "format": "wav" | "mp3" | "ogg"
    }

    Server responds: {
        "status": "success" | "error",
        "transcription": "<original text>",
        "translation": "<translated text>",
        "audio": "<base64-encoded translated audio>",
        "latency_ms": <int>,
        "error": "<error message if status=error>"
    }
    """
    await websocket.accept()
    print(f"✓ WebSocket client connected from {websocket.client}")

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            request = json.loads(data)

            print(f"\n{'='*60}")
            print(f"📥 Translation request: {request.get('source_lang')} → {request.get('target_lang')}")
            start_time = asyncio.get_event_loop().time()

            try:
                # Decode audio
                audio_data = base64.b64decode(request["audio"])
                audio_format = request.get("format", "wav")

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp_audio:
                    temp_audio.write(audio_data)
                    temp_audio_path = temp_audio.name

                # Convert to WAV if needed (Whisper requires WAV)
                if audio_format != "wav":
                    import subprocess
                    wav_path = temp_audio_path.replace(f".{audio_format}", ".wav")
                    subprocess.run([
                        "ffmpeg", "-i", temp_audio_path,
                        "-ar", "16000",  # 16kHz sample rate
                        "-ac", "1",      # Mono
                        "-y",            # Overwrite
                        wav_path
                    ], capture_output=True, check=True)
                    # Clean up original file
                    Path(temp_audio_path).unlink(missing_ok=True)
                    temp_audio_path = wav_path

                # Process translation
                result = translation_service.translate_audio(
                    input_audio=temp_audio_path,
                    source_lang=request["source_lang"],
                    target_lang=request["target_lang"]
                )

                # Read output audio and encode
                with open(result["output_audio"], "rb") as f:
                    output_audio_data = f.read()
                output_audio_b64 = base64.b64encode(output_audio_data).decode('utf-8')

                # Calculate latency
                latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                # Send response
                response = {
                    "status": "success",
                    "transcription": result["transcription"],
                    "translation": result["translation"],
                    "audio": output_audio_b64,
                    "latency_ms": latency_ms
                }

                print(f"✅ Translation completed in {latency_ms}ms")
                print(f"   Original: {result['transcription'][:50]}...")
                print(f"   Translated: {result['translation'][:50]}...")

                await websocket.send_text(json.dumps(response))

                # Cleanup temp files
                Path(temp_audio_path).unlink(missing_ok=True)
                Path(result["output_audio"]).unlink(missing_ok=True)

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Translation error: {error_msg}")

                await websocket.send_text(json.dumps({
                    "status": "error",
                    "error": error_msg
                }))

    except WebSocketDisconnect:
        print(f"✗ WebSocket client disconnected")


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint for streaming translation (low-latency TTS).

    Protocol:
    Client sends: {
        "audio": "<base64-encoded audio data>",
        "source_lang": "es" | "en",
        "target_lang": "en" | "es",
        "format": "wav" | "mp3" | "ogg",
        "streaming_interval": <float, optional, default: 2.0>
    }

    Server responds (multiple messages):
    1. Metadata message: {
        "type": "metadata",
        "transcription": "<original text>",
        "translation": "<translated text>"
    }

    2. Audio chunks (one or more): {
        "type": "audio_chunk",
        "data": "<base64-encoded audio chunk>",
        "chunk_index": <int>
    }

    3. Completion message: {
        "type": "complete",
        "total_chunks": <int>,
        "latency_ms": <int>
    }

    4. Error message (if error): {
        "type": "error",
        "error": "<error message>"
    }
    """
    await websocket.accept()
    print(f"✓ Streaming WebSocket client connected from {websocket.client}")

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            request = json.loads(data)

            print(f"\n{'='*60}")
            print(f"📥 Streaming translation: {request.get('source_lang')} → {request.get('target_lang')}")
            start_time = asyncio.get_event_loop().time()

            try:
                # Decode audio
                audio_data = base64.b64decode(request["audio"])
                audio_format = request.get("format", "wav")
                streaming_interval = request.get("streaming_interval", 2.0)

                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix=f".{audio_format}", delete=False) as temp_audio:
                    temp_audio.write(audio_data)
                    temp_audio_path = temp_audio.name

                # Convert to WAV if needed (Whisper requires WAV)
                if audio_format != "wav":
                    import subprocess
                    wav_path = temp_audio_path.replace(f".{audio_format}", ".wav")
                    subprocess.run([
                        "ffmpeg", "-i", temp_audio_path,
                        "-ar", "16000",  # 16kHz sample rate
                        "-ac", "1",      # Mono
                        "-y",            # Overwrite
                        wav_path
                    ], capture_output=True, check=True)
                    # Clean up original file
                    Path(temp_audio_path).unlink(missing_ok=True)
                    temp_audio_path = wav_path

                # Process streaming translation
                chunk_count = 0
                for result in streaming_translation_service.translate_audio_streaming(
                    input_audio=temp_audio_path,
                    source_lang=request["source_lang"],
                    target_lang=request["target_lang"],
                    streaming_interval=streaming_interval
                ):
                    if result["type"] == "metadata":
                        # Send metadata (transcription + translation)
                        await websocket.send_text(json.dumps({
                            "type": "metadata",
                            "transcription": result["transcription"],
                            "translation": result["translation"]
                        }))
                        print(f"   Original: {result['transcription'][:50]}...")
                        print(f"   Translated: {result['translation'][:50]}...")

                    elif result["type"] == "audio_chunk":
                        # Send audio chunk
                        audio_b64 = base64.b64encode(result["data"]).decode('utf-8')
                        await websocket.send_text(json.dumps({
                            "type": "audio_chunk",
                            "data": audio_b64,
                            "chunk_index": result["chunk_index"]
                        }))
                        chunk_count += 1
                        print(f"   📤 Sent chunk {result['chunk_index']}: {len(result['data'])} bytes")

                # Calculate total latency
                latency_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                # Send completion message
                await websocket.send_text(json.dumps({
                    "type": "complete",
                    "total_chunks": chunk_count,
                    "latency_ms": latency_ms
                }))

                print(f"✅ Streaming translation completed in {latency_ms}ms ({chunk_count} chunks)")

                # Cleanup temp files
                Path(temp_audio_path).unlink(missing_ok=True)

            except Exception as e:
                error_msg = str(e)
                print(f"❌ Streaming translation error: {error_msg}")

                await websocket.send_text(json.dumps({
                    "type": "error",
                    "error": error_msg
                }))

    except WebSocketDisconnect:
        print(f"✗ Streaming WebSocket client disconnected")


if __name__ == "__main__":
    import uvicorn

    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║               🎙️  LEVI TRANSLATION SERVICE  🌍            ║
    ║                                                           ║
    ║  Phase 2: WebSocket Server for Cloud Integration         ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        app,
        host="0.0.0.0",  # Listen on all interfaces
        port=8000,
        log_level="info"
    )
