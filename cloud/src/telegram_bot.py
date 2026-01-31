"""
Telegram bot for Levi translation service.
Receives voice messages, sends to Mac backend, returns translated audio.
Supports both voice messages and real-time voice calls.
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
from pyrogram import Client
import websockets
from dotenv import load_dotenv

from voice_call_manager import VoiceCallManager
from realtime_translation_pipeline import RealtimeTranslationPipeline

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
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
MAC_WEBSOCKET_URL = os.getenv("MAC_WEBSOCKET_URL", "ws://localhost:8000/ws/translate")
ALLOWED_USER_IDS = (
    os.getenv("ALLOWED_USER_IDS", "").split(",")
    if os.getenv("ALLOWED_USER_IDS")
    else []
)

# Voice call settings
VOICE_CALL_ENABLED = os.getenv("VOICE_CALL_ENABLED", "true").lower() == "true"
AUTO_JOIN_VOICE_CHATS = os.getenv("AUTO_JOIN_VOICE_CHATS", "true").lower() == "true"
DEFAULT_SOURCE_LANG = os.getenv("DEFAULT_SOURCE_LANG", "es")
DEFAULT_TARGET_LANG = os.getenv("DEFAULT_TARGET_LANG", "en")
VAD_AGGRESSIVENESS = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
SILENCE_DURATION_MS = int(os.getenv("SILENCE_DURATION_MS", "500"))

# User state management (simple in-memory for now)
user_states = {}

# Global instances (will be initialized in main)
voice_manager: VoiceCallManager = None
translation_pipelines = {}  # chat_id -> RealtimeTranslationPipeline


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.username}) started the bot")

    voice_call_info = ""
    if VOICE_CALL_ENABLED:
        voice_call_info = """
**Voice Calls (NEW!):**
/join - Join voice chat for real-time translation
/leave - Leave voice chat

"""

    welcome_message = f"""
🎙️ **Welcome to Levi Translation Service!** 🌍

Hi {user.first_name}! I can help you translate between Spanish and English.

**How to use:**
1. Send me a voice message in Spanish or English
2. I'll transcribe it
3. Translate it to the other language
4. Send you back a voice message with the translation!

{voice_call_info}**Commands:**
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
    voice_call_help = ""
    if VOICE_CALL_ENABLED:
        voice_call_help = """
**Voice Calls:**
/join - Join group voice chat for real-time translation
/leave - Leave voice chat

To use voice calls:
1. Add me to a group chat
2. Start a voice chat
3. Send /join
4. Speak and I'll translate live!

"""

    help_text = f"""
**Levi Translation Service Help** 📖

**Available Commands:**
/start - Start the bot and see welcome message
/help - Show this help message
/mode - Toggle between ES→EN and EN→ES
/status - Check if the service is running
{voice_call_help}
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


async def join_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /join command to join voice chat."""
    if not VOICE_CALL_ENABLED:
        await update.message.reply_text(
            "❌ Voice call feature is disabled.\n"
            "Set VOICE_CALL_ENABLED=true in .env to enable."
        )
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    # Check if this is a group
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text(
            "❌ Voice calls only work in group chats.\n\n"
            "**How to use:**\n"
            "1. Add me to a group chat\n"
            "2. Start a voice chat in the group\n"
            "3. Send /join command\n"
            "4. Speak and I'll translate in real-time!"
        )
        return

    # Get user state for language settings
    if user_id not in user_states:
        user_states[user_id] = {"source_lang": DEFAULT_SOURCE_LANG, "target_lang": DEFAULT_TARGET_LANG}

    state = user_states[user_id]

    try:
        # Join the voice chat
        success = await voice_manager.join_voice_chat(chat_id)

        if success:
            # Create translation pipeline for this chat
            pipeline = RealtimeTranslationPipeline(
                mac_backend_url=MAC_WEBSOCKET_URL,
                source_lang=state["source_lang"],
                target_lang=state["target_lang"],
                vad_aggressiveness=VAD_AGGRESSIVENESS,
                silence_duration_ms=SILENCE_DURATION_MS,
            )

            translation_pipelines[chat_id] = pipeline

            await update.message.reply_text(
                f"✅ **Joined voice chat!**\n\n"
                f"🎙️ Translation mode: {state['source_lang'].upper()} → {state['target_lang'].upper()}\n\n"
                f"Speak and I'll translate in real-time!\n"
                f"Use /mode to change language direction.\n"
                f"Use /leave to exit the voice chat.",
                parse_mode="Markdown",
            )
            logger.info(f"Successfully joined voice chat {chat_id}")
        else:
            await update.message.reply_text(
                "❌ Failed to join voice chat.\n\n"
                "**Possible reasons:**\n"
                "- No active voice chat in this group\n"
                "- Bot lacks permissions\n"
                "- Already in the voice chat\n\n"
                "Make sure a voice chat is active and try again."
            )

    except Exception as e:
        logger.error(f"Error joining voice chat: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Error joining voice chat:\n{str(e)}\n\n"
            "Please check the logs for details."
        )


