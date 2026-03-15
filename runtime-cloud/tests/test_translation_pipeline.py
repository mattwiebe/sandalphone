from unittest.mock import Mock

import pytest
from pipecat.frames.frames import InterimTranscriptionFrame, TranscriptionFrame
from pipecat.tests.utils import run_test
from pipecat.transcriptions.language import Language

from runtime_cloud_service.translation_pipeline import (
    DeepLTranslateClient,
    TranslationProcessor,
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


@pytest.mark.anyio
async def test_translation_processor_emits_translation_message_and_tts_frames() -> None:
    translator = _FakeTranslator()
    processor = TranslationProcessor(
        config=TranslationPipelineConfig(
            trusted_identity="trusted-matt",
            source_language=Language.ES_MX,
            target_language=Language.EN_US,
        ),
        translator=translator,
    )
    transcription = TranscriptionFrame(
        text="hola",
        user_id="sip-participant-1",
        timestamp="2026-03-15T06:00:00Z",
        language=Language.ES_MX,
        finalized=True,
    )

    down_frames, _ = await run_test(
        processor,
        frames_to_send=[transcription],
    )

    assert translator.calls == [("hola", Language.ES_MX, Language.EN_US)]
    assert [type(frame).__name__ for frame in down_frames] == [
        "TranslationFrame",
        "LiveKitOutputTransportMessageFrame",
        "TTSSpeakFrame",
    ]
    assert down_frames[1].participant_id == "trusted-matt"


@pytest.mark.anyio
async def test_translation_processor_ignores_interim_frames_in_pipeline() -> None:
    translator = _FakeTranslator()
    processor = TranslationProcessor(
        config=TranslationPipelineConfig(
            trusted_identity="trusted-matt",
            source_language=Language.ES_MX,
            target_language=Language.EN_US,
        ),
        translator=translator,
    )
    transcription = InterimTranscriptionFrame(
        text="ho",
        user_id="sip-participant-1",
        timestamp="2026-03-15T06:00:00Z",
        language=Language.ES_MX,
    )

    down_frames, _ = await run_test(
        processor,
        frames_to_send=[transcription],
    )

    assert down_frames == []
    assert translator.calls == []


def test_deepl_translate_client_uses_auth_header_and_text_params() -> None:
    response = Mock()
    response.json.return_value = {"translations": [{"text": "hello there"}]}
    response.raise_for_status.return_value = None

    session = Mock()
    session.post.return_value = response

    client = DeepLTranslateClient(api_key="test-key", session=session)

    translated = client.translate(
        "hola",
        source_language=Language.ES_MX,
        target_language=Language.EN_US,
    )

    assert translated == "hello there"
    session.post.assert_called_once_with(
        "https://api-free.deepl.com/v2/translate",
        data={
            "text": "hola",
            "source_lang": "ES",
            "target_lang": "EN-US",
        },
        headers={"Authorization": "DeepL-Auth-Key test-key"},
        timeout=10,
    )


def test_deepl_translate_client_raises_for_missing_translation_text() -> None:
    response = Mock()
    response.json.return_value = {"translations": [{}]}
    response.raise_for_status.return_value = None

    session = Mock()
    session.post.return_value = response

    client = DeepLTranslateClient(api_key="test-key", session=session)

    with pytest.raises(ValueError, match="DeepL response did not include translated text"):
        client.translate(
            "hola",
            source_language=Language.ES_MX,
            target_language=Language.EN_US,
        )
