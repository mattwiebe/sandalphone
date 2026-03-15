from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.transcriptions.language import Language

from runtime_cloud_service.translation_pipeline import (
    TranslationPipelineConfig,
    build_translation_output_frames,
)


class _FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Language, Language]] = []

    def translate(self, text: str, *, source_language: Language, target_language: Language) -> str:
        self.calls.append((text, source_language, target_language))
        return "hello there"


def test_translation_output_frames_include_private_message_and_tts() -> None:
    translator = _FakeTranslator()
    config = TranslationPipelineConfig(
        trusted_identity="trusted-matt",
        source_language=Language.ES_MX,
        target_language=Language.EN_US,
    )
    transcription = TranscriptionFrame(
        text="hola",
        user_id="sip-participant-1",
        timestamp="2026-03-15T06:00:00Z",
        language=Language.ES_MX,
        finalized=True,
    )

    frames = build_translation_output_frames(
        config=config,
        transcription=transcription,
        translator=translator,
    )

    assert translator.calls == [("hola", Language.ES_MX, Language.EN_US)]
    assert frames[0].text == "hello there"
    assert frames[1].participant_id == "trusted-matt"
    assert frames[2].text == "hello there"


def test_interim_transcriptions_do_not_emit_output() -> None:
    translator = _FakeTranslator()
    config = TranslationPipelineConfig(
        trusted_identity="trusted-matt",
        source_language=Language.ES_MX,
        target_language=Language.EN_US,
    )
    transcription = InterimTranscriptionFrame(
        text="ho",
        user_id="sip-participant-1",
        timestamp="2026-03-15T06:00:00Z",
        language=Language.ES_MX,
    )

    frames = build_translation_output_frames(
        config=config,
        transcription=transcription,
        translator=translator,
    )

    assert frames == []
    assert translator.calls == []
