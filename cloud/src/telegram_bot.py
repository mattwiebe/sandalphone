"""
Telegram bot for Levi translation service.
Receives voice messages, sends to Mac backend, returns translated audio.
"""

import os
import asyncio
import json
import base64
import logging
from pathlib import Path
from io import BytesIO

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import websockets
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
)
logger = logging.getLogger(__name__)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MAC_WEBSOCKET_URL = os.getenv("MAC_WEBSOCKET_URL", "ws://localhost:8000/ws/translate")
ALLOWED_USER_IDS = (
    os.getenv("ALLOWED_USER_IDS", "").split(",")
    if os.getenv("ALLOWED_USER_IDS")
    else []
)

# User state management (simple in-memory for now)
user_states = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")

    welcome_message = f"""
🎙️ **Welcome to Levi Translation Service!** 🌍

Hi {user.first_name}! I can help you translate between Spanish and English.

**How to use:**
1. Send me a voice message in Spanish or English
2. I'll transcribe it
3. Translate it to the other language
4. Send you back a voice message with the translation!

**Commands:**
/start - Show this message
/help - Get help
/mode - Toggle translation mode (ES→EN or EN→ES)
/status - Check service status

**Current mode:** Spanish → English

Try sending me a voice message! 🎤
    """

    await update.message.reply_text(welcome_message, parse_mode="Markdown")

    # Initialize user state
    user_states[user.id] = {"source_lang": "es", "target_lang": "en"}


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = """
**Levi Translation Service Help** 📖

**Available Commands:**
/start - Start the bot and see welcome message
/help - Show this help message
/mode - Toggle between ES→EN and EN→ES
/status - Check if the service is running

**How it works:**
1. Record a voice message in Telegram
2. Send it to me
3. I'll translate it and send back a voice message

**Supported languages:**
- Spanish (Español)
- English

**Tips:**
- Speak clearly for best transcription
- Works best with 5-30 second voice messages
- Background noise may affect accuracy

Need more help? Contact the developer!
    """
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def toggle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mode command to toggle translation direction."""
    user_id = update.effective_user.id

    # Get or initialize user state
    if user_id not in user_states:
        user_states[user_id] = {"source_lang": "es", "target_lang": "en"}

    # Toggle mode
    current_state = user_states[user_id]
    if current_state["source_lang"] == "es":
        current_state["source_lang"] = "en"
        current_state["target_lang"] = "es"
        new_mode = "English → Spanish 🇨🇦 → 🇪🇸"
    else:
        current_state["source_lang"] = "es"
        current_state["target_lang"] = "en"
        new_mode = "Spanish → English 🇪🇸 → 🇨🇦"

    await update.message.reply_text(
        f"Translation mode changed to:\n**{new_mode}**", parse_mode="Markdown"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command to check service health."""
    try:
        # Try to connect to Mac backend
        async with websockets.connect(MAC_WEBSOCKET_URL, open_timeout=5) as ws:
            status_msg = "✅ **Service Status: Online**\n\nMac backend is reachable and ready for translations!"
    except Exception as e:
        status_msg = f"❌ **Service Status: Offline**\n\nCannot reach Mac backend.\nError: {str(e)}"

    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages."""
    user = update.effective_user
    user_id = user.id

    # Check if user is allowed (if whitelist is configured)
    if ALLOWED_USER_IDS and str(user_id) not in ALLOWED_USER_IDS:
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        await update.message.reply_text(
            "Sorry, you are not authorized to use this bot."
        )
        return

    # Get user state
    if user_id not in user_states:
        user_states[user_id] = {"source_lang": "es", "target_lang": "en"}

    state = user_states[user_id]
    source_lang = state["source_lang"]
    target_lang = state["target_lang"]

    logger.info(
        f"Received voice message from {user.username} ({user_id}), mode: {source_lang}→{target_lang}"
    )

    # Send "processing" message
    processing_msg = await update.message.reply_text(
        f"🎙️ Processing your voice message...\n"
        f"Mode: {source_lang.upper()} → {target_lang.upper()}"
    )

    try:
        # Download voice message
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)

        # Download to BytesIO
        voice_data = BytesIO()
        await file.download_to_memory(voice_data)
        voice_data.seek(0)

        # Encode as base64
        audio_b64 = base64.b64encode(voice_data.read()).decode("utf-8")

        # Send to Mac backend via WebSocket
        logger.info(f"Connecting to Mac backend at {MAC_WEBSOCKET_URL}")

        async with websockets.connect(
            MAC_WEBSOCKET_URL,
            open_timeout=10,
            close_timeout=10,
            ping_timeout=60,  # Keep connection alive for up to 60 seconds
            ping_interval=20,  # Send ping every 20 seconds
        ) as ws:
            # Send translation request
            request = {
                "audio": audio_b64,
                "source_lang": source_lang,
                "target_lang": target_lang,
                "format": "ogg",  # Telegram voice messages are OGG
            }

            await ws.send(json.dumps(request))

            # Update status
            await processing_msg.edit_text(
                f"🎙️ Voice received!\n"
                f"⏳ Translating {source_lang.upper()} → {target_lang.upper()}..."
            )

            # Receive response
            response_str = await ws.recv()
            response = json.loads(response_str)

        if response["status"] == "success":
            # Decode translated audio
            translated_audio = base64.b64decode(response["audio"])

            # Send as voice message
            await update.message.reply_voice(
                voice=BytesIO(translated_audio),
                caption=f"✅ Translation ({source_lang.upper()}→{target_lang.upper()}):\n\n"
                f"**Original:** {response['transcription']}\n\n"
                f"**Translation:** {response['translation']}\n\n"
                f"⚡ Latency: {response['latency_ms']}ms",
                parse_mode="Markdown",
            )

            # Delete processing message
            await processing_msg.delete()

            logger.info(
                f"Translation successful for user {user_id}, latency: {response['latency_ms']}ms"
            )

        else:
            error_msg = response.get("error", "Unknown error")
            await processing_msg.edit_text(f"❌ Translation failed:\n{error_msg}")
            logger.error(f"Translation failed for user {user_id}: {error_msg}")

    except websockets.exceptions.WebSocketException as e:
        await processing_msg.edit_text(
            "❌ Cannot connect to translation service.\n"
            "Please try again later or contact support."
        )
        logger.error(f"WebSocket error: {e}")

    except Exception as e:
        await processing_msg.edit_text(f"❌ An error occurred:\n{str(e)}")
        logger.error(f"Error processing voice message: {e}", exc_info=True)


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set in environment!")
        print("\n❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("\nPlease:")
        print("1. Create a Telegram bot via @BotFather")
        print("2. Copy .env.example to .env")
        print("3. Add your bot token to .env")
        print("\nSee docs/telegram-setup.md for details.\n")
        return

    logger.info(f"Starting Levi Telegram Bot...")
    logger.info(f"Mac backend URL: {MAC_WEBSOCKET_URL}")
    if ALLOWED_USER_IDS:
        logger.info(f"User whitelist enabled: {ALLOWED_USER_IDS}")

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mode", toggle_mode))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Start bot
    logger.info("✅ Bot started! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          🤖  LEVI TELEGRAM TRANSLATION BOT  🌍            ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    main()
