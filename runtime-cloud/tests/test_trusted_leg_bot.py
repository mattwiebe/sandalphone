import pytest
from pipecat.frames.frames import UserAudioRawFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.tests.utils import run_test
from pipecat.frames.frames import TTSSpeakFrame, TranscriptionFrame, TranslationFrame
from pipecat.transcriptions.language import Language

from runtime_cloud_service.trusted_leg_bot import (
    AudioNormalizeForSTTProcessor,
    build_provider_bundle_from_env,
    normalize_audio_for_stt,
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


def test_build_provider_bundle_from_env_uses_new_provider_keys(monkeypatch) -> None:
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "assembly")
    monkeypatch.setenv("ASSEMBLYAI_SAMPLE_RATE", "16000")
    monkeypatch.setenv("ASSEMBLYAI_SPEECH_MODEL", "universal-streaming-multilingual")
    monkeypatch.setenv("DEEPL_API_KEY", "deepl")
    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "voice-123")

    providers = build_provider_bundle_from_env()

    assert providers.assemblyai_api_key == "assembly"
    assert providers.assemblyai_sample_rate == 16000
    assert providers.assemblyai_speech_model == "universal-streaming-multilingual"
    assert providers.deepl_api_key == "deepl"
    assert providers.cartesia_api_key == "cartesia"
    assert providers.cartesia_voice_id == "voice-123"


def test_build_provider_bundle_from_env_defaults_assembly_to_16khz(monkeypatch) -> None:
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "assembly")
    monkeypatch.delenv("ASSEMBLYAI_SAMPLE_RATE", raising=False)
    monkeypatch.setenv("DEEPL_API_KEY", "deepl")
    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia")
    monkeypatch.setenv("CARTESIA_VOICE_ID", "voice-123")

    providers = build_provider_bundle_from_env()

    assert providers.assemblyai_sample_rate == 16000


def test_normalize_audio_for_stt_downmixes_stereo_to_mono() -> None:
    stereo_frame = (
        (1000).to_bytes(2, "little", signed=True)
        + (-1000).to_bytes(2, "little", signed=True)
    ) * 10

    normalized = normalize_audio_for_stt(
        audio=stereo_frame,
        num_channels=2,
        sample_rate=48000,
        target_sample_rate=48000,
    )

    assert len(normalized) == len(stereo_frame) // 2


def test_normalize_audio_for_stt_resamples_to_target_rate() -> None:
    mono_frame = (1000).to_bytes(2, "little", signed=True) * 480

    normalized = normalize_audio_for_stt(
        audio=mono_frame,
        num_channels=1,
        sample_rate=48000,
        target_sample_rate=16000,
    )

    assert len(normalized) < len(mono_frame)


@pytest.mark.anyio
async def test_audio_normalize_processor_rewrites_frame_for_stt() -> None:
    processor = AudioNormalizeForSTTProcessor(target_sample_rate=16000)
    frame = UserAudioRawFrame(
        user_id="caller-1",
        audio=(1000).to_bytes(2, "little", signed=True) * 480,
        sample_rate=48000,
        num_channels=1,
    )

    down_frames, _ = await run_test(
        processor,
        frames_to_send=[frame],
    )

    assert len(down_frames) == 1
    normalized = down_frames[0]
    assert isinstance(normalized, UserAudioRawFrame)
    assert normalized.user_id == "caller-1"
    assert normalized.sample_rate == 16000
    assert normalized.num_channels == 1
    assert len(normalized.audio) < len(frame.audio)
