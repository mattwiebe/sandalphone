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
from levi_pipeline.models import AudioChunkResult, TranslationMetadata
from levi_pipeline.service import StreamingTranslationPipeline
from llm.translation_factory import create_translation_client
from tts.factory import create_tts_provider


class StreamingTranslationService:
    """Translation service with streaming TTS support."""

    def __init__(self, stt=None, translator=None, tts=None):
        """
        Initialize the streaming translation pipeline.

        Args:
            stt: Optional pre-initialized WhisperClient (for sharing)
            translator: Optional pre-initialized translation client (for sharing)
            tts: Optional pre-initialized TTS provider (for sharing)
        """
        if stt and translator and tts:
            # Use shared components
            print("Initializing Streaming Translation Service (using shared components)...")
            self.stt = stt
            self.translator = translator
            self.tts = tts
            print("✓ Streaming Translation Service ready (shared)!")
        else:
            # Initialize new components
            print("Initializing Streaming Translation Service...")

            print("1. Loading Whisper STT...")
            self.stt = WhisperClient()

            print("2. Loading Translation LLM...")
            self.translator = create_translation_client()

            print("3. Loading TTS...")
            self.tts = create_tts_provider()

            print("✓ Streaming Translation Service ready!")

        self.pipeline = StreamingTranslationPipeline(
            stt=self.stt,
            translator=self.translator,
            tts=self.tts,
        )

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
        print(f"\n[1/3] Transcribing audio ({source_lang})...")
        print(f"\n[2/3] Translating {source_lang} → {target_lang}...")
        print(f"\n[3/3] Streaming speech ({target_lang})...")

        chunk_count = 0
        for event in self.pipeline.translate(
            input_audio=input_audio,
            source_lang=source_lang,
            target_lang=target_lang,
            streaming_interval=streaming_interval,
        ):
            if isinstance(event, TranslationMetadata):
                print(f'      Transcribed: "{event.transcription}"')
                print(f'      Translated: "{event.translation}"')
                yield event.to_dict()
                continue

            assert isinstance(event, AudioChunkResult)
            print(f"      Chunk {event.chunk_index}: {len(event.data)} bytes")
            yield event.to_dict()
            chunk_count += 1

        print(f"\n{'=' * 60}")
        print(f"✓ STREAMING TRANSLATION COMPLETE ({chunk_count} chunks)")
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
