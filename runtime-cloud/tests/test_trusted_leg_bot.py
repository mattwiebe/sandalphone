from pipecat.frames.frames import TTSSpeakFrame, TranscriptionFrame, TranslationFrame
from pipecat.transcriptions.language import Language

from runtime_cloud_service.trusted_leg_bot import (
    TrustedLegBotConfig,
    build_private_audio_permissions,
    build_trusted_translation_frames,
)


def test_build_private_audio_permissions_targets_only_trusted_identity() -> None:
    permissions = build_private_audio_permissions("trusted-matt")

    assert len(permissions) == 1
    assert permissions[0].participant_identity == "trusted-matt"
    assert permissions[0].allow_all is True


def test_build_trusted_translation_frames_emit_private_metadata_and_tts() -> None:
    transcription = TranscriptionFrame(
        text="hola, buenas tardes",
        user_id="sip-participant-1",
        timestamp="2026-03-15T05:00:00Z",
        language=Language.ES_MX,
        finalized=True,
    )

    frames = build_trusted_translation_frames(
        config=TrustedLegBotConfig(
            room_name="call-main",
            trusted_identity="trusted-matt",
            source_language=Language.ES_MX,
            target_language=Language.EN_US,
        ),
        transcription=transcription,
        translated_text="hello, good afternoon",
    )

    assert isinstance(frames[0], TranslationFrame)
    assert frames[0].text == "hello, good afternoon"
    assert frames[0].language == Language.EN_US

    assert frames[1].participant_id == "trusted-matt"
    assert "hello, good afternoon" in frames[1].message
    assert "sip-participant-1" in frames[1].message

    assert isinstance(frames[2], TTSSpeakFrame)
    assert frames[2].text == "hello, good afternoon"
