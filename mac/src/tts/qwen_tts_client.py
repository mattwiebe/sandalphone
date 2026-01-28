"""
Qwen3-TTS client for text-to-speech synthesis.
Uses MLX-optimized Qwen3-TTS for low-latency speech generation.
"""
import subprocess
import tempfile
from pathlib import Path


class QwenTTSClient:
    def __init__(self, model_path=None):
        """
        Initialize TTS client.

        Args:
            model_path: Path to Qwen3-TTS model directory
        """
        if model_path is None:
            model_path = Path(__file__).parent.parent.parent / "models" / "qwen3-tts-0.6b"

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f"TTS model not found: {self.model_path}")

        # Note: Qwen3-TTS requires specific inference code
        # For now, we'll use a placeholder until we implement the full TTS pipeline
        print(f"TTS model path: {self.model_path}")

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
        # TODO: Implement full Qwen3-TTS inference
        # For now, use system TTS as placeholder
        if output_file is None:
            output_file = Path(tempfile.mktemp(suffix=".wav"))
        else:
            output_file = Path(output_file)

        # Placeholder: Use macOS 'say' command for testing
        # This will be replaced with actual Qwen3-TTS inference
        voice = "Samantha" if language == "en" else "Paulina"

        cmd = ["say", "-v", voice, "-o", str(output_file), "--data-format=LEI16@16000", text]

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise RuntimeError(f"TTS synthesis failed: {result.stderr.decode()}")

        return output_file


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
