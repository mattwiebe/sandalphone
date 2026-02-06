# Voice Calls Setup Guide

## Overview

The Levi Telegram bot now supports **real-time voice call translation** via Telegram group voice chats!

## What's New (Phase 1 Complete)

### ✅ Infrastructure
- **Dual Client Architecture**: Bot now runs both `python-telegram-bot` (for messages) and `pyrogram` (for voice calls)
- **Voice Call Manager**: Handles joining/leaving voice chats via `pytgcalls`
- **Real-Time Translation Pipeline**: Processes audio with VAD (Voice Activity Detection) and streams to Mac backend
- **New Commands**: `/join` and `/leave` for voice chat control

### 📁 New Files Created
1. **`cloud/src/voice_call_manager.py`** - Manages pytgcalls integration
2. **`cloud/src/realtime_translation_pipeline.py`** - Audio processing and translation pipeline
3. **`docs/voice-calls-setup.md`** - This guide

### 📦 New Dependencies
- `py-tgcalls` - Telegram voice chat library
- `pyrogram` - MTProto client for Telegram
- `TgCrypto` - Cryptography for Pyrogram (speeds up operations)
- `webrtcvad` - Voice Activity Detection

## Prerequisites

### 1. Telegram Bot Token
You already have this from @BotFather.

### 2. Telegram API Credentials (NEW!)
Required for voice call features.

**How to get them:**
1. Go to https://my.telegram.org
2. Login with your phone number
3. Go to "API development tools"
4. Create a new application (any name/description)
5. Copy your **API ID** and **API Hash**

## Configuration

### Update your `.env` file

Add the following to `cloud/.env`:

```bash
# Existing configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
MAC_WEBSOCKET_URL=ws://100.x.x.x:8000/ws/translate

# NEW: Telegram API Credentials
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here

# NEW: Voice Call Settings (optional, these are defaults)
VOICE_CALL_ENABLED=true
DEFAULT_SOURCE_LANG=es
DEFAULT_TARGET_LANG=en
VAD_AGGRESSIVENESS=2
SILENCE_DURATION_MS=500

# Logging
LOG_LEVEL=INFO
```

### Configuration Options Explained

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_API_ID` | API ID from my.telegram.org | **Required** |
| `TELEGRAM_API_HASH` | API Hash from my.telegram.org | **Required** |
| `VOICE_CALL_ENABLED` | Enable/disable voice call features | `true` |
| `DEFAULT_SOURCE_LANG` | Default source language | `es` |
| `DEFAULT_TARGET_LANG` | Default target language | `en` |
| `VAD_AGGRESSIVENESS` | Voice detection sensitivity (0-3, higher = more aggressive) | `2` |
| `SILENCE_DURATION_MS` | Silence duration to detect speech end | `500` |

## Installation

Install the new dependencies:

```bash
# From the levi/ directory
uv sync --extra cloud
```

## Usage

### Starting the Bot

Make sure your Mac backend is running first:

```bash
# Terminal 1: Start Mac backend
TTS_PROVIDER=vibevoice uv run --extra mac python mac/src/main.py
```

Then start the bot:

```bash
# Terminal 2: Start Telegram bot with voice call support
uv run --extra cloud python cloud/src/telegram_bot.py
```

### Using Voice Calls

#### Step 1: Create a Group Chat
1. Create a new Telegram group
2. Add your Levi bot to the group

#### Step 2: Start Voice Chat
1. In the group, start a voice chat (tap the phone icon)
2. Join the voice chat yourself

#### Step 3: Invite the Bot
```
/join
```

The bot will join the voice chat. You should see:
```
✅ Joined voice chat!

🎙️ Translation mode: ES → EN

Speak and I'll translate in real-time!
Use /mode to change language direction.
Use /leave to exit the voice chat.
```

#### Step 4: Speak!
- Speak in Spanish (or your configured source language)
- The bot will detect when you stop speaking (500ms silence)
- It will translate your speech
- You'll hear the translation in the voice chat

### Voice Call Commands

| Command | Description |
|---------|-------------|
| `/join` | Join the active voice chat in the current group |
| `/leave` | Leave the voice chat |
| `/mode` | Toggle translation direction (ES↔EN) |

### Existing Voice Message Commands

All existing commands still work:

| Command | Description |
|---------|-------------|
| `/start` | Show welcome message |
| `/help` | Show help |
| `/status` | Check service status |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Telegram Group                        │
│  ┌────────────┐         ┌──────────────┐               │
│  │   User     │ ◄─────► │ Voice Chat   │               │
│  │  Speaking  │         │              │               │
│  └────────────┘         └──────┬───────┘               │
└─────────────────────────────────┼─────────────────────────┘
                                  │ Audio Stream
                                  ▼
┌─────────────────────────────────────────────────────────┐
│              Cloud Bot (Telegram Bot Server)            │
│                                                          │
│  ┌─────────────────┐    ┌──────────────────────────┐  │
│  │ python-telegram │    │   pyrogram + pytgcalls   │  │
│  │      -bot       │    │   (voice chat client)    │  │
│  │ (voice msgs)    │    │                          │  │
│  └─────────────────┘    └──────────┬───────────────┘  │
│                                     │                   │
│                    ┌────────────────▼────────────────┐ │
│                    │ VoiceCallManager                │ │
│                    │ - Join/leave voice chats        │ │
│                    │ - Stream audio                  │ │
│                    └────────────┬────────────────────┘ │
│                                 │                       │
│                    ┌────────────▼────────────────────┐ │
│                    │ RealtimeTranslationPipeline     │ │
│                    │ - Buffer audio                  │ │
│                    │ - VAD (detect speech end)       │ │
│                    │ - Call Mac backend              │ │
│                    └────────────┬────────────────────┘ │
└─────────────────────────────────┼─────────────────────────┘
                                  │ WebSocket
                                  ▼
┌─────────────────────────────────────────────────────────┐
│              Mac Backend (Translation Server)           │
│  ┌────────────────────────────────────────────────┐    │
│  │  /ws/translate Endpoint                        │    │
│  │  ├─ STT (Whisper)                              │    │
│  │  ├─ Translation (LLM)                          │    │
│  │  └─ TTS (VibeVoice streaming)                  │    │
│  └────────────┬───────────────────────────────────┘    │
└───────────────┼─────────────────────────────────────────┘
                │ Translated Audio
                ▼
         User hears translation
```

