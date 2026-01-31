"""
Voice call manager using Pyrogram raw API calls.
Handles joining/leaving voice chats using Telegram's MTProto.
"""

import logging
import asyncio
from typing import Dict, Optional
from pyrogram import raw

logger = logging.getLogger(__name__)


class VoiceCallManager:
    """Manages Telegram voice chat connections using raw MTProto."""

    def __init__(self, pyrogram_client):
        """
        Initialize voice call manager.

        Args:
            pyrogram_client: Pyrogram client instance
        """
        self.client = pyrogram_client
        self.active_calls: Dict[int, dict] = {}  # chat_id -> call_state
        self._started = False
        logger.info("VoiceCallManager initialized (Raw MTProto)")

    async def start(self):
        """Initialize voice call manager."""
        if self._started:
            logger.warning("VoiceCallManager already started")
            return

        self._started = True
        logger.info("✅ VoiceCallManager started")

    async def stop(self):
        """Stop voice call manager gracefully."""
        if not self._started:
            return

        # Leave all active calls first
        for chat_id in list(self.active_calls.keys()):
            try:
                await self.leave_voice_chat(chat_id)
            except Exception as e:
                logger.error(f"Error leaving chat {chat_id}: {e}")

        self._started = False
        logger.info("VoiceCallManager stopped")

    async def join_voice_chat(self, chat_id: int, audio_path: Optional[str] = None) -> bool:
        """
        Join a voice chat in a group using raw Telegram API.

        Args:
            chat_id: Telegram chat ID of the group
            audio_path: Optional path to audio file to play initially

        Returns:
            True if joined successfully, False otherwise
        """
        if not self._started:
            logger.error("Cannot join voice chat: Manager not started")
            return False

        if chat_id in self.active_calls:
            logger.warning(f"Already in voice chat {chat_id}")
            return True

        try:
            logger.info(f"Attempting to join voice chat in {chat_id}")

            # Get the chat's full info to find the active call
            peer = await self.client.resolve_peer(chat_id)

            # Get full chat info
            if isinstance(peer, raw.types.InputPeerChannel):
                full_chat = await self.client.invoke(
                    raw.functions.channels.GetFullChannel(channel=peer)
                )
                call = full_chat.full_chat.call
            elif isinstance(peer, raw.types.InputPeerChat):
                full_chat = await self.client.invoke(
                    raw.functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
                call = full_chat.full_chat.call
            else:
                logger.error(f"Invalid peer type for chat {chat_id}")
                return False

            if not call:
                logger.error(f"No active voice chat in {chat_id}")
                return False

            logger.info(f"Found active call: {call.id}")

            # Join the group call
            # Note: This joins as a listener. To stream audio, we'd need ntgcalls
            result = await self.client.invoke(
                raw.functions.phone.JoinGroupCall(
                    call=call,
                    join_as=peer,
                    params=raw.types.DataJSON(data='{}'),
                    muted=False,
                )
            )

            logger.info(f"Join result: {result}")

            # Track the call
            self.active_calls[chat_id] = {
                "joined_at": asyncio.get_event_loop().time(),
                "call_id": call.id,
                "stream_active": False,
            }

            logger.info(f"✅ Successfully joined voice chat in {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to join voice chat {chat_id}: {e}", exc_info=True)
            return False

    async def leave_voice_chat(self, chat_id: int) -> bool:
        """
        Leave a voice chat.

        Args:
            chat_id: Telegram chat ID

        Returns:
            True if left successfully, False otherwise
        """
        if chat_id not in self.active_calls:
            logger.warning(f"Not in voice chat {chat_id}, cannot leave")
            return False

        try:
            logger.info(f"Leaving voice chat in {chat_id}")

            call_info = self.active_calls[chat_id]

            # Get the chat peer
            peer = await self.client.resolve_peer(chat_id)

            # Get call reference
            if isinstance(peer, raw.types.InputPeerChannel):
                full_chat = await self.client.invoke(
                    raw.functions.channels.GetFullChannel(channel=peer)
                )
                call = full_chat.full_chat.call
            elif isinstance(peer, raw.types.InputPeerChat):
                full_chat = await self.client.invoke(
                    raw.functions.messages.GetFullChat(chat_id=peer.chat_id)
                )
                call = full_chat.full_chat.call
            else:
                logger.error(f"Invalid peer type for chat {chat_id}")
                return False

            if call:
                # Leave the call
                await self.client.invoke(
                    raw.functions.phone.LeaveGroupCall(
                        call=call,
                        source=0,
                    )
                )

            # Remove from tracking
            del self.active_calls[chat_id]

            logger.info(f"✅ Successfully left voice chat {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to leave voice chat {chat_id}: {e}", exc_info=True)
            return False

    async def change_stream(self, chat_id: int, audio_path: str) -> bool:
        """
        Change the audio stream being played in a voice chat.

        Note: Streaming audio requires ntgcalls integration.

        Args:
            chat_id: Telegram chat ID
            audio_path: Path to audio file to stream

        Returns:
            True if stream changed successfully, False otherwise
        """
        if chat_id not in self.active_calls:
            logger.error(f"Not in voice chat {chat_id}, cannot change stream")
            return False

        logger.warning("Audio streaming not yet implemented - requires ntgcalls")
        return False

    def is_in_call(self, chat_id: int) -> bool:
        """Check if bot is currently in a voice chat."""
        return chat_id in self.active_calls

    def get_active_calls(self) -> list:
        """Get list of active call chat IDs."""
        return list(self.active_calls.keys())
