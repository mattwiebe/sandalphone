"""
Qwen3-TTS client for text-to-speech synthesis with voice cloning.
Uses MLX-optimized Qwen3-TTS for low-latency speech generation.
Falls back to macOS 'say' command if model loading fails.
"""

import subprocess
import tempfile
from pathlib import Path
from tts.base import TTSProvider

try:
    from mlx_audio.tts.utils import load_model
    from mlx_audio.tts.generate import generate_audio
    MLX_AUDIO_AVAILABLE = True
except ImportError:
    MLX_AUDIO_AVAILABLE = False


class QwenTTSClient(TTSProvider):
    def __init__(self, model_path=None):
        """
        Initialize TTS client.

        Args:
            model_path: Path to Qwen3-TTS model directory
        """
        self.use_fallback = False

        if model_path is None:
            model_path = (
                Path(__file__).parent.parent.parent / "models" / "qwen3-tts-0.6b"
            )

        self.model_path = Path(model_path)

        # Try to load the Qwen3-TTS model, fall back to macOS 'say' if it fails
        try:
            if not MLX_AUDIO_AVAILABLE:
                raise ImportError("mlx_audio not available")

            if not self.model_path.exists():
                raise FileNotFoundError(f"TTS model not found: {self.model_path}")

            print(f"Loading TTS model from {self.model_path}...")
            self.model = load_model(self.model_path)
            print("TTS model loaded!")
        except (ImportError, FileNotFoundError, ValueError) as e:
            print(f"⚠️  Could not load Qwen TTS model: {e}")
            print("⚠️  Falling back to macOS 'say' command for TTS")
            self.use_fallback = True
            self.model = None

    def synthesize(self, text, output_file=None, language="en"):
        """
        Synthesize speech from text.

        Args:
            text: Text to synthesize
            output_file: Output audio file path (optional, generates temp file if None)
            language: Language code (en or es)

        Returns:
            Path to generated audio file
        """
        if output_file is None:
            # Create temp file with proper prefix
            temp_dir = Path(tempfile.gettempdir())
            output_file = temp_dir / f"tts_{id(self)}.wav"
        else:
            output_file = Path(output_file)

        # Use fallback macOS 'say' command if model not loaded
        if self.use_fallback:
            return self._synthesize_with_say(text, output_file, language)

        # Remove extension from output file for generate_audio
        # (it adds .wav automatically)
        file_prefix = str(output_file.parent / output_file.stem)

        # Generate audio
        generate_audio(
            model=self.model,
            text=text,
            file_prefix=file_prefix,
        )

        # generate_audio creates {file_prefix}_000.wav (with segment number)
        generated_file = Path(f"{file_prefix}_000.wav")

        if not generated_file.exists():
            # Also check for .wav without suffix
            alt_file = Path(f"{file_prefix}.wav")
            if alt_file.exists():
                generated_file = alt_file
            else:
                raise RuntimeError(
                    f"TTS synthesis failed: output file not created at {generated_file} or {alt_file}"
                )

        # If the desired output file is different, rename it
        if generated_file != output_file:
            generated_file.rename(output_file)
            return output_file

        return generated_file

    def _synthesize_with_say(self, text, output_file, language):
        """Fallback TTS using macOS 'say' command."""
        output_file = Path(output_file)

        # Use Spanish voice if language is Spanish
        voice = "Monica" if language == "es" else "Samantha"

        # Use say command to generate audio
        # say -v voice -o output.aiff "text"
        # then convert to wav
        temp_aiff = output_file.with_suffix('.aiff')

        try:
            subprocess.run(
                ["say", "-v", voice, "-o", str(temp_aiff), text],
                check=True,
                capture_output=True
            )

            # Convert AIFF to WAV
            subprocess.run(
                ["ffmpeg", "-i", str(temp_aiff), "-y", str(output_file)],
                check=True,
                capture_output=True
            )

            # Clean up temp file
            temp_aiff.unlink()

            return output_file
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"TTS synthesis with 'say' failed: {e}")


if __name__ == "__main__":
    # Test the client
    client = QwenTTSClient()

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
