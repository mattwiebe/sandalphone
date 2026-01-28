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
            model_path = Path(__file__).parent.parent.parent / "models" / "qwen-7b-4bit"

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
        # Create translation prompt with few-shot examples to guide the model
        if source_lang == "es" and target_lang == "en":
            prompt = f"""Spanish: Hola
English: Hello

Spanish: ¿Cómo estás?
English: How are you?

Spanish: Buenos días
English: Good morning

Spanish: {text}
English:"""
        elif source_lang == "en" and target_lang == "es":
            prompt = f"""English: Hello
Spanish: Hola

English: How are you?
Spanish: ¿Cómo estás?

English: Good morning
Spanish: Buenos días

English: {text}
Spanish:"""
        else:
            raise ValueError(f"Unsupported language pair: {source_lang} -> {target_lang}")

        # Generate translation
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=50,  # Keep it short to prevent hallucinations
            verbose=False
        )

        # Extract just the translation (remove prompt echo)
        translation = response.strip()

        # Sometimes the model adds extra explanation - try to extract just the translation
        # Look for the actual translation after the prompt
        if source_lang == "es":
            if "English:" in translation:
                translation = translation.split("English:")[-1].strip()
        else:
            if "Spanish:" in translation:
                translation = translation.split("Spanish:")[-1].strip()

        # Remove any trailing explanations
        if "\n\n" in translation:
            translation = translation.split("\n\n")[0].strip()

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
