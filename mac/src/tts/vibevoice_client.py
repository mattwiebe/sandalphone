"""
VibeVoice TTS client using MLX-optimized VibeVoice models.
Falls back to Qwen TTS if model loading fails.
"""

import tempfile
import io
import wave
from pathlib import Path
from typing import Optional, Generator
from tts.base import TTSProvider

try:
    from mlx_audio.tts.utils import load_model
    from mlx_audio.tts.generate import generate_audio
    import mlx.core as mx
    import numpy as np

    MLX_AUDIO_AVAILABLE = True
except ImportError:
    MLX_AUDIO_AVAILABLE = False


class VibeVoiceClient(TTSProvider):
    """VibeVoice TTS client with fallback to Qwen TTS."""

    def __init__(self, model_path: str = "mlx-community/VibeVoice-Realtime-0.5B-fp16"):
        """
        Initialize VibeVoice TTS client with fallback to Qwen.

        Args:
            model_path: HuggingFace model repo or local path
                       Default: mlx-community/VibeVoice-Realtime-0.5B-fp16
        """
        self.model_path = model_path
        self.use_fallback = False
        self.fallback_client = None
        self.model = None

        try:
            if not MLX_AUDIO_AVAILABLE:
                raise ImportError("mlx_audio not available")

            print(f"Loading VibeVoice model from {model_path}...")
            self.model = load_model(model_path)
            print("VibeVoice model loaded!")

        except Exception as e:
            print(f"⚠️  Could not load VibeVoice model: {e}")
            print("⚠️  Falling back to Qwen TTS")
            self.use_fallback = True

            # Import here to avoid circular dependency
            from tts.qwen_tts_client import QwenTTSClient

            self.fallback_client = QwenTTSClient()

    def synthesize(
        self, text: str, output_file: Optional[Path] = None, language: str = "en"
    ) -> Path:
        """
        Synthesize speech from text using VibeVoice.

        Args:
            text: Text to synthesize
            output_file: Optional output path (generates temp file if None)
            language: Language code ("en" or "es")

        Returns:
            Path to generated audio file
        """
        # If fallback is enabled, delegate to Qwen
        if self.use_fallback:
            return self.fallback_client.synthesize(text, output_file, language)

        if output_file is None:
            # Create temp file with proper prefix
            temp_dir = Path(tempfile.gettempdir())
            output_file = temp_dir / f"tts_vibevoice_{id(self)}.wav"
        else:
            output_file = Path(output_file)

        # Map language to voice
        # Note: VibeVoice voice options may vary. Common options:
        # English: "en-Emma_woman", "en-default"
        # Spanish: Need to verify available Spanish voices
        voice = self._get_voice_for_language(language)

        # Remove extension from output file for generate_audio
        # (it adds .wav automatically with _000 suffix)
        file_prefix = str(output_file.parent / output_file.stem)

        try:
            # Generate audio using mlx_audio's generate_audio function
            # cfg_scale is required for VibeVoice (classifier-free guidance scale)
            # Lower values (1.0-1.5) are more stable, higher for more variation
            generate_audio(
                text=text,
                model=self.model,
                voice=voice,
                lang_code=language,
                file_prefix=file_prefix,
                audio_format="wav",
                cfg_scale=1.5,  # Stable value for VibeVoice
                ddpm_steps=5,  # Default diffusion steps
                verbose=False,
                play=False,
            )

            # generate_audio creates {file_prefix}_000.wav
            generated_file = Path(f"{file_prefix}_000.wav")

            if not generated_file.exists():
                # Also check for .wav without suffix (some models might not add suffix)
                alt_file = Path(f"{file_prefix}.wav")
                if alt_file.exists():
                    generated_file = alt_file
                else:
                    raise RuntimeError(
                        f"VibeVoice synthesis failed: output file not created at {generated_file}"
                    )

            # If the desired output file is different, rename it
            if generated_file != output_file:
                generated_file.rename(output_file)
                return output_file

            return generated_file

        except Exception as e:
            print(f"⚠️  VibeVoice synthesis error: {e}")
            print("⚠️  Attempting fallback to Qwen TTS")

            # Lazy-load fallback if not already initialized
            if self.fallback_client is None:
                from tts.qwen_tts_client import QwenTTSClient

                self.fallback_client = QwenTTSClient()
                self.use_fallback = True

            # Clean up any partial files
            if generated_file and generated_file.exists():
                generated_file.unlink()

            return self.fallback_client.synthesize(text, output_file, language)

    def synthesize_streaming(
        self,
        text: str,
        language: str = "en",
        streaming_interval: float = 2.0
    ) -> Generator[bytes, None, None]:
        """
        Stream audio chunks as they're generated (real-time TTS).

        This method leverages VibeVoice's native streaming capability to yield
        audio chunks as they're generated, reducing time-to-first-audio significantly.

        Args:
            text: Text to synthesize
            language: Language code ("en" or "es")
            streaming_interval: Seconds of audio per chunk (default: 2.0)

        Yields:
            Audio chunks as WAV-encoded bytes

        Raises:
            RuntimeError: If VibeVoice model not available
        """
        # If fallback is enabled, VibeVoice isn't available
        if self.use_fallback:
            raise RuntimeError(
                "VibeVoice model not loaded - streaming not available in fallback mode"
            )

        if not MLX_AUDIO_AVAILABLE:
            raise RuntimeError("mlx_audio not available for streaming")

        voice = self._get_voice_for_language(language)

        # Use VibeVoice's native streaming generator
        for result in self.model.generate(
            text=text,
            voice=voice,
            lang_code=language,
            cfg_scale=1.5,  # Stable value for VibeVoice
            ddpm_steps=5,   # Default diffusion steps
            stream=True,
            streaming_interval=streaming_interval,
            verbose=False,
        ):
            # Convert numpy array to WAV bytes
            audio_bytes = self._array_to_wav(result.audio, result.sample_rate)
            yield audio_bytes

    def _array_to_wav(self, audio_array, sample_rate: int) -> bytes:
        """
        Convert audio array (MLX or numpy) to WAV-encoded bytes.

        Args:
            audio_array: Audio samples as MLX array or numpy array
            sample_rate: Sample rate in Hz

        Returns:
            WAV file as bytes
        """
        # Convert MLX array to numpy
        # MLX arrays need explicit conversion using np.array()
        if hasattr(audio_array, '__class__') and 'mlx' in str(type(audio_array)):
            # This is an MLX array - convert to numpy
            audio_np = np.array(audio_array)
        else:
            audio_np = audio_array

        # Ensure audio is in int16 format
        if audio_np.dtype != np.int16:
            # Normalize to [-1, 1] if needed
            max_val = np.max(np.abs(audio_np))
            if max_val > 1.0:
                audio_np = audio_np / max_val
            # Convert to int16
            audio_np = (audio_np * 32767).astype(np.int16)

        # Write to WAV format in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(audio_np.tobytes())

        return wav_buffer.getvalue()

    def _get_voice_for_language(self, language: str) -> str:
        """
        Map language code to VibeVoice voice name.

        Args:
            language: Language code ("en" or "es")

        Returns:
            Voice name for the specified language
        """
        # VibeVoice voice mapping
        # Available voices include: en-Emma_woman, en-Grace_woman, sp-Spk0_woman, etc.
        voice_map = {
            "en": "en-Emma_woman",  # English female voice
            "es": "sp-Spk0_woman",  # Spanish female voice
        }

        return voice_map.get(language, "en-Emma_woman")


if __name__ == "__main__":
    # Test the client
    import subprocess

    client = VibeVoiceClient()

    # Test English
    english_text = "What is your best price?"
    print(f"Synthesizing English: {english_text}")
    audio_file = client.synthesize(english_text, language="en")
    print(f"Generated audio: {audio_file}")

    # Test Spanish
    spanish_text = "¿Cuál es tu mejor precio?"
    print(f"\nSynthesizing Spanish: {spanish_text}")
    audio_file_es = client.synthesize(spanish_text, language="es")
    print(f"Generated audio: {audio_file_es}")

    # Play the audio
    print("\nPlaying English audio...")
    subprocess.run(["afplay", str(audio_file)])

    print("Playing Spanish audio...")
    subprocess.run(["afplay", str(audio_file_es)])
