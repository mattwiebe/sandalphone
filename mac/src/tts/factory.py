"""
Factory for creating TTS provider instances based on configuration.
Supports multiple TTS providers (Qwen, VibeVoice) with runtime selection.
"""

import os
from tts.base import TTSProvider
from tts.qwen_tts_client import QwenTTSClient
from tts.vibevoice_client import VibeVoiceClient


def create_tts_provider(provider: str = None) -> TTSProvider:
    """
    Create a TTS provider based on configuration.

    The provider is selected from the TTS_PROVIDER environment variable.
    If not set, defaults to "vibevoice".

    Args:
        provider: Provider name ("qwen" or "vibevoice").
                 If None, reads from TTS_PROVIDER env var.
                 Defaults to "vibevoice" if not specified.

    Returns:
        TTSProvider instance (QwenTTSClient or VibeVoiceClient)

    Raises:
        ValueError: If an unknown provider name is specified

    Examples:
        # Use default (VibeVoice)
        tts = create_tts_provider()

        # Explicitly use Qwen
        tts = create_tts_provider("qwen")

        # Use env var: TTS_PROVIDER=qwen
        tts = create_tts_provider()
    """
    if provider is None:
        provider = os.getenv("TTS_PROVIDER", "vibevoice").lower()
    else:
        provider = provider.lower()

    if provider == "vibevoice":
        print(f"TTS Provider: VibeVoice")
        return VibeVoiceClient()
    elif provider == "qwen":
        print(f"TTS Provider: Qwen")
        return QwenTTSClient()
    else:
        raise ValueError(
            f"Unknown TTS provider: '{provider}'. "
            f"Valid options: 'qwen', 'vibevoice'"
        )
