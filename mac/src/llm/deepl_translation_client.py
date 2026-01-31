"""
DeepL API translation client for Spanish <-> English translation.
Uses cloud API - no local model, no memory usage, excellent quality.

Free tier: 500k characters/month
"""
import os
from typing import Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class DeepLTranslationClient:
    """
    DeepL API translation client.

    Memory usage: 0 GB (cloud API)
    Quality: Excellent (often better than local models)
    Latency: 150-300ms
    Cost: Free tier 500k chars/month, then $5.49/month for 1M chars
    """

    LANG_CODES = {
        "en": "EN-US",
        "es": "ES",
    }

    API_BASE_URL = "https://api-free.deepl.com/v2"  # Free tier
    # API_BASE_URL = "https://api.deepl.com/v2"  # Pro tier

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DeepL translation client.

        Args:
            api_key: DeepL API key (or set DEEPL_API_KEY env var)
                    Get free key at: https://www.deepl.com/pro-api
        """
        if not REQUESTS_AVAILABLE:
            raise ImportError(
                "requests library not available. Install with:\n"
                "uv add requests"
            )

        self.api_key = api_key or os.getenv("DEEPL_API_KEY")

        if not self.api_key:
            raise ValueError(
                "DeepL API key required. Set DEEPL_API_KEY env var or pass api_key.\n"
                "Get free API key at: https://www.deepl.com/pro-api"
            )

        print(f"✓ DeepL API client initialized (cloud-based, no local memory)")

    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        """
        Translate text using DeepL API.

        Args:
            text: Text to translate
            source_lang: Source language code (es or en)
            target_lang: Target language code (en or es)

        Returns:
            Translated text
        """
        src_code = self.LANG_CODES.get(source_lang)
        tgt_code = self.LANG_CODES.get(target_lang)

        if not src_code or not tgt_code:
            raise ValueError(
                f"Unsupported language pair: {source_lang} -> {target_lang}\n"
                f"Supported: {list(self.LANG_CODES.keys())}"
            )

        # Call DeepL API
        url = f"{self.API_BASE_URL}/translate"
        headers = {
            "Authorization": f"DeepL-Auth-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "text": [text],
            "source_lang": src_code,
            "target_lang": tgt_code
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()

            result = response.json()
            translation = result["translations"][0]["text"]
            return translation.strip()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                raise RuntimeError(
                    "Invalid DeepL API key. Get a free key at:\n"
                    "https://www.deepl.com/pro-api"
                )
            elif e.response.status_code == 456:
                raise RuntimeError(
                    "DeepL API quota exceeded. Upgrade at:\n"
                    "https://www.deepl.com/pro-api"
                )
            else:
                raise RuntimeError(f"DeepL API error: {e}")

        except Exception as e:
            raise RuntimeError(f"Translation failed: {e}")


def main():
    """Test the DeepL translation client."""
    print("Testing DeepL Translation Client\n")

    # Check for API key
    api_key = os.getenv("DEEPL_API_KEY")
    if not api_key:
        print("❌ DEEPL_API_KEY not set!")
        print("\nTo test:")
        print("1. Get free API key: https://www.deepl.com/pro-api")
        print("2. export DEEPL_API_KEY='your-key-here'")
        print("3. Run this script again")
        return

    client = DeepLTranslationClient()

    # Test 1: Spanish to English (short)
    print("=" * 60)
    print("Test 1: Short Spanish → English")
    spanish_text = "¿Cuál es tu mejor precio?"
    print(f"ES: {spanish_text}")
    english = client.translate(spanish_text, "es", "en")
    print(f"EN: {english}\n")

    # Test 2: English to Spanish (short)
    print("=" * 60)
    print("Test 2: Short English → Spanish")
    english_text = "What is your best price?"
    print(f"EN: {english_text}")
    spanish = client.translate(english_text, "en", "es")
    print(f"ES: {spanish}\n")

    # Test 3: Simple greeting (the one that made Qwen-7B hallucinate)
    print("=" * 60)
    print("Test 3: Simple greeting (Qwen-7B hallucination test)")
    greeting = "Hola, ¿cómo estás?"
    print(f"ES: {greeting}")
    greeting_en = client.translate(greeting, "es", "en")
    print(f"EN: {greeting_en}\n")

    # Test 4: The problematic transcription from the logs
    print("=" * 60)
    print("Test 4: Problematic transcription from logs")
    problematic = "Yocero, aplandir a español"
    print(f"Original transcription: {problematic}")
    translation = client.translate(problematic, "es", "en")
    print(f"DeepL translation: {translation}")
    print("(Note: garbage in, garbage out - but at least it won't hallucinate!)\n")

    print("=" * 60)
    print("✓ All tests complete!")


if __name__ == "__main__":
    main()
