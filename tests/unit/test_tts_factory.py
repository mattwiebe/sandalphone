import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mac" / "src"))

import tts.factory as factory


class _FakeVibeVoiceClient:
    pass


class _FakeQwenTTSClient:
    pass


@pytest.mark.unit
def test_create_tts_provider_defaults_to_vibevoice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    monkeypatch.setattr(factory, "_load_vibevoice_client", lambda: _FakeVibeVoiceClient())

    provider = factory.create_tts_provider()

    assert isinstance(provider, _FakeVibeVoiceClient)


@pytest.mark.unit
def test_create_tts_provider_uses_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TTS_PROVIDER", "qwen")
    monkeypatch.setattr(factory, "_load_qwen_client", lambda: _FakeQwenTTSClient())

    provider = factory.create_tts_provider()

    assert isinstance(provider, _FakeQwenTTSClient)


@pytest.mark.unit
def test_create_tts_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown TTS provider"):
        factory.create_tts_provider("does-not-exist")
