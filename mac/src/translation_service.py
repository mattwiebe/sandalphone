"""
Core translation service that orchestrates STT → Translation → TTS pipeline.
This is the heart of Levi's translation mode.
"""

import sys
from pathlib import Path
import tempfile
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from stt.whisper_client import WhisperClient
from llm.translation_factory import create_translation_client
from tts.factory import create_tts_provider


class TranslationService:
    def __init__(self, stt=None, translator=None, tts=None):
        """
        Initialize the full translation pipeline.

        Args:
            stt: Optional pre-initialized WhisperClient (for sharing)
            translator: Optional pre-initialized translation client (for sharing)
            tts: Optional pre-initialized TTS provider (for sharing)
        """
        if stt and translator and tts:
            # Use shared components
            print("Initializing Translation Service (using shared components)...")
            self.stt = stt
            self.translator = translator
            self.tts = tts
            print("✓ Translation Service ready (shared)!")
        else:
            # Initialize new components
            print("Initializing Translation Service...")

            print("1. Loading Whisper STT...")
            self.stt = WhisperClient()

            print("2. Loading Translation LLM...")
            self.translator = create_translation_client()

            print("3. Loading TTS...")
            self.tts = create_tts_provider()

            print("✓ Translation Service ready!")

    def translate_audio(
        self, input_audio, source_lang="es", target_lang="en", output_audio=None
    ):
        """
        Full pipeline: Audio → Transcribe → Translate → Synthesize → Audio

        Args:
            input_audio: Path to input audio file
            source_lang: Source language (es or en)
            target_lang: Target language (en or es)
            output_audio: Optional path for output audio (generated if None)

        Returns:
            dict with transcription, translation, and output_audio path
        """
        print(f"\n{'=' * 60}")
        print(f"TRANSLATION PIPELINE: {source_lang.upper()} → {target_lang.upper()}")
        print(f"{'=' * 60}")

        # Step 1: Transcribe audio
        print(f"\n[1/3] Transcribing audio ({source_lang})...")
        transcription = self.stt.transcribe(input_audio, language=source_lang)
        print(f'      Transcribed: "{transcription}"')

        # Step 2: Translate text
        print(f"\n[2/3] Translating {source_lang} → {target_lang}...")
        translation = self.translator.translate(transcription, source_lang, target_lang)
        print(f'      Translated: "{translation}"')

        # Step 3: Synthesize translated text with voice cloning
        print(f"\n[3/3] Synthesizing speech ({target_lang})...")
        output_audio_path = self.tts.synthesize(
            text=translation, output_file=output_audio, language=target_lang
        )
        print(f"      Audio generated: {output_audio_path}")

        print(f"\n{'=' * 60}")
        print(f"✓ TRANSLATION COMPLETE")
        print(f"{'=' * 60}\n")

        return {
            "transcription": transcription,
            "translation": translation,
            "output_audio": str(output_audio_path),
        }


def main():
    """Test the translation service with sample audio."""
    import subprocess

    service = TranslationService()

    # Test with JFK sample (English)
    sample_audio = (
        Path(__file__).parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"
    )

    if not sample_audio.exists():
        print(f"Sample audio not found: {sample_audio}")
        return

    # Translate English to Spanish
    print("Testing English → Spanish translation...")
    result = service.translate_audio(
        input_audio=sample_audio, source_lang="en", target_lang="es"
    )

    print("\nResult:")
    print(f"  Original (EN): {result['transcription']}")
    print(f"  Translation (ES): {result['translation']}")
    print(f"  Audio file: {result['output_audio']}")

    # Play the translated audio
    print("\nPlaying translated Spanish audio...")
    subprocess.run(["afplay", result["output_audio"]])


if __name__ == "__main__":
    main()
