# NLLB-200 Migration Guide

## Overview

NLLB-200 (No Language Left Behind) is a specialized translation model that offers:
- **90% less memory**: ~1-2GB vs 10-12GB for Qwen-14B
- **Better translation quality**: Purpose-built for translation (not a general LLM)
- **No hallucinations**: Dedicated translation model doesn't produce random text
- **Fast inference**: Optimized for translation tasks

## Quick Start

### 1. Install Dependencies

Already done:
```bash
uv add --optional mac transformers torch sentencepiece protobuf
```

### 2. Switch to NLLB (Default)

Set environment variable:
```bash
export TRANSLATION_PROVIDER=nllb
```

Or add to `.env`:
```bash
TRANSLATION_PROVIDER=nllb
```

### 3. Start the Service

```bash
# Mac backend with NLLB (default)
uv run --extra mac python mac/src/main.py

# Or explicitly set NLLB
TRANSLATION_PROVIDER=nllb uv run --extra mac python mac/src/main.py
```

## Configuration Options

### Translation Provider Selection

```bash
# Use NLLB (default, lightweight)
TRANSLATION_PROVIDER=nllb

# Use Qwen (high memory, but you already have it)
TRANSLATION_PROVIDER=qwen
```

### NLLB Model Selection

```bash
# Default: 600M model (best balance)
NLLB_MODEL=facebook/nllb-200-distilled-600M

# Larger: 1.3B model (better quality, ~2-3GB memory)
NLLB_MODEL=facebook/nllb-200-distilled-1.3B

# Larger: 3.3B model (best quality, ~5-6GB memory)
NLLB_MODEL=facebook/nllb-200-3.3B
```

### Qwen Model Path (if using Qwen)

```bash
QWEN_MODEL_PATH=/Users/matt/levi/mac/models/qwen-14b-4bit
```

## Testing

### Test NLLB Standalone

```bash
cd /Users/matt/levi/mac/src
uv run --extra mac python llm/nllb_translation_client.py
```

Expected output:
```
Loading NLLB model: facebook/nllb-200-distilled-600M...
Using device: mps
✓ NLLB model loaded (~600MB)

Test 1: Short Spanish → English
ES: ¿Cuál es tu mejor precio?
EN: What is your best price?

Test 4: Simple greeting (Qwen-7B hallucination test)
ES: Hola, ¿cómo estás?
EN: Hello, how are you?

✓ All tests complete!
```

### Test Factory

```bash
cd /Users/matt/levi/mac/src
uv run --extra mac python llm/translation_factory.py
```

### Test Full Translation Service

```bash
cd /Users/matt/levi/mac/src
TRANSLATION_PROVIDER=nllb uv run --extra mac python translation_service.py
```

## Memory Comparison

| Model | Memory (GPU) | Quality | Speed |
|-------|-------------|---------|-------|
| Qwen-14B-4bit | ~10-12GB | Good | Fast |
| NLLB-600M | ~1-2GB | Excellent* | Very Fast |
| NLLB-1.3B | ~2-3GB | Excellent+ | Fast |
| NLLB-3.3B | ~5-6GB | Best | Medium |

*For translation tasks specifically

## Expected Memory Reduction

**Before (Qwen-14B):**
- Translation LLM: 10-12 GB
- VibeVoice TTS: 3-4 GB
- Whisper STT: 0.2-0.4 GB
- **Total: ~14-16 GB**

**After (NLLB-600M):**
- Translation: 1-2 GB ✅ (90% reduction!)
- VibeVoice TTS: 3-4 GB
- Whisper STT: 0.2-0.4 GB
- **Total: ~5-7 GB**

**Memory savings: ~10 GB** (from 20GB to 10GB total footprint)

## Troubleshooting

### Model Download Slow

First time running, NLLB will download from HuggingFace (~600MB).
Subsequent runs use cached model.

Cache location: `~/.cache/huggingface/hub/`

### Out of Memory

Try smaller model:
```bash
# Use 600M instead of 1.3B
NLLB_MODEL=facebook/nllb-200-distilled-600M
```

### Import Errors

Make sure dependencies installed:
```bash
uv sync --extra mac
```

## Reverting to Qwen

If you need to switch back:

```bash
TRANSLATION_PROVIDER=qwen uv run --extra mac python mac/src/main.py
```

Or remove from `.env`:
```bash
# Remove or comment out:
# TRANSLATION_PROVIDER=nllb
```

## Performance Notes

### Token Limit Handling

NLLB has a 512 token limit (~400 words). The client automatically:
1. Splits long texts into sentences
2. Batches sentences under token limit
3. Translates each batch
4. Joins results back together

For voice messages (typically 5-30 seconds), this is never an issue.

### Translation Quality

NLLB is trained specifically for translation and often outperforms general LLMs:
- No hallucinations (won't make up random text)
- Better handling of idioms and colloquialisms
- More accurate for low-resource language pairs
- Consistent output (no creativity/randomness)

## Next Steps

After verifying NLLB works:

1. **Stop the Mac backend** (if running with Qwen)
2. **Restart with NLLB** (will see immediate memory reduction)
3. **Test translation quality** (should be better for simple phrases)
4. **Monitor memory** (should see ~10GB reduction)

## Sources

- [NLLB-200 on Hugging Face](https://huggingface.co/facebook/nllb-200-distilled-600M)
- [Meta AI NLLB Blog Post](https://ai.meta.com/blog/nllb-200-high-quality-machine-translation/)
