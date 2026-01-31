"""
NLLB-200 translation client for Spanish <-> English translation.
Uses Facebook's NLLB-200-distilled-600M model (only ~600MB vs 7.7GB Qwen).

Handles 512 token limit by splitting long texts into sentences.
"""
from pathlib import Path
import re
import gc
from typing import List

try:
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class NLLBTranslationClient:
    """
    NLLB-200 translation client with automatic sentence batching.

    Memory usage: ~1-2GB (vs 10-12GB for Qwen-14B)
    Quality: Excellent for translation (purpose-built model)
    """

    # Language codes for NLLB
    LANG_CODES = {
        "en": "eng_Latn",  # English
        "es": "spa_Latn",  # Spanish
    }

    def __init__(self, model_name: str = "facebook/nllb-200-distilled-600M", device: str = None):
        """
        Initialize NLLB translation client.

        Args:
            model_name: HuggingFace model name or local path
            device: Device to use ("cpu", "mps", "cuda", or None for auto)
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers library not available. Install with:\n"
                "uv add transformers torch"
            )

        print(f"Loading NLLB model: {model_name}...")
        self.model_name = model_name

        # Auto-detect best device
        if device is None:
            if torch.backends.mps.is_available():
                device = "mps"  # Apple Silicon GPU
            elif torch.cuda.is_available():
                device = "cuda"
            else:
                device = "cpu"

        self.device = device
        print(f"Using device: {device}")

        # Load model and tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.eval()  # Inference mode

        print(f"✓ NLLB model loaded (~600MB)")

    def translate(self, text: str, source_lang: str = "es", target_lang: str = "en") -> str:
        """
        Translate text from source to target language.

        Automatically handles long texts by splitting into sentences
        to stay within 512 token limit.

        Args:
            text: Text to translate
            source_lang: Source language code (es or en)
            target_lang: Target language code (en or es)

        Returns:
            Translated text
        """
        # Get NLLB language codes
        src_code = self.LANG_CODES.get(source_lang)
        tgt_code = self.LANG_CODES.get(target_lang)

        if not src_code or not tgt_code:
            raise ValueError(
                f"Unsupported language pair: {source_lang} -> {target_lang}\n"
                f"Supported: {list(self.LANG_CODES.keys())}"
            )

        # Split text into sentences to handle 512 token limit
        sentences = self._split_sentences(text)

        # Translate each sentence (or batch small sentences together)
        translated_sentences = []
        current_batch = []
        current_tokens = 0

        for sentence in sentences:
            # Check token count for this sentence
            tokens = self.tokenizer.encode(sentence, add_special_tokens=False)
            sentence_token_count = len(tokens)

            # If single sentence exceeds limit, translate it alone (will truncate)
            if sentence_token_count > 450:  # Leave margin for special tokens
                if current_batch:
                    # Translate accumulated batch first
                    batch_text = " ".join(current_batch)
                    translated_sentences.append(
                        self._translate_single(batch_text, src_code, tgt_code)
                    )
                    current_batch = []
                    current_tokens = 0

                # Translate long sentence alone
                translated_sentences.append(
                    self._translate_single(sentence, src_code, tgt_code)
                )

            # If adding this sentence would exceed limit, translate current batch
            elif current_tokens + sentence_token_count > 450:
                if current_batch:
                    batch_text = " ".join(current_batch)
                    translated_sentences.append(
                        self._translate_single(batch_text, src_code, tgt_code)
                    )
                current_batch = [sentence]
                current_tokens = sentence_token_count

            # Otherwise, add to current batch
            else:
                current_batch.append(sentence)
                current_tokens += sentence_token_count

        # Translate remaining batch
        if current_batch:
            batch_text = " ".join(current_batch)
            translated_sentences.append(
                self._translate_single(batch_text, src_code, tgt_code)
            )

        # Join all translated sentences
        return " ".join(translated_sentences)

    def _translate_single(self, text: str, src_code: str, tgt_code: str) -> str:
        """Translate a single text segment (must fit in 512 tokens)."""
        # Set source language
        self.tokenizer.src_lang = src_code

        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=512
        ).to(self.device)

        # Generate translation
        with torch.no_grad():
            # Get target language token ID
            tgt_lang_id = self.tokenizer.convert_tokens_to_ids(tgt_code)

            # Use greedy decoding instead of beam search to reduce memory
            # Beam search creates multiple candidates that leak on MPS
            translated_tokens = self.model.generate(
                **inputs,
                forced_bos_token_id=tgt_lang_id,
                max_length=512,
                do_sample=False,  # Greedy decoding
                num_beams=1,      # No beam search (fixes MPS memory leak)
            )

        # Move to CPU immediately to free GPU memory
        translated_tokens_cpu = translated_tokens.cpu()

        # Decode
        translation = self.tokenizer.batch_decode(
            translated_tokens_cpu,
            skip_special_tokens=True
        )[0]

        # Aggressive cleanup
        del inputs
        del translated_tokens
        del translated_tokens_cpu

        # Force garbage collection and clear GPU cache
        gc.collect()
        if self.device == "mps":
            torch.mps.empty_cache()
        elif self.device == "cuda":
            torch.cuda.empty_cache()

        return translation.strip()

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for batching.

        Uses simple regex-based sentence splitting.
        Preserves sentence boundaries for natural translations.
        """
        # Simple sentence splitter (handles . ! ? with spaces)
        # For production, could use nltk or spacy for better splitting
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        # If no sentence boundaries found, return whole text
        if not sentences:
            sentences = [text]

        return sentences


def main():
    """Test the NLLB translation client."""
    print("Testing NLLB Translation Client\n")

    client = NLLBTranslationClient()

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

    # Test 3: Longer text (tests batching)
    print("=" * 60)
    print("Test 3: Longer text (multi-sentence)")
    long_spanish = (
        "Hola, ¿cómo estás? Me gustaría comprar este producto. "
        "¿Cuánto cuesta? ¿Tienen descuentos disponibles? "
        "Necesito enviarlo a México."
    )
    print(f"ES: {long_spanish}")
    long_english = client.translate(long_spanish, "es", "en")
    print(f"EN: {long_english}\n")

    # Test 4: Simple greeting (the one that made Qwen-7B hallucinate)
    print("=" * 60)
    print("Test 4: Simple greeting (Qwen-7B hallucination test)")
    greeting = "Hola, ¿cómo estás?"
    print(f"ES: {greeting}")
    greeting_en = client.translate(greeting, "es", "en")
    print(f"EN: {greeting_en}\n")

    print("=" * 60)
    print("✓ All tests complete!")


if __name__ == "__main__":
    main()
