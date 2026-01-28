# Setting Up Remote Access to Mac

You have two options for securely exposing your Mac to the cloud VPS:

## Option 1: Cloudflare Tunnel (Recommended - FREE)

### Why Cloudflare Tunnel?
- ✅ 100% Free
- ✅ No port forwarding needed
- ✅ Automatic TLS encryption
- ✅ Survives IP changes
- ✅ Built-in DDoS protection

### Setup Steps:

1. **Create Cloudflare Account** (if you don't have one):
   - Go to: https://dash.cloudflare.com/sign-up
   - Sign up for free account
   - No credit card required!

2. **Authenticate cloudflared**:
   ```bash
   cloudflared tunnel login
   ```
   This will open a browser where you authorize the tunnel.

3. **Create the tunnel**:
   ```bash
   cloudflared tunnel create levi-mac
   ```
   This creates a tunnel named "levi-mac" and saves credentials to `~/.cloudflared/`

4. **Configure the tunnel**:
   Create `~/.cloudflared/config.yml`:
   ```yaml
   tunnel: levi-mac
   credentials-file: /Users/matt/.cloudflared/<TUNNEL-ID>.json

   ingress:
     - hostname: levi.yourdomain.com  # Optional: use a custom domain
       service: http://localhost:8000
     - service: http_status:404
   ```

   Or for no domain (just use tunnel URL):
   ```yaml
   tunnel: levi-mac
   credentials-file: /Users/matt/.cloudflared/<TUNNEL-ID>.json

   ingress:
     - service: http://localhost:8000
   ```

5. **Run the tunnel**:
   ```bash
   cloudflared tunnel run levi-mac
   ```

6. **Get your tunnel URL**:
   ```bash
   cloudflared tunnel info levi-mac
   ```

### Keep Tunnel Running (Production):

Use macOS launchd to keep it running automatically:

```bash
# Install as service
sudo cloudflared service install

# Start the service
sudo launchctl start com.cloudflare.cloudflared
```

---

## Option 2: Tailscale (Alternative - FREE, Simpler)

### Why Tailscale?
- ✅ Even simpler than Cloudflare
- ✅ Free for personal use (up to 100 devices)
- ✅ Peer-to-peer WireGuard VPN
- ✅ No domain needed
- ✅ Works great for Mac ↔ VPS connection

### Setup Steps:

1. **Create Tailscale Account**:
   - Go to: https://login.tailscale.com/start
   - Sign up with Google/GitHub (super quick!)

2. **Install on Mac**:
   ```bash
   brew install tailscale
   sudo tailscale up
   ```
   Follow the browser prompt to authenticate.

3. **Install on Cloud VPS** (later):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   sudo tailscale up
   ```

4. **Get your Mac's Tailscale IP**:
   ```bash
   tailscale ip -4
   ```
   You'll get something like `100.x.x.x`

5. **Connect from VPS**:
   Your VPS can now reach your Mac at:
   ```
   http://100.x.x.x:8000/ws/translate
   ```

### Advantages of Tailscale:
- No configuration files needed
- Direct peer-to-peer connection (lower latency)
- Works even if Mac changes networks
- Can use from phone, laptop, anywhere

---

## Option 3: ngrok (Quick Testing - FREE tier limited)

If you just want to test quickly without creating accounts:

```bash
# Install ngrok
brew install ngrok

# Run tunnel
ngrok http 8000
```

You'll get a public URL like: `https://abc123.ngrok.io`

**Note**: Free tier has limitations and URLs change on restart. Good for testing, not production.

---

## Recommendation

**For Levi, I recommend Tailscale** because:
1. Simpler setup (no config files)
2. Better for Mac ↔ VPS use case
3. Lower latency (peer-to-peer)
4. No domain name needed

**Use Cloudflare if**:
- You want a custom domain
- You need it accessible from non-Tailscale devices
- You want built-in analytics

---

## Current Status

Your Mac WebSocket server is running on:
- **Local**: `ws://localhost:8000/ws/translate`
- **Remote**: Need to set up tunnel first!

Choose your preferred option above and we'll set it up! 🚀
