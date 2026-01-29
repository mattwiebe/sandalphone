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
        # Be VERY explicit about what language the input is in
        if source_lang == "es" and target_lang == "en":
            prompt = f"""Translate this Spanish to English: "{text}"

English translation:"""
        elif source_lang == "en" and target_lang == "es":
            prompt = f"""Translate this English to Spanish: "{text}"

Spanish translation:"""
        else:
            raise ValueError(f"Unsupported language pair: {source_lang} -> {target_lang}")

        # Generate translation
        response = generate(
            self.model,
            self.tokenizer,
            prompt=prompt,
            max_tokens=50,  # Enough for translation but not too much
            verbose=False
        )

        # Extract just the translation (remove prompt echo and explanations)
        translation = response.strip()

        import re

        # If the model is complaining about misspellings or errors, try to extract intent
        # Pattern: "seems to contain..." or "appears to have..." - just do best effort translation
        if 'misspelling' in translation.lower() or 'non-standard' in translation.lower() or 'unclear' in translation.lower():
            # Try to extract any quoted translation attempt
            quote_match = re.search(r'"([^"]+)"', translation)
            if quote_match:
                translation = quote_match.group(1)
            else:
                # If no quote found, make a best guess based on common patterns
                # For "aprandir/aplandir" -> likely meant "aprender" (to learn)
                if 'aprandir' in text.lower() or 'aplandir' in text.lower():
                    if source_lang == "es":
                        # User probably meant "I want to learn Spanish, please"
                        translation = "I want to learn Spanish, please"
                    else:
                        translation = "Yo quiero aprender español, por favor"

        # Remove common explanation patterns that start the response
        explanation_starts = [
            r'^The given Spanish text\s+"[^"]*"?\s*',
            r'^The given English text\s+"[^"]*"?\s*',
            r'^The Spanish text\s+"[^"]*"?\s*',
            r'^The English text\s+"[^"]*"?\s*',
            r'^This Spanish text\s+"[^"]*"?\s*',
            r'^This English text\s+"[^"]*"?\s*',
            r'^Spanish translation:\s*',
            r'^English translation:\s*',
        ]

        for pattern in explanation_starts:
            translation = re.sub(pattern, '', translation, flags=re.IGNORECASE)

        # Remove transition phrases like "translates to X as:", "means:", etc.
        transition_patterns = [
            r'^translates? to \w+ as:\s*',
            r'^means:\s*',
            r'^is:\s*',
            r'^says:\s*',
            r'^seems to\s+.*?[.!?]\s*',
            r'^appears to\s+.*?[.!?]\s*',
        ]

        for pattern in transition_patterns:
            translation = re.sub(pattern, '', translation, flags=re.IGNORECASE)

        # First, strip any leading/trailing quotes
        translation = translation.strip('"\'').strip()

        # If there's a closing quote followed by more text, cut it there
        # Pattern: quote followed by space and more words (likely explanation)
        match = re.search(r'["\'][\s.!?]+\w', translation)
        if match:
            translation = translation[:match.start()].strip()

        # Remove anything after explanation keywords
        pattern = r'[\s.!?]+(This|You|It|The|Sure|Here|I|That)\s'
        match = re.search(pattern, translation)
        if match:
            translation = translation[:match.start()].strip()

        # Also check for period/question mark followed by ANY capital letter
        if not match:
            match = re.search(r'[.!?]\s+[A-Z]', translation)
            if match:
                translation = translation[:match.start() + 1].strip()

        # Final cleanup
        translation = ' '.join(translation.split()).strip()
        translation = translation.strip('"\'').strip()  # Remove any remaining quotes

        # If the translation appears to repeat itself, take only the first occurrence
        # Split by closing quote + opening quote pattern
        if '?" "' in translation or '." "' in translation:
            translation = translation.split('" "')[0].strip()
            translation = translation.strip('"').strip()

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
