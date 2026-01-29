# Levi Service Management

Levi is now set up to run automatically on your Mac with auto-restart capabilities.

## Service Manager

Use the convenient service manager script:

```bash
# Check if services are running
./scripts/manage-services.sh status

# Start services
./scripts/manage-services.sh start

# Stop services
./scripts/manage-services.sh stop

# Restart services
./scripts/manage-services.sh restart

# View recent logs
./scripts/manage-services.sh logs

# Follow logs in real-time
./scripts/manage-services.sh follow
```

## What's Running

Two services are managed by macOS launchd:

1. **Mac Backend** (`com.levi.mac-backend`)
   - Runs the translation service (Whisper + Qwen 14B + TTS)
   - Listens on `http://0.0.0.0:8000` for WebSocket connections
   - Accessible via Tailscale at `ws://100.70.223.105:8000/ws/translate`

2. **Telegram Bot** (`com.levi.telegram-bot`)
   - Handles incoming voice messages from Telegram
   - Connects to Mac backend for processing
   - Auto-restarts if it crashes

## Auto-Start & Auto-Restart

Services are configured to:
- ✅ Start automatically when you log in (`RunAtLoad`)
- ✅ Restart automatically if they crash (`KeepAlive`)
- ✅ Wait 10 seconds between restart attempts (`ThrottleInterval`)

## Logs

Logs are stored in `/Users/matt/levi/logs/`:
- `mac-backend.log` - Mac backend stdout
- `mac-backend.error.log` - Mac backend errors
- `telegram-bot.log` - Telegram bot stdout
- `telegram-bot.error.log` - Telegram bot errors

## Manual Management (Advanced)

If you need to manually manage launchd services:

```bash
# Load services
launchctl load ~/Library/LaunchAgents/com.levi.mac-backend.plist
launchctl load ~/Library/LaunchAgents/com.levi.telegram-bot.plist

# Unload services
launchctl unload ~/Library/LaunchAgents/com.levi.mac-backend.plist
launchctl unload ~/Library/LaunchAgents/com.levi.telegram-bot.plist

# View service status
launchctl list | grep levi
```

## Testing End-to-End

1. Send a voice message to your Telegram bot
2. Levi will transcribe, translate, and respond with translated audio
3. Check status: `./scripts/manage-services.sh status`
4. View logs: `./scripts/manage-services.sh logs`

## Troubleshooting

**Services not starting?**
```bash
# Check launchd logs
log show --predicate 'subsystem == "com.apple.launchd"' --last 5m | grep levi
```

**Need to update the code?**
```bash
# Restart services to pick up changes
./scripts/manage-services.sh restart
```

**Clear old processes**
```bash
# Kill any stray processes
pkill -f "python.*main.py"
pkill -f "python.*telegram_bot.py"

# Then restart services
./scripts/manage-services.sh start
```

## 24/7 Operation

To keep Levi running 24/7:
1. ✅ Services are already configured to auto-start
2. Keep your Mac powered on
3. Disable sleep for network services:
   ```bash
   sudo pmset -a tcpkeepalive 1
   ```
4. (Optional) Enable "Wake for network access" in System Preferences > Energy

Levi will now be available from your iPhone via Telegram anytime, anywhere! 🎉
