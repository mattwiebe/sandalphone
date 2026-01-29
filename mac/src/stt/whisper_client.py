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

        # Parse output - look for lines starting with timestamps or just text
        # Whisper outputs to stderr, actual transcription is in lines without whisper_ prefix
        output = result.stderr + result.stdout
        lines = output.strip().split('\n')

        # Find the transcription - look for lines with the actual text
        transcription = ""
        for line in lines:
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Skip all system/debug messages
            skip_prefixes = ['whisper_', 'ggml_', 'system_info:', 'main:', 'operator()', 'Metal', 'CPU', 'OPENVINO', 'COREML']
            if any(line.startswith(prefix) for prefix in skip_prefixes):
                continue

            # Skip lines with system info keywords
            skip_keywords = ['nthreads', 'EMBEDLIBRARY', 'NEON', 'ARMFMA', 'ACCELERATE', 'DOTPROD', 'load time', 'mel time', 'sample time', 'encode time', 'decode time', 'batchd time', 'prompt time', 'total time', 'fallbacks', 'processing']
            if any(keyword in line for keyword in skip_keywords):
                continue

            # If it starts with [timestamp], extract the text after ]
            if line.startswith('[') and ']' in line:
                # Format: [00:00:00.000 --> 00:00:10.000]  Transcribed text here
                text_part = line.split(']', 1)[1].strip()
                if text_part and len(text_part) > 3:  # Must have actual content
                    transcription = text_part
                    break
            # Otherwise, if it looks like transcribed text (not debug info), take it
            elif len(line) > 3 and not line.startswith('ggml') and not 'time =' in line:
                transcription = line
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
