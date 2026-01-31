"""
Real-time translation pipeline for voice chat audio.
Handles audio buffering, VAD, and streaming translation.
"""

import asyncio
import logging
import json
import base64
import os
from collections import deque
from typing import Optional, Callable
import websockets
import webrtcvad
import wave

logger = logging.getLogger(__name__)


class RealtimeTranslationPipeline:
    """
    Processes incoming voice chat audio and streams translations back.

    Pipeline flow:
    1. Buffer incoming audio chunks
    2. Detect speech end with VAD
    3. Send to Mac backend for translation
    4. Stream translated audio back to voice chat
    """

    def __init__(
        self,
        mac_backend_url: str,
        source_lang: str = "es",
        target_lang: str = "en",
        vad_aggressiveness: int = 2,
        silence_duration_ms: int = 500,
    ):
        """
        Initialize pipeline.

        Args:
            mac_backend_url: WebSocket URL of Mac backend
            source_lang: Source language code
            target_lang: Target language code
            vad_aggressiveness: VAD sensitivity (0-3, higher = more aggressive)
            silence_duration_ms: Milliseconds of silence to detect speech end
        """
        self.backend_url = mac_backend_url
        self.source_lang = source_lang
        self.target_lang = target_lang

        # Audio buffering
        self.audio_buffer = deque(maxlen=1000)  # ~10 seconds at 100 chunks/sec
        self.is_processing = False

        # Voice Activity Detection
        self.vad = webrtcvad.Vad(vad_aggressiveness)
        self.silence_frames = 0
        self.speech_frames = 0
        self.silence_threshold = silence_duration_ms // 10  # Convert to frame count

        # Callback for translated audio
        self.on_translation_ready: Optional[Callable] = None

        # Stats
        self.total_translations = 0
        self.last_translation = None

        logger.info(
            f"Pipeline initialized: {source_lang}→{target_lang}, "
            f"VAD={vad_aggressiveness}, silence={silence_duration_ms}ms"
        )

    async def process_incoming_audio(self, audio_chunk: bytes, sample_rate: int = 16000):
        """
        Process incoming audio chunk from voice chat.

        Args:
            audio_chunk: Raw audio data (PCM)
            sample_rate: Audio sample rate in Hz
        """
        # Add to buffer
        self.audio_buffer.append(audio_chunk)

        # Check for speech end using VAD
        try:
            # VAD expects 10, 20, or 30ms frames at 8000, 16000, or 32000 Hz
            # For 16kHz, 20ms frame = 320 samples = 640 bytes (16-bit PCM)
            if len(audio_chunk) == 640:  # 20ms frame at 16kHz
                is_speech = self.vad.is_speech(audio_chunk, sample_rate)

                if is_speech:
                    self.speech_frames += 1
                    self.silence_frames = 0
                else:
                    self.silence_frames += 1

                # Speech ended if we have silence after speech
                if (
                    self.speech_frames > 10  # At least 200ms of speech
                    and self.silence_frames >= self.silence_threshold
                ):
                    logger.info(
                        f"Speech ended detected: {self.speech_frames} speech frames, "
                        f"{self.silence_frames} silence frames"
                    )
                    # Process buffered audio
                    await self.translate_speech()

                    # Reset counters
                    self.speech_frames = 0
                    self.silence_frames = 0

        except Exception as e:
            logger.error(f"VAD error: {e}")

    async def translate_speech(self):
        """Process buffered audio through translation pipeline."""
        if self.is_processing:
            logger.debug("Already processing, skipping")
            return

        if len(self.audio_buffer) == 0:
            logger.debug("Empty buffer, skipping translation")
            return

        self.is_processing = True

        try:
            # Combine buffered audio
            audio_data = b"".join(self.audio_buffer)
            logger.info(f"Processing {len(audio_data)} bytes of audio")

            # Convert raw PCM to WAV format for Mac backend
            wav_data = self._pcm_to_wav(audio_data)

            # Send to Mac backend
            translated_audio = await self._call_backend(wav_data)

            if translated_audio and self.on_translation_ready:
                # Notify callback with translated audio
                await self.on_translation_ready(translated_audio)

            self.total_translations += 1
            self.last_translation = asyncio.get_event_loop().time()

        except Exception as e:
            logger.error(f"Translation error: {e}", exc_info=True)

        finally:
            self.is_processing = False
            self.audio_buffer.clear()

    async def _call_backend(self, wav_data: bytes) -> Optional[bytes]:
        """
        Call Mac backend for translation.

        Args:
            wav_data: WAV audio data

        Returns:
            Translated audio as bytes, or None if failed
        """
        try:
            logger.info(f"Connecting to Mac backend at {self.backend_url}")

            async with websockets.connect(
                self.backend_url,
                open_timeout=10,
                close_timeout=10,
                ping_timeout=60,
                ping_interval=20,
            ) as ws:
                # Encode audio
                audio_b64 = base64.b64encode(wav_data).decode("utf-8")

                request = {
                    "audio": audio_b64,
                    "source_lang": self.source_lang,
                    "target_lang": self.target_lang,
                    "format": "wav",
                }

                # Send request
                await ws.send(json.dumps(request))
                logger.info("Sent translation request to backend")

                # Receive response
                response_str = await ws.recv()
                response = json.loads(response_str)

                if response.get("status") == "success":
                    # Decode translated audio
                    translated_audio = base64.b64decode(response["audio"])
                    logger.info(
                        f"✅ Translation successful: {response.get('transcription')} → "
                        f"{response.get('translation')}"
                    )
                    return translated_audio
                else:
                    logger.error(f"Translation failed: {response.get('error')}")
                    return None

        except Exception as e:
            logger.error(f"Backend call error: {e}", exc_info=True)
            return None

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 16000) -> bytes:
        """
        Convert raw PCM audio to WAV format.

        Args:
            pcm_data: Raw PCM data (16-bit)
            sample_rate: Sample rate in Hz

        Returns:
            WAV file as bytes
        """
        import io

        wav_buffer = io.BytesIO()

        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)

        wav_buffer.seek(0)
        return wav_buffer.read()

    def set_translation_callback(self, callback: Callable):
        """
        Set callback to be called when translation is ready.

        Args:
            callback: Async function that takes translated audio bytes
        """
        self.on_translation_ready = callback

    def toggle_language(self):
        """Toggle translation direction."""
        self.source_lang, self.target_lang = self.target_lang, self.source_lang
        logger.info(f"Language toggled to {self.source_lang}→{self.target_lang}")
