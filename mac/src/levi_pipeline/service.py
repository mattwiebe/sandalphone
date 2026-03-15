from pathlib import Path
from typing import Generator

from .interfaces import SpeechSynthesizer, SpeechToText, StreamingSpeechSynthesizer, Translator
from .models import AudioChunkResult, TranslationMetadata, TranslationResult


class BatchTranslationPipeline:
    def __init__(self, stt: SpeechToText, translator: Translator, tts: SpeechSynthesizer) -> None:
        self.stt = stt
        self.translator = translator
        self.tts = tts

    def translate(
        self,
        input_audio: str | Path,
        source_lang: str = "es",
        target_lang: str = "en",
        output_audio: str | Path | None = None,
    ) -> TranslationResult:
        transcription = self.stt.transcribe(input_audio, language=source_lang)
        translation = self.translator.translate(transcription, source_lang, target_lang)
        output_audio_path = self.tts.synthesize(
            text=translation,
            output_file=output_audio,
            language=target_lang,
        )

        return TranslationResult(
            transcription=transcription,
            translation=translation,
            output_audio=Path(output_audio_path),
        )


class StreamingTranslationPipeline:
    def __init__(self, stt: SpeechToText, translator: Translator, tts: SpeechSynthesizer) -> None:
        self.stt = stt
        self.translator = translator
        self.tts = tts

    def translate(
        self,
        input_audio: str | Path,
        source_lang: str = "es",
        target_lang: str = "en",
        streaming_interval: float = 2.0,
    ) -> Generator[TranslationMetadata | AudioChunkResult, None, None]:
        transcription = self.stt.transcribe(input_audio, language=source_lang)
        translation = self.translator.translate(transcription, source_lang, target_lang)

        yield TranslationMetadata(
            transcription=transcription,
            translation=translation,
        )

        if isinstance(self.tts, StreamingSpeechSynthesizer):
            for chunk_index, audio_chunk in enumerate(
                self.tts.synthesize_streaming(
                    text=translation,
                    language=target_lang,
                    streaming_interval=streaming_interval,
                )
            ):
                yield AudioChunkResult(data=audio_chunk, chunk_index=chunk_index)
            return

        output_audio = self.tts.synthesize(text=translation, language=target_lang)
        yield AudioChunkResult(data=Path(output_audio).read_bytes(), chunk_index=0)
