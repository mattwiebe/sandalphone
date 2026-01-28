# Setting Up the Telegram Bot

## Quick Setup (5 minutes)

### 1. Create Your Bot with BotFather

1. **Open Telegram** on your phone or https://web.telegram.org

2. **Find BotFather**:
   - Search for `@BotFather` in Telegram
   - Or open: https://t.me/BotFather

3. **Create a new bot**:
   ```
   /newbot
   ```

4. **Choose a name** (what users will see):
   ```
   Levi Translation Bot
   ```

5. **Choose a username** (must end in 'bot'):
   ```
   levi_translation_bot
   ```
   (Try variations if taken: `levi_translate_bot`, `your_name_levi_bot`, etc.)

6. **Save your token**:
   BotFather will give you a token like:
   ```
   1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
   **Keep this secret!** This is your bot's password.

### 2. Configure the Bot

1. **Copy the environment file**:
   ```bash
   cd /Users/matt/levi/cloud
   cp .env.example .env
   ```

2. **Edit `.env`** and add your token:
   ```bash
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
   MAC_WEBSOCKET_URL=ws://100.x.x.x:8000/ws/translate  # Your Tailscale IP
   ```

3. **Optional - Restrict access** (recommended):
   ```bash
   # Get your Telegram user ID by messaging @userinfobot
   ALLOWED_USER_IDS=123456789,987654321
   ```

### 3. Test Locally

You can test the bot on your Mac before deploying to the cloud:

```bash
cd /Users/matt/levi
source venv/bin/activate

# Install Telegram bot dependencies
pip install python-telegram-bot python-dotenv

# Make sure your Mac WebSocket server is running
# In another terminal:
python mac/src/main.py

# Run the Telegram bot
cd cloud
python src/telegram_bot.py
```

Now open Telegram, find your bot, and try:
- `/start` - Get welcome message
- Send a voice message - Get it translated!

## Bot Commands

Once your bot is running, users can:

- `/start` - Start the bot and see instructions
- `/help` - Get help
- `/mode` - Toggle between Spanish→English and English→Spanish
- `/status` - Check if the translation service is online
- **Send voice message** - Get translation!

## Deploying to Cloud (Phase 2b)

Once you're ready to deploy to a VPS:

1. Provision Hetzner VPS (see `docs/hetzner-setup.md`)
2. Install Tailscale on VPS
3. Copy bot code to VPS
4. Install dependencies: `pip install -r cloud/requirements.txt`
5. Set up `.env` with your bot token and Mac's Tailscale IP
6. Run with supervisor/systemd to keep it running

## Troubleshooting

**Bot doesn't respond:**
- Check that `mac/src/main.py` is running
- Verify your Tailscale IP is correct in `.env`
- Check logs for errors

**"Cannot connect to translation service":**
- Verify Tailscale is running on Mac: `tailscale status`
- Test WebSocket manually: `curl http://100.x.x.x:8000/health`
- Check firewall isn't blocking port 8000

**Voice messages not working:**
- Make sure you installed `python-telegram-bot` correctly
- Check the bot has permission to receive voice messages
- Verify `.env` file is loaded (try printing `os.getenv('TELEGRAM_BOT_TOKEN')`)

## Security Notes

- **Never commit `.env` to git!** (it's in `.gitignore`)
- Use `ALLOWED_USER_IDS` to restrict who can use your bot
- Your bot token is like a password - keep it secret
- Regenerate token via @BotFather if it leaks

---

**Next Steps:**
1. Create your bot with @BotFather
2. Test locally on Mac
3. Deploy to cloud VPS when ready!
