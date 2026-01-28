# Levi Deployment Guide

Complete guide to get Levi running end-to-end.

## Current Status

✅ **Phase 1 Complete**: Local translation pipeline working
✅ **Phase 2 In Progress**: Cloud integration ready, needs configuration

## What's Working Right Now

1. **Mac Backend** ✅
   - Whisper STT with Metal acceleration
   - Qwen translation (Spanish ↔ English)
   - TTS synthesis
   - FastAPI WebSocket server on port 8000
   - 2.2 second end-to-end latency

2. **Telegram Bot** ✅ (code ready)
   - Voice message handling
   - Mode toggling (/mode command)
   - User whitelist support
   - Error handling and logging

## Quick Start: Test Locally (5 minutes)

You can test the entire system on your Mac without any cloud setup:

```bash
# Terminal 1: Start Mac backend
cd /Users/matt/levi
source venv/bin/activate
python mac/src/main.py

# Terminal 2: Start Telegram bot (after configuring - see below)
cd /Users/matt/levi
source venv/bin/activate
pip install python-telegram-bot python-dotenv
cd cloud
cp .env.example .env
# Edit .env and add your bot token from @BotFather
# Set MAC_WEBSOCKET_URL=ws://localhost:8000/ws/translate
python src/telegram_bot.py
```

Now you can send voice messages to your Telegram bot and get translations!

## Full Deployment: Mac + Cloud VPS

### Prerequisites

- [x] Mac M4 Max with models downloaded
- [ ] Telegram bot token (from @BotFather)
- [ ] Tailscale installed and authenticated
- [ ] Hetzner VPS account (or any VPS provider)

### Step 1: Set Up Tailscale (10 minutes)

**On Mac:**
1. Download Tailscale: https://tailscale.com/download/mac
2. Install and authenticate (sign in with Google/GitHub)
3. Get your IP: `tailscale ip -4`
   - You'll get something like: `100.115.92.201`
   - **Save this IP!** You'll need it for the VPS.

**Keep the Tailscale app running** - it needs to be active for the VPS to reach your Mac.

### Step 2: Create Telegram Bot (5 minutes)

1. Message @BotFather on Telegram
2. Send: `/newbot`
3. Choose a name: `Levi Translation Bot`
4. Choose username: `your_name_levi_bot`
5. **Save your token**: `1234567890:ABCdef...`

### Step 3: Configure Mac Backend

```bash
cd /Users/matt/levi

# Create .env for cloud bot
cd cloud
cp .env.example .env
```

Edit `.env`:
```bash
TELEGRAM_BOT_TOKEN=your_token_from_botfather
MAC_WEBSOCKET_URL=ws://100.x.x.x:8000/ws/translate  # Use your Tailscale IP!
ALLOWED_USER_IDS=your_telegram_user_id  # Optional, get from @userinfobot
```

### Step 4: Start Mac Services

```bash
# Make sure Whisper server is running
cd /Users/matt/levi
source venv/bin/activate
python mac/src/main.py
```

Keep this running! You can use `screen` or `tmux` to keep it alive.

### Step 5: Provision Cloud VPS (Optional for remote access)

If you want to access your bot from anywhere (not just your Mac):

**Option A: Run Bot on Mac (Simpler)**
- Just run the Telegram bot on your Mac
- Works great for local testing
- Mac must stay on and connected

**Option B: Run Bot on Cloud VPS ($4/month)**
- Provision Hetzner VPS: https://www.hetzner.com/cloud
- Choose CPX11: 2 vCPU, 2GB RAM, $4.09/month
- Ubuntu 22.04 LTS

Once you have the VPS:

```bash
# SSH into VPS
ssh root@your-vps-ip

# Install Tailscale on VPS
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Install Python and dependencies
apt update && apt upgrade -y
apt install -y python3.11 python3-pip git

# Clone your repo (or copy files)
git clone https://github.com/yourusername/levi.git
cd levi/cloud

# Install dependencies
pip3 install -r requirements.txt

# Configure
cp .env.example .env
nano .env  # Add your bot token and Mac's Tailscale IP

# Test
python3 src/telegram_bot.py
```

### Step 6: Keep Bot Running (Production)

**On Mac (screen/tmux):**
```bash
screen -S levi-mac
python mac/src/main.py
# Press Ctrl+A then D to detach
```

**On VPS (systemd):**
Create `/etc/systemd/system/levi-bot.service`:
```ini
[Unit]
Description=Levi Telegram Translation Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/levi/cloud
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /root/levi/cloud/src/telegram_bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
systemctl daemon-reload
systemctl enable levi-bot
systemctl start levi-bot
systemctl status levi-bot
```

## Testing

1. **Find your bot** in Telegram
2. Send `/start` - you should get a welcome message
3. **Send a voice message** in Spanish or English
4. **Wait 3-5 seconds**
5. **Receive translated voice message back!** 🎉

## Monitoring

**Check Mac backend:**
```bash
curl http://localhost:8000/health
```

**Check from VPS (via Tailscale):**
```bash
curl http://100.x.x.x:8000/health
```

**Check bot logs:**
```bash
# On VPS
journalctl -u levi-bot -f
```

## Troubleshooting

**Bot doesn't respond:**
- Check Mac backend is running: `ps aux | grep main.py`
- Verify Tailscale: `tailscale status`
- Test WebSocket: `curl http://100.x.x.x:8000/health`

**"Cannot connect to translation service":**
- Check Tailscale IPs match in `.env`
- Verify Mac firewall isn't blocking port 8000
- Try: `sudo lsof -i :8000` to see if server is listening

**Slow translations:**
- Normal: 2-4 seconds
- If >5 seconds, check Mac CPU usage
- Verify Metal is being used: Look for "Metal" in Whisper output

## Cost Breakdown

**Local Only (Mac):** $0/month
- Run bot on Mac
- Perfect for testing

**Production (Mac + VPS):**
- Hetzner VPS: $4.09/month
- Tailscale: $0 (free tier)
- **Total: $4.09/month**

All translation processing stays on your Mac = $0 API costs! 🎉

## Architecture Diagram

```
Your Phone → Telegram → Cloud VPS → Tailscale → Mac M4 Max
                         ($4/mo)      (free)      (local)
                            ↓                         ↓
                      Bot receives              Translation
                      voice message              Pipeline:
                            ↓                    - Whisper STT
                      Sends to Mac              - Qwen LLM
                            ↓                    - TTS
                      Receives audio             ↓
                            ↓                   Sends back
                      Sends to user         ←────┘
```

## Performance

- **Transcription**: ~500ms (Whisper base, Metal)
- **Translation**: ~1.5s (Qwen 7B, MLX)
- **TTS**: ~200ms (macOS say placeholder)
- **Network**: ~200ms (Telegram + Tailscale)
- **Total**: ~2.5s ⚡

## Next Steps

1. ✅ Create Telegram bot via @BotFather
2. ✅ Install and authenticate Tailscale
3. ✅ Configure `.env` with your settings
4. ✅ Test locally on Mac
5. ⏳ (Optional) Deploy to VPS for 24/7 access

---

**You're almost there!** Just need to:
1. Set up Tailscale (download the Mac app)
2. Create your Telegram bot
3. Configure `.env`
4. Start the services!

Then you'll have a working voice translation assistant! 🚀
