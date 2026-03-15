# Levi - Voice-Driven AI Assistant

A voice-first AI assistant focused on real-time Spanish/English translation, with plans to expand into a full personal assistant for restaurant operations and daily tasks.

## Project Status

The repo has been pivoted toward:

- `Pipecat` as the realtime orchestration layer
- `LiveKit Cloud` as the media plane and SIP integration layer
- the existing `mac/` inference stack behind typed adapters
- private translation as the default listening mode

What is implemented in the codebase now:

- typed STT / translation / TTS adapter boundary
- typed session, transcript, and task event contracts
- Pipecat-facing runtime skeleton for private translation and ambient mode
- LiveKit room policy, participant-role mapping, and reconnect handling
- inbound and outbound SIP domain models on the same room/session shape
- audio policy and basic operability modules
- automated unit / contract / integration coverage for the new runtime surface

What is still transitional:

- the old websocket and Telegram paths still exist in the repo
- the FastAPI server and legacy orchestration have not been fully removed
- LiveKit/Pipecat server connectivity is modeled locally, not fully wired end-to-end yet

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete setup guide.
See [docs/testing.md](docs/testing.md) for the automated test matrix and opt-in integration/hardware suites.

## Architecture

```
[PSTN/SIP Provider] → [LiveKit Cloud] → [LiveKit Room]
                                          ↓
                                [Pipecat Runtime / Policy]
                                          ↓
                            [Typed Translation Adapter Boundary]
                                          ↓
                                   [mac/ inference stack]
```

## Quick Start

### Prerequisites
- Mac with Apple Silicon (M1/M2/M3/M4)
- Python 3.13+
- Homebrew

### Installation

1. **Clone and setup:**
```bash
cd /Users/matt/levi

# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --extra mac
```

2. **Install system dependencies:**
```bash
brew install cmake ffmpeg cloudflared direnv
```

3. **Build Whisper.cpp with Metal:**
```bash
cd mac/models
git clone https://github.com/ggml-org/whisper.cpp
cd whisper.cpp
mkdir build && cd build
cmake .. -DGGML_METAL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build . --config Release -j8
cd .. && bash ./models/download-ggml-model.sh base
```

4. **Download ML models:**
```bash
# Already downloaded:
# - Qwen2.5-7B-Instruct-4bit (mac/models/qwen-7b-4bit)
# - Qwen3-TTS-0.6B-4bit (mac/models/qwen3-tts-0.6b)
```

### Usage

**Test the translation pipeline:**
```bash
uv run --extra mac python mac/src/translation_service.py
```

This will:
1. Transcribe the JFK sample audio (English)
2. Translate to Spanish using Qwen
3. Synthesize Spanish audio
4. Play the result

**Use individual components:**

```python
from stt.whisper_client import WhisperClient
from llm.translation_client import TranslationClient
from tts.qwen_tts_client import QwenTTSClient

# Transcribe audio
stt = WhisperClient()
text = stt.transcribe("audio.wav", language="es")

# Translate
translator = TranslationClient()
translation = translator.translate(text, "es", "en")

# Synthesize
tts = QwenTTSClient()
audio_file = tts.synthesize(translation, language="en")
```

## Project Structure

```
levi/
├── mac/                          # Mac inference backend and adapters
│   ├── src/
│   │   ├── levi_pipeline/            # Typed translation pipeline boundary
│   │   ├── stt/
│   │   ├── llm/
│   │   ├── tts/
│   │   ├── translation_service.py
│   │   └── streaming_translation_service.py
├── cloud/
│   └── src/
│       └── pipecat_app/              # Pipecat/LiveKit-facing runtime surface
├── tests/
│   ├── unit/
│   ├── contract/
│   └── integration/
├── docs/
└── scripts/
```

## Roadmap

### Complete
- [x] Phase 0: test harness, markers, and baseline suite
- [x] Phase 1: typed adapter contracts around the Mac inference stack
- [x] Phase 2: Pipecat-facing runtime skeleton and event contracts
- [x] Phase 3: LiveKit room model, role mapping, and reconnect policy
- [x] Phase 4: inbound SIP session/config model
- [x] Phase 5: outbound SIP session/config model
- [x] Phase 6: audio policy
- [x] Phase 7: operability primitives

### Remaining
- [ ] Phase 8: remove or isolate more legacy orchestration paths
- [ ] wire the runtime to real LiveKit/Pipecat connectivity end to end
- [ ] replace transitional Telegram/websocket paths or move them behind explicit compatibility boundaries
- [ ] add production deployment wiring and real call-flow integration tests

## Technology Stack

- **STT**: Whisper.cpp (base model, Metal-accelerated)
- **Translation**: Qwen2.5-7B-Instruct (MLX 4-bit quantized)
- **TTS**: Qwen3-TTS 0.6B / VibeVoice with fallback support
- **Realtime Orchestration**: Pipecat
- **Media / SIP Plane**: LiveKit Cloud + LiveKit Agents
- **Legacy Compatibility**: FastAPI WebSocket server and Telegram bot

## Cost Breakdown

**Current (Local Only):** $0/month
**Phase 2 (Cloud Integration):**
- Hetzner VPS: $4.09/month
- Cloudflare Tunnel: $0 (free)
- Telegram Bot: $0 (free)
- **Total: ~$4-5/month** (well under $20 budget!)

## Performance Metrics

### M4 Max Benchmarks
- **Whisper base**: 504ms for 11s audio (21.8x real-time)
- **Qwen 7B translation**: ~2-3s per sentence
- **Metal acceleration**: Working perfectly
- **Memory usage**: ~8GB for full pipeline

### Target Latency Goals
- Phase 1 (local): 3-5 seconds ✓
- Phase 2 (cloud): <4 seconds
- Phase 3 (optimized): <3 seconds

## Development Notes

### Lessons Learned
1. **Whisper.cpp Metal build**: Use CMake, not Makefile, for proper Metal support
2. **MLX models**: Download from `mlx-community` for optimized quantized versions
3. **Qwen prompting**: Use ChatML format (`<|im_start|>system...`) for best results
4. **TTS**: Qwen3-TTS requires custom inference code (using macOS `say` as placeholder)

### Next Steps
1. Implement proper Qwen3-TTS inference (replace macOS `say`)
2. Create WebSocket server for remote access
3. Set up Cloudflare Tunnel
4. Build Telegram bot integration

## Contributing

This is a personal project for restaurant operations in Puerto Vallarta, Mexico. The translation features are specifically tuned for Mexican Spanish.

## License

Private project - All rights reserved

---

**Built with Claude Code** 🤖
*Making Star Trek's Universal Translator a reality, one taco at a time.*
