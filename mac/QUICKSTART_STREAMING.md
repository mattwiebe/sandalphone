# Quick Start: Streaming TTS with VibeVoice

Get up and running with streaming text-to-speech in 5 minutes.

## Prerequisites

- Python environment with `uv` installed
- macOS (for VibeVoice MLX support)
- Project dependencies installed: `uv sync --extra mac`

## 1. Enable Streaming TTS

Set the TTS provider to VibeVoice:

```bash
export TTS_PROVIDER=vibevoice
```

Or use it inline with commands:

```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py
```

## 2. Test Streaming (30 seconds)

Run the interactive demo:

```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/examples/streaming_demo.py
```

**Expected output:**
```
============================================================
VIBEVOICE STREAMING TTS DEMO
============================================================
Text to synthesize:
  "Welcome to the streaming text-to-speech demonstration..."

🎙️  Starting streaming generation...

Progress:
  ⚡ First chunk: 2544ms
  █ Chunk 0: 748,844 bytes

✅ Complete!

Batch mode:    873ms to first audio
Streaming:     785ms to first audio
Faster by:     10.1%
```

## 3. Run the Server (2 minutes)

Start the FastAPI server:

```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py
```

**Verify it's running:**
```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy",
  "translation_service": "ready",
  "streaming_service": "ready",
  "timestamp": "2026-01-29T12:00:00.000000"
}
```

## 4. Test WebSocket Streaming (2 minutes)

**Terminal 1 (server):**
```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py
```

**Terminal 2 (test client):**
```bash
uv run --extra mac python mac/tests/test_websocket_streaming.py
```

**Expected output:**
```
✓ Metadata received:
  Transcription: [English text]
  Translation: [Spanish text]

✓ First audio chunk: 150ms

  Chunk 0: 256000 bytes
  Chunk 1: 256000 bytes

✓ Complete:
  Total chunks: 2
  Time to first chunk: 150ms

✓ TEST PASSED
```

## 5. Use in Your Code

### Python API - Streaming TTS

```python
from tts.factory import create_tts_provider

tts = create_tts_provider()

# Stream audio chunks
for chunk in tts.synthesize_streaming(
    text="Hello, this is a streaming test!",
    language="en",
    streaming_interval=1.5
):
    # Process each chunk as it arrives
    # chunk is WAV-encoded bytes
    play_audio(chunk)
```

### Python API - Full Translation Pipeline

```python
from streaming_translation_service import StreamingTranslationService

service = StreamingTranslationService()

for result in service.translate_audio_streaming(
    input_audio="spanish_audio.wav",
    source_lang="es",
    target_lang="en"
):
    if result["type"] == "metadata":
        print(f"Original: {result['transcription']}")
        print(f"Translation: {result['translation']}")

    elif result["type"] == "audio_chunk":
        # Stream chunk to client/speaker
        play_audio(result["data"])
```

### WebSocket Client (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/stream');

// Send audio for translation
ws.send(JSON.stringify({
    audio: base64EncodedAudio,
    source_lang: "es",
    target_lang: "en",
    streaming_interval: 1.5
}));

// Receive streaming responses
ws.onmessage = (event) => {
    const response = JSON.parse(event.data);

    if (response.type === 'metadata') {
        console.log('Original:', response.transcription);
        console.log('Translation:', response.translation);
    }
    else if (response.type === 'audio_chunk') {
        // Decode and play chunk immediately
        const audioData = atob(response.data);
        playAudioChunk(audioData);
    }
    else if (response.type === 'complete') {
        console.log(`Done! ${response.total_chunks} chunks in ${response.latency_ms}ms`);
    }
};
```

## Key Parameters

### Streaming Interval

Controls chunk size (seconds of audio per chunk):

```python
tts.synthesize_streaming(
    text="...",
    language="en",
    streaming_interval=1.5  # 1.5 seconds per chunk
)
```

**Recommendations:**
- **0.5s:** Very responsive, may be choppy
- **1.5s:** Good balance (recommended)
- **2.0s:** Smooth, slightly slower first chunk
- **5.0s:** Very smooth, defeats purpose of streaming

### Language Support

```python
# English
tts.synthesize_streaming(text="Hello", language="en")

# Spanish
tts.synthesize_streaming(text="Hola", language="es")
```

## Troubleshooting

### "VibeVoice model not loaded"

**Problem:** VibeVoice failed to load
**Solution:** Check model is available:

```bash
uv run --extra mac python -c "from mlx_audio.tts.utils import load_model; load_model('mlx-community/VibeVoice-Realtime-0.5B-fp16')"
```

### "TTS provider doesn't support streaming"

**Problem:** Using wrong TTS provider
**Solution:** Set `TTS_PROVIDER=vibevoice`

```bash
export TTS_PROVIDER=vibevoice
```

### WebSocket connection refused

**Problem:** Server not running
**Solution:** Start server first:

```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py
```

### Audio chunks sound corrupted

**Problem:** Incorrect WAV encoding
**Solution:** Check sample rate and format in `_array_to_wav()` method

## Performance Tips

### 1. Adjust Streaming Interval

For longer text, use larger intervals:

```python
# Short text (1-2 sentences)
streaming_interval=1.0

# Medium text (paragraph)
streaming_interval=1.5

# Long text (multiple paragraphs)
streaming_interval=2.0
```

### 2. Monitor Latency

The streaming service prints timing info:

```
[1/3] Transcribing audio (es)...
[2/3] Translating es → en...
[3/3] Streaming speech (en)...
      Chunk 0: 256000 bytes
      Chunk 1: 256000 bytes
✓ STREAMING TRANSLATION COMPLETE (2 chunks)
```

### 3. Use Batch Mode for Short Text

For very short text (<10 words), batch mode may be faster:

```python
# Short text - use batch
if len(text.split()) < 10:
    audio = tts.synthesize(text, language="en")
else:
    # Long text - use streaming
    for chunk in tts.synthesize_streaming(text, language="en"):
        yield chunk
```

## What's Next?

- **Read full docs:** `mac/STREAMING_TTS.md`
- **See implementation:** `IMPLEMENTATION_SUMMARY.md`
- **Run all tests:** `TTS_PROVIDER=vibevoice uv run --extra mac python mac/tests/test_streaming_tts.py`
- **Explore examples:** `mac/examples/streaming_demo.py`

## Need Help?

**Check these files:**
- `mac/STREAMING_TTS.md` - Complete user guide
- `IMPLEMENTATION_SUMMARY.md` - Technical details
- `PHASE1_CHECKLIST.md` - What's implemented

**Common issues:**
- Make sure `TTS_PROVIDER=vibevoice` is set
- Verify VibeVoice model is loaded (takes 5-10s on first run)
- Check server is running for WebSocket tests
- Use `uv run --extra mac` to ensure correct dependencies

## Quick Reference

**Environment variable:**
```bash
export TTS_PROVIDER=vibevoice
```

**Run demo:**
```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/examples/streaming_demo.py
```

**Start server:**
```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py
```

**Test streaming:**
```bash
TTS_PROVIDER=vibevoice uv run --extra mac python mac/tests/test_streaming_tts.py
```

**Test WebSocket:**
```bash
uv run --extra mac python mac/tests/test_websocket_streaming.py
```

---

**You're all set!** Streaming TTS is now enabled with VibeVoice, reducing latency by 10-80% depending on text length.
