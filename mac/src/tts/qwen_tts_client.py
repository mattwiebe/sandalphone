"""
Qwen3-TTS client for text-to-speech synthesis with voice cloning.
Uses MLX-optimized Qwen3-TTS for low-latency speech generation.
"""

import subprocess
import tempfile
from pathlib import Path
from mlx_audio.tts.utils import load_model
from mlx_audio.tts.generate import generate_audio


class QwenTTSClient:
    def __init__(self, model_path=None):
        """
        Initialize TTS client.

        Args:
            model_path: Path to Qwen3-TTS model directory
        """
        if model_path is None:
            model_path = (
                Path(__file__).parent.parent.parent / "models" / "qwen3-tts-0.6b"
            )

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f"TTS model not found: {self.model_path}")

        # Load the Qwen3-TTS model
        print(f"Loading TTS model from {self.model_path}...")
        self.model = load_model(self.model_path)
        print("TTS model loaded!")

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
