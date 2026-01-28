"""
Translation client using MLX-optimized Qwen model.
Handles Spanish <-> English translation via local LLM.
"""
from mlx_lm import load, generate
from pathlib import Path


class TranslationClient:
    def __init__(self, model_path=None):
        """
        Initialize translation client.

        Args:
            model_path: Path to MLX model directory
        """
        if model_path is None:
            model_path = Path(__file__).parent.parent.parent / "models" / "qwen-14b-4bit"

        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model not found: {self.model_path}")

        print(f"Loading translation model from {self.model_path}...")
        self.model, self.tokenizer = load(str(self.model_path))
        print("Translation model loaded!")

    def translate(self, text, source_lang="es", target_lang="en"):
        """
        Translate text from source to target language.

        Args:
            text: Text to translate
            source_lang: Source language code (es or en)
            target_lang: Target language code (es or en)

        Returns:
            Translated text
        """
        # Use simple, direct instruction - Qwen models work best with clear tasks
        if source_lang == "es" and target_lang == "en":
            # Just ask for the translation directly
            prompt = f"Translate to English: {text}\n\nEnglish translation:"
        elif source_lang == "en" and target_lang == "es":
            prompt = f"Translate to Spanish: {text}\n\nSpanish translation:"
        else:
            raise ValueError(f"Unsupported language pair: {source_lang} -> {target_lang}")

        # Generate translation
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=30,  # Short to prevent over-explaining
            verbose=False
        )

        # Extract just the translation (remove prompt echo and explanations)
        translation = response.strip()

        import re

        # Aggressive cleanup: Remove anything after explanation keywords
        # Use regex to catch all variations (with or without preceding space/punctuation)
        pattern = r'[\s.!?]+(This|You|It|The)\s'
        match = re.search(pattern, translation)
        if match:
            translation = translation[:match.start()].strip()

        # Also check for period/question mark followed by ANY capital letter
        if not match:  # Only if we haven't already truncated
            match = re.search(r'[.!?]\s+[A-Z]', translation)
            if match:
                translation = translation[:match.start() + 1].strip()

        # Clean up whitespace
        translation = ' '.join(translation.split()).strip()

        return translation


if __name__ == "__main__":
    # Test the client
    client = TranslationClient()

    # Test Spanish to English
    spanish_text = "¿Cuál es tu mejor precio?"
    print(f"Spanish: {spanish_text}")
    english = client.translate(spanish_text, "es", "en")
    print(f"English: {english}\n")

    # Test English to Spanish
    english_text = "What is your best price?"
    print(f"English: {english_text}")
    spanish = client.translate(english_text, "en", "es")
    print(f"Spanish: {spanish}")