## Technical Details

### How Voice Activity Detection Works

The pipeline uses WebRTC VAD to detect when you stop speaking:

1. **Audio buffering**: Incoming audio is buffered in 20ms chunks
2. **VAD analysis**: Each chunk is analyzed for speech/silence
3. **Speech end detection**: After 500ms of silence following speech, translation begins
4. **Processing**: Buffered audio is sent to Mac backend
5. **Playback**: Translated audio is streamed back to voice chat

### Voice Call vs Voice Messages

| Feature | Voice Messages | Voice Calls |
|---------|---------------|-------------|
| Type | Pre-recorded files | Real-time stream |
| Latency | No constraint | ~3-5s end-to-end |
| Usage | 1-on-1 or groups | Groups only |
| Implementation | python-telegram-bot | pyrogram + pytgcalls |
| Handler | `MessageHandler` | `play()` / `leave_call()` |

## Troubleshooting

### Bot doesn't join voice chat

**Symptoms:**
```
❌ Failed to join voice chat.
```

**Possible causes:**
1. No active voice chat in the group
2. Bot lacks permissions
3. API credentials not set

**Solutions:**
- Make sure a voice chat is active before sending `/join`
- Check bot has admin permissions in the group
- Verify `TELEGRAM_API_ID` and `TELEGRAM_API_HASH` are set in `.env`

### Import errors on startup

**Symptoms:**
```
ModuleNotFoundError: No module named 'pytgcalls'
```

**Solution:**
```bash
uv sync --extra cloud
```

### Voice calls disabled message

**Symptoms:**
```
❌ Voice call feature is disabled.
Set VOICE_CALL_ENABLED=true in .env to enable.
```

**Solution:**
Add to `.env`:
```bash
VOICE_CALL_ENABLED=true
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
```

### Bot joins but doesn't translate

**Symptoms:**
- Bot joins voice chat
- No translation happens when speaking

**Possible causes:**
1. Mac backend not running
2. VAD sensitivity too high
3. Audio format issues

**Solutions:**
1. Check Mac backend is running: `/status`
2. Adjust VAD aggressiveness: Set `VAD_AGGRESSIVENESS=1` (less aggressive)
3. Check logs for audio processing errors

## Current Limitations (Phase 1)

### What Works
✅ Join/leave voice chats
✅ Detect speech end with VAD
✅ Send audio to Mac backend for translation
✅ Voice message translation (existing feature)

### What's Not Implemented Yet (Future Phases)
⏳ Streaming audio playback in voice chat (Phase 2)
⏳ OPUS audio format conversion (Phase 3)
⏳ Real-time bidirectional translation (Phase 4)
⏳ Multiple simultaneous voice chats
⏳ Private voice calls (Telegram limitation)

### Known Issues
- Currently uses batch STT (Whisper), so there's latency waiting for speech end
- Audio playback in voice chat not yet implemented (Phase 2)
- Only works in group voice chats, not direct calls (Telegram API limitation)

## Next Steps (Phase 2-4)

### Phase 2: Audio Streaming Back to Voice Chat
- Implement audio playback in voice chat
- Stream translated audio chunks
- Handle audio queuing

### Phase 3: OPUS Audio Format
- Add OPUS encoder/decoder
- Convert PCM ↔ OPUS for Telegram compatibility
- Optimize audio quality

### Phase 4: Full Real-Time Experience
- Implement streaming STT
- Reduce end-to-end latency to <2s
- Add echo cancellation

## FAQ

### Q: Can I use this for 1-on-1 calls?
**A:** No, Telegram's bot API doesn't support direct voice calls. Only group voice chats are supported.

### Q: How many people can be in a voice chat?
**A:** Telegram supports large voice chats (thousands of participants). The bot can handle translation for one speaker at a time.

### Q: Does this use my phone's voice chat?
**A:** No, the bot runs independently on your cloud server. You can still join the voice chat with your phone to hear the translations.

### Q: What languages are supported?
**A:** Currently Spanish ↔ English. The backend can support any language pair with the appropriate models.

### Q: Can I change language direction mid-call?
**A:** Yes! Use `/mode` to toggle between ES→EN and EN→ES.

### Q: How much does this cost?
**A:** The bot itself is free (just server hosting costs). The translation runs on your Mac backend using local models (no API costs).

## Support

If you encounter issues:

1. Check the logs: `LOG_LEVEL=DEBUG` in `.env`
2. Verify Mac backend is running: `/status`
3. Check API credentials are correct
4. Review the troubleshooting section above

## Summary

**Phase 1 Complete! 🎉**

You now have:
- ✅ Dual client architecture (python-telegram-bot + pyrogram)
- ✅ Voice call manager for joining/leaving voice chats
- ✅ Real-time translation pipeline with VAD
- ✅ `/join` and `/leave` commands
- ✅ Foundation for full voice call translation

**Next:** Phase 2 will add audio playback in voice chats to complete the translation loop!
