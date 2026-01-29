"""
Streaming translation service that yields audio chunks as they're generated.
This reduces time-to-first-audio significantly for real-time applications.
"""

import sys
from pathlib import Path
from typing import Generator, Dict, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from stt.whisper_client import WhisperClient
from llm.translation_client import TranslationClient
from tts.factory import create_tts_provider


class StreamingTranslationService:
    """Translation service with streaming TTS support."""

    def __init__(self):
        """Initialize the streaming translation pipeline."""
        print("Initializing Streaming Translation Service...")

        print("1. Loading Whisper STT...")
        self.stt = WhisperClient()

        print("2. Loading Translation LLM...")
        self.translator = TranslationClient()

        print("3. Loading TTS...")
        self.tts = create_tts_provider()

        print("✓ Streaming Translation Service ready!")

    def translate_audio_streaming(
        self,
        input_audio,
        source_lang: str = "es",
        target_lang: str = "en",
        streaming_interval: float = 2.0
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Full pipeline with streaming TTS: Audio → Transcribe → Translate → Stream Audio

        This method performs STT and translation as usual, but streams the TTS output
        as it's generated, reducing latency for the first audio chunk.

        Args:
            input_audio: Path to input audio file
            source_lang: Source language (es or en)
            target_lang: Target language (en or es)
            streaming_interval: Seconds of audio per chunk (default: 2.0)

        Yields:
            Dict containing:
                - type: "metadata" (first) or "audio_chunk" (subsequent)
                - transcription: Original transcribed text (metadata only)
                - translation: Translated text (metadata only)
                - data: Audio chunk bytes (audio_chunk only)
                - chunk_index: Index of audio chunk (audio_chunk only)
        """
        print(f"\n{'=' * 60}")
        print(f"STREAMING TRANSLATION: {source_lang.upper()} → {target_lang.upper()}")
        print(f"{'=' * 60}")

        # Step 1: Transcribe audio
        print(f"\n[1/3] Transcribing audio ({source_lang})...")
        transcription = self.stt.transcribe(input_audio, language=source_lang)
        print(f'      Transcribed: "{transcription}"')

        # Step 2: Translate text
        print(f"\n[2/3] Translating {source_lang} → {target_lang}...")
        translation = self.translator.translate(transcription, source_lang, target_lang)
        print(f'      Translated: "{translation}"')

        # Yield metadata first
        yield {
            "type": "metadata",
            "transcription": transcription,
            "translation": translation,
        }

        # Step 3: Stream TTS output
        print(f"\n[3/3] Streaming speech ({target_lang})...")

        # Check if TTS provider supports streaming
        if hasattr(self.tts, 'synthesize_streaming'):
            chunk_index = 0
            for audio_chunk in self.tts.synthesize_streaming(
                text=translation,
                language=target_lang,
                streaming_interval=streaming_interval
            ):
                print(f"      Chunk {chunk_index}: {len(audio_chunk)} bytes")
                yield {
                    "type": "audio_chunk",
                    "data": audio_chunk,
                    "chunk_index": chunk_index,
                }
                chunk_index += 1

            print(f"\n{'=' * 60}")
            print(f"✓ STREAMING TRANSLATION COMPLETE ({chunk_index} chunks)")
            print(f"{'=' * 60}\n")

        else:
            # Fallback to non-streaming
            print("      TTS provider doesn't support streaming, using batch mode...")
            audio_file = self.tts.synthesize(translation, language=target_lang)

            # Read the entire file and yield as single chunk
            with open(audio_file, "rb") as f:
                audio_data = f.read()

            yield {
                "type": "audio_chunk",
                "data": audio_data,
                "chunk_index": 0,
            }

            print(f"\n{'=' * 60}")
            print(f"✓ TRANSLATION COMPLETE (batch mode)")
            print(f"{'=' * 60}\n")


def main():
    """Test the streaming translation service."""
    import subprocess
    import tempfile
    from pathlib import Path

    service = StreamingTranslationService()

    # Test with JFK sample (English)
    sample_audio = (
        Path(__file__).parent.parent / "models" / "whisper.cpp" / "samples" / "jfk.wav"
    )

    if not sample_audio.exists():
        print(f"Sample audio not found: {sample_audio}")
        return

    print("Testing Streaming English → Spanish translation...")

    chunks = []
    metadata = None

    for result in service.translate_audio_streaming(
        input_audio=sample_audio,
        source_lang="en",
        target_lang="es",
        streaming_interval=1.5  # 1.5 seconds per chunk
    ):
        if result["type"] == "metadata":
            metadata = result
            print(f"\nReceived metadata:")
            print(f"  Original (EN): {metadata['transcription']}")
            print(f"  Translation (ES): {metadata['translation']}")
        elif result["type"] == "audio_chunk":
            chunks.append(result["data"])
            print(f"  Chunk {result['chunk_index']}: {len(result['data'])} bytes")

    # Combine all chunks and save to temp file
    print(f"\nReceived {len(chunks)} audio chunks")

    if chunks:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            for chunk in chunks:
                temp_file.write(chunk)
            output_file = temp_file.name

        print(f"Combined audio saved to: {output_file}")
        print("\nPlaying translated Spanish audio...")
        subprocess.run(["afplay", output_file])


if __name__ == "__main__":
    main()
