"""
Factory for creating translation client instances based on configuration.
Supports multiple translation providers (Qwen, NLLB) with runtime selection.
"""

import os
from typing import Protocol


class TranslationProvider(Protocol):
    """Protocol for translation providers."""

    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        """Translate text from source to target language."""
        ...


def create_translation_client(provider: str = None) -> TranslationProvider:
    """
    Create a translation client based on configuration.

    The provider is selected from the TRANSLATION_PROVIDER environment variable.
    If not set, defaults to "qwen" (most reliable).

    Args:
        provider: Provider name ("qwen", "nllb", or "deepl").
                 If None, reads from TRANSLATION_PROVIDER env var.
                 Defaults to "qwen" if not specified.

    Returns:
        TranslationProvider instance

    Raises:
        ValueError: If an unknown provider name is specified

    Examples:
        # Use default (Qwen)
        translator = create_translation_client()

        # Use DeepL API (best quality, no memory)
        translator = create_translation_client("deepl")

        # Use env var: TRANSLATION_PROVIDER=deepl
        translator = create_translation_client()

    Environment Variables:
        TRANSLATION_PROVIDER: "qwen", "nllb", or "deepl" (default: "qwen")
        DEEPL_API_KEY: API key for DeepL (required if using "deepl")
        NLLB_MODEL: Model name for NLLB (default: "facebook/nllb-200-distilled-600M")
        QWEN_MODEL_PATH: Path to Qwen model (default: "models/qwen-14b-4bit")
    """
    if provider is None:
        provider = os.getenv("TRANSLATION_PROVIDER", "qwen").lower()
    else:
        provider = provider.lower()

    if provider == "deepl":
        print(f"Translation Provider: DeepL API (cloud, 0GB memory)")
        from llm.deepl_translation_client import DeepLTranslationClient

        return DeepLTranslationClient()

    elif provider == "nllb":
        print(f"Translation Provider: NLLB-200 (~1-2GB memory)")
        from llm.nllb_translation_client import NLLBTranslationClient

        model_name = os.getenv("NLLB_MODEL", "facebook/nllb-200-distilled-600M")
        return NLLBTranslationClient(model_name=model_name)

    elif provider == "qwen":
        print(f"Translation Provider: Qwen-14B (~10-12GB memory)")
        from llm.translation_client import TranslationClient

        model_path = os.getenv("QWEN_MODEL_PATH")
        if model_path:
            return TranslationClient(model_path=model_path)
        else:
            return TranslationClient()

    else:
        raise ValueError(
            f"Unknown translation provider: '{provider}'. "
            f"Valid options: 'qwen', 'nllb', 'deepl'"
        )


if __name__ == "__main__":
    """Test the factory with both providers."""
    import sys

    print("=" * 60)
    print("Testing Translation Factory")
    print("=" * 60)

    # Test NLLB
    print("\n1. Testing NLLB provider:")
    try:
        nllb_client = create_translation_client("nllb")
        result = nllb_client.translate("Hola, ¿cómo estás?", "es", "en")
        print(f"   ES: Hola, ¿cómo estás?")
        print(f"   EN: {result}")
        print("   ✓ NLLB working!")
    except Exception as e:
        print(f"   ✗ NLLB error: {e}")

    # Test Qwen (optional)
    if "--test-qwen" in sys.argv:
        print("\n2. Testing Qwen provider:")
        try:
            qwen_client = create_translation_client("qwen")
            result = qwen_client.translate("Hola, ¿cómo estás?", "es", "en")
            print(f"   ES: Hola, ¿cómo estás?")
            print(f"   EN: {result}")
            print("   ✓ Qwen working!")
        except Exception as e:
            print(f"   ✗ Qwen error: {e}")

    print("\n" + "=" * 60)
    print("Factory test complete!")
