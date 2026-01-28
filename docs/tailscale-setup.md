# Tailscale Setup for Levi

Tailscale has been installed via Homebrew, but on macOS it works best when set up manually. Here's the simple process:

## Quick Setup (2 minutes)

### Option 1: Using Tailscale GUI (Easiest)

1. **Download the Tailscale app**:
   - Go to: https://tailscale.com/download/mac
   - Download and install the macOS app
   - Or just run: `open https://tailscale.com/download/mac`

2. **Launch Tailscale**:
   - Open the Tailscale app from Applications
   - Click "Log in" in the menu bar
   - Sign in with Google, GitHub, or email (it's fast!)

3. **You're connected!**
   - Tailscale will show your machine's IP in the menu bar
   - It's something like `100.x.x.x`

### Option 2: Command Line Only

If you prefer CLI-only setup:

```bash
# Run tailscaled with sudo (required on macOS)
sudo tailscaled

# In another terminal, connect
sudo tailscale up
```

This will print a URL like:
```
https://login.tailscale.com/a/abc123def
```

Open that URL in your browser to authenticate.

## Get Your Tailscale IP

Once connected, get your Mac's Tailscale IP:

```bash
tailscale ip -4
```

You'll see something like: `100.115.92.201`

**This is your Mac's private VPN IP!** Your cloud VPS will use this to connect to your Mac.

## Test It

With your WebSocket server still running, you can test locally:

```bash
# Start your Levi server (if not already running)
cd /Users/matt/levi
source venv/bin/activate
python mac/src/main.py

# Test via Tailscale IP (replace with your actual IP)
curl http://100.115.92.201:8000/health
```

## Next Steps

Once you have your Tailscale IP (`100.x.x.x`):

1. We'll provision a Hetzner VPS
2. Install Tailscale on the VPS
3. The VPS will be able to reach your Mac at: `ws://100.x.x.x:8000/ws/translate`
4. Build the Telegram bot on the VPS
5. Full remote translation working! 🎉

## Current Status

✅ Tailscale installed on Mac
⏳ Need to authenticate (use GUI app or `sudo tailscale up`)
⏳ Get your Tailscale IP with `tailscale ip -4`

---

**Recommendation**: Just download the Tailscale Mac app from https://tailscale.com/download/mac - it's the easiest way and takes 30 seconds!
