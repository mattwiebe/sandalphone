# Levi - Voice-Driven AI Assistant

A voice-first AI assistant focused on real-time Spanish/English translation, with plans to expand into a full personal assistant for restaurant operations and daily tasks.

## Project Status: Phase 2 - Ready for Deployment! 🚀

**What's Working:**
- ✅ **Phase 1**: Local translation pipeline (STT → Translation → TTS)
- ✅ **Phase 2**: WebSocket server + Telegram bot (ready to deploy!)

**Components:**
- ✅ Whisper.cpp with Metal acceleration (16x real-time on M4 Max)
- ✅ Qwen2.5-7B-Instruct (4-bit quantized) for translation
- ✅ FastAPI WebSocket server for remote access
- ✅ Telegram bot with voice message handling
- ✅ Tailscale setup for secure Mac ↔ Cloud connection

**Performance on M4 Max:**
- **Transcription**: ~500ms for 11s audio (21.8x real-time)
- **Translation**: ~1.5s for typical sentences
- **TTS**: ~200ms (macOS `say` placeholder)
- **WebSocket round-trip**: 2.2s total latency ⚡

**Next Steps:**
1. Set up Tailscale and get your Mac's IP
2. Create Telegram bot via @BotFather
3. Configure and test!

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete setup guide.

## Architecture

```
Current (Local Testing):
[Audio File] → [Whisper STT] → [Qwen Translation] → [TTS] → [Audio Output]
                    ↓                    ↓                ↓
              Metal-accelerated    MLX-optimized    Placeholder (macOS say)
```

```
Planned (Phase 2 - Cloud Integration):
[iPhone] → [Telegram] → [Cloud VPS] → [Cloudflare Tunnel] → [Mac M4 Max]
                                                                    ↓
                                                        [Translation Pipeline]
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
python3 -m venv venv
source venv/bin/activate
```

2. **Install dependencies:**
```bash
brew install cmake ffmpeg cloudflared
pip install fastapi uvicorn websockets vllm-mlx
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
source venv/bin/activate
python mac/src/translation_service.py
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
├── mac/                          # Mac M4 backend
│   ├── src/
│   │   ├── stt/
│   │   │   └── whisper_client.py    # Whisper.cpp wrapper
│   │   ├── llm/
│   │   │   └── translation_client.py # Qwen translation
│   │   ├── tts/
│   │   │   └── qwen_tts_client.py   # TTS client
│   │   └── translation_service.py    # Main pipeline
│   ├── models/
│   │   ├── whisper.cpp/              # Whisper with Metal
│   │   ├── qwen-7b-4bit/             # Translation LLM
│   │   └── qwen3-tts-0.6b/           # TTS model
│   └── config/
├── cloud/                        # Cloud orchestrator (Phase 2)
├── scripts/                      # Setup scripts
├── shared/                       # Shared protocol definitions
└── venv/                         # Python virtual environment
```

## Roadmap

### Phase 1: Local Translation Pipeline ✅ COMPLETE
- [x] Set up Whisper.cpp with Metal
- [x] Download and test Qwen translation model
- [x] Download Qwen3-TTS model
- [x] Create translation service pipeline
- [x] Test end-to-end locally

### Phase 2: Cloud Integration (Next 2 weeks)
- [ ] Create FastAPI WebSocket server on Mac
- [ ] Set up Cloudflare Tunnel
- [ ] Provision Hetzner VPS ($4/month)
- [ ] Create Telegram bot
- [ ] Implement Pipecat voice pipeline
- [ ] Test remote translation via Telegram

### Phase 3: Production (Week 4-5)
- [ ] Add conversation state management
- [ ] Implement audio archival (SQLite + M4A)
- [ ] Add monitoring and health checks
- [ ] Optimize latency (<3 seconds target)
- [ ] Real-world testing with Spanish speakers

### Phase 4: Advanced Features (Future)
- [ ] Voice commands for mode switching
- [ ] MoltBot integration
- [ ] Mac automation with MCP
- [ ] Restaurant operations features

## Technology Stack

- **STT**: Whisper.cpp (base model, Metal-accelerated)
- **Translation**: Qwen2.5-7B-Instruct (MLX 4-bit quantized)
- **TTS**: Qwen3-TTS 0.6B (placeholder: macOS `say`)
- **LLM Runtime**: MLX + vllm-mlx
- **Web Framework**: FastAPI + Uvicorn
- **Cloud**: Hetzner VPS + Cloudflare Tunnel
- **Messaging**: Telegram Bot API

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