async def leave_call(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /leave command to leave voice chat."""
    chat_id = update.effective_chat.id

    if not voice_manager.is_in_call(chat_id):
        await update.message.reply_text(
            "ℹ️ I'm not currently in a voice chat.\n"
            "Use /join to join a voice chat first."
        )
        return

    try:
        # Leave the voice chat
        success = await voice_manager.leave_voice_chat(chat_id)

        if success:
            # Clean up translation pipeline
            if chat_id in translation_pipelines:
                del translation_pipelines[chat_id]

            await update.message.reply_text(
                "👋 **Left voice chat**\n\n"
                "Use /join to rejoin anytime!"
            )
            logger.info(f"Successfully left voice chat {chat_id}")
        else:
            await update.message.reply_text(
                "❌ Failed to leave voice chat.\n"
                "Please check the logs for details."
            )

    except Exception as e:
        logger.error(f"Error leaving voice chat: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Error leaving voice chat:\n{str(e)}"
        )


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


async def async_main():
    """Async main function to run both clients concurrently."""
    global voice_manager

    # Validate configuration
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
    logger.info(f"Voice calls enabled: {VOICE_CALL_ENABLED}")

    # Create python-telegram-bot application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("mode", toggle_mode))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))

    # Add voice call handlers if enabled
    if VOICE_CALL_ENABLED:
        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            logger.warning(
                "Voice calls enabled but TELEGRAM_API_ID/TELEGRAM_API_HASH not set!"
            )
            logger.warning("Voice call features will be disabled.")
            logger.warning("Get API credentials from https://my.telegram.org")
        else:
            application.add_handler(CommandHandler("join", join_call))
            application.add_handler(CommandHandler("leave", leave_call))
            logger.info("✅ Voice call handlers registered")

    # Start python-telegram-bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)

    logger.info("✅ Python-telegram-bot started")

    # Initialize Pyrogram client and voice manager if voice calls are enabled
    pyrogram_client = None
    if VOICE_CALL_ENABLED and TELEGRAM_API_ID and TELEGRAM_API_HASH:
        try:
            # Create Pyrogram client for voice calls
            pyrogram_client = Client(
                name="levi_bot",
                api_id=int(TELEGRAM_API_ID),
                api_hash=TELEGRAM_API_HASH,
                bot_token=TELEGRAM_BOT_TOKEN,
                workdir=os.path.expanduser("~/.levi"),  # Session file location
            )

            # Initialize voice call manager
            voice_manager = VoiceCallManager(pyrogram_client)

            # Start both clients
            await pyrogram_client.start()
            await voice_manager.start()

            # Register auto-join handler for voice chats if enabled
            if AUTO_JOIN_VOICE_CHATS:
                @pyrogram_client.on_message()
                async def auto_join_voice_chat(client, message):
                    """Auto-join when voice chat starts in a group."""
                    try:
                        # Check if this is a voice chat started service message
                        if message.service and hasattr(message, 'video_chat_started'):
                            chat_id = message.chat.id
                            logger.info(f"🎙️ Voice chat started in {chat_id}, auto-joining...")

                            # Auto-join the voice chat
                            success = await voice_manager.join_voice_chat(chat_id)

                            if success:
                                # Get default language settings
                                default_state = {"source_lang": DEFAULT_SOURCE_LANG, "target_lang": DEFAULT_TARGET_LANG}

                                # Create translation pipeline for this chat
                                pipeline = RealtimeTranslationPipeline(
                                    mac_backend_url=MAC_WEBSOCKET_URL,
                                    source_lang=default_state["source_lang"],
                                    target_lang=default_state["target_lang"],
                                    vad_aggressiveness=VAD_AGGRESSIVENESS,
                                    silence_duration_ms=SILENCE_DURATION_MS,
                                )
                                translation_pipelines[chat_id] = pipeline

                                logger.info(f"✅ Auto-joined voice chat in {chat_id}")

                                # Send confirmation message to the group
                                await client.send_message(
                                    chat_id,
                                    f"🎙️ **Auto-joined voice chat!**\n\n"
                                    f"Translation mode: {default_state['source_lang'].upper()} → {default_state['target_lang'].upper()}\n\n"
                                    f"Speak and I'll translate!\n"
                                    f"Use /mode to change languages.\n"
                                    f"Use /leave to exit."
                                )
                            else:
                                logger.warning(f"Failed to auto-join voice chat in {chat_id}")

                    except Exception as e:
                        logger.error(f"Error in auto-join handler: {e}", exc_info=True)

                logger.info("✅ Pyrogram client and voice manager started")
                logger.info("✅ Auto-join enabled for voice chats")
            else:
                logger.info("✅ Pyrogram client and voice manager started")
                logger.info("ℹ️ Auto-join disabled, use /join manually")

        except Exception as e:
            logger.error(f"Failed to start voice call features: {e}", exc_info=True)
            logger.warning("Continuing without voice call support")

    logger.info("✅ Bot fully started! Press Ctrl+C to stop.")

    try:
        # Keep running until interrupted
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")

    # Cleanup
    if voice_manager:
        await voice_manager.stop()
    if pyrogram_client:
        await pyrogram_client.stop()

    await application.updater.stop()
    await application.stop()
    await application.shutdown()

    logger.info("✅ Shutdown complete")


def main():
    """Entry point - run async main."""
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          🤖  LEVI TELEGRAM TRANSLATION BOT  🌍            ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    main()
