"""
Whisper.cpp client for speech-to-text transcription.
Uses Metal-accelerated Whisper for fast transcription on M4 Max.
"""
import subprocess
import os
from pathlib import Path


class WhisperClient:
    def __init__(self, model_path=None, whisper_bin=None):
        """
        Initialize Whisper client.

        Args:
            model_path: Path to ggml model file
            whisper_bin: Path to whisper-cli binary
        """
        if model_path is None:
            model_path = Path(__file__).parent.parent.parent / "models" / "whisper.cpp" / "models" / "ggml-base.bin"

        if whisper_bin is None:
            whisper_bin = Path(__file__).parent.parent.parent / "models" / "whisper.cpp" / "build" / "bin" / "whisper-cli"

        self.model_path = Path(model_path)
        self.whisper_bin = Path(whisper_bin)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Whisper model not found: {self.model_path}")

        if not self.whisper_bin.exists():
            raise FileNotFoundError(f"Whisper binary not found: {self.whisper_bin}")

    def transcribe(self, audio_file, language=None):
        """
        Transcribe audio file to text.

        Args:
            audio_file: Path to audio file (wav, mp3, etc.)
            language: Optional language code (e.g., 'es' for Spanish, 'en' for English)

        Returns:
            Transcribed text
        """
        audio_path = Path(audio_file)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        cmd = [
            str(self.whisper_bin),
            "-m", str(self.model_path),
            "-f", str(audio_path),
            "--no-timestamps",  # Just get the text
            "--output-txt",  # Output as text
        ]

        if language:
            cmd.extend(["-l", language])

        # Run transcription
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            raise RuntimeError(f"Whisper transcription failed: {result.stderr}")

        # Parse output - whisper-cli writes to stdout
        # Extract just the transcribed text
        lines = result.stdout.strip().split('\n')

        # Find the transcription line (skipping timing info)
        transcription = ""
        for line in lines:
            if line.strip() and not line.startswith('[') and not line.startswith('whisper_'):
                transcription = line.strip()
                break

        return transcription


if __name__ == "__main__":
    # Test the client
    client = WhisperClient()

    # Test with sample audio
    sample = Path(__file__).parent.parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"

    if sample.exists():
        print(f"Testing transcription with: {sample}")
        text = client.transcribe(sample)
        print(f"Transcribed: {text}")
    else:
        print("Sample audio not found")
