# Known Issues & Future Improvements

## Current Issues

### 1. Translation Quality (Qwen 7B Hallucinations)

**Problem**: The Qwen2.5-7B-Instruct model occasionally hallucinates or produces incorrect translations, especially for simple greetings.

**Examples**:
- Input: "Hola, ¿cómo estás?"
- Expected: "Hello, how are you?"
- Sometimes gets: Random unrelated sentences

**Why**: The 7B model, even with 4-bit quantization, struggles with consistent translation behavior despite various prompting strategies tried:
- ChatML format with system instructions
- Simple prompts
- Few-shot examples

**Solutions to Try**:

1. **Use a larger model** (recommended):
   - Qwen2.5-14B or Qwen2.5-32B
   - Better translation quality but slower
   - Your M4 Max can handle it

2. **Use a specialized translation model**:
   - Try: `mlx-community/Qwen-MT-14B-4bit`
   - Qwen-MT is specifically fine-tuned for translation

3. **Add temperature/sampling controls**:
   ```python
   response = generate(
       model, tokenizer, prompt,
       max_tokens=50,
       top_p=0.9,      # Nucleus sampling
       repetition_penalty=1.1
   )
   ```

4. **Fall back to cloud API**:
   - Google Translate API: $20/month for 1M characters
   - DeepL API: Better quality, similar pricing
   - Use only when local translation seems wrong

**Workaround for Now**:
- The model works better with longer, more complex sentences
- Simple greetings are more prone to hallucination
- Consider the translation as "best effort" for Phase 2 testing

---

## Future Improvements

### Phase 3: Better Models

1. **Download Qwen2.5-14B** instead of 7B
   ```bash
   huggingface-cli download mlx-community/Qwen2.5-14B-Instruct-4bit
   ```

2. **Try Qwen-MT** (specialized for translation)
   ```bash
   huggingface-cli download mlx-community/Qwen-MT-14B-4bit
   ```

### Phase 3: Implement Real Qwen3-TTS

Currently using macOS `say` as placeholder. Need to:
1. Implement proper Qwen3-TTS inference
2. Use the downloaded 0.6B model at `mac/models/qwen3-tts-0.6b`
3. Expected latency: ~100ms (much better than current ~200ms)

### Phase 3: Add Voice Activity Detection (VAD)

- Filter out background noise
- Improve transcription quality
- Reduce false positives from ambient sounds

### Phase 4: Context Management

- Remember previous messages in conversation
- Better handling of multi-turn dialogues
- Store conversation history in SQLite

### Phase 4: Streaming TTS

- Start playing audio before full generation
- Perceived latency improvement
- More "natural" feeling conversation

---

## Performance Targets

**Current** (Phase 2):
- Latency: 2-4s
- Translation accuracy: ~70-80% (7B model)

**Target** (Phase 3):
- Latency: <2s
- Translation accuracy: >90% (14B+ model)

**Ideal** (Phase 4):
- Latency: <1s with streaming
- Translation accuracy: >95%
- Context-aware translations

---

## Testing Recommendations

For now, test with:
- **Longer sentences** (work better than single words)
- **Common phrases** (model has seen more examples)
- **Clear speech** (helps Whisper STT)

Examples that should work well:
- "¿Dónde está el baño?" → "Where is the bathroom?"
- "¿Cuánto cuesta esto?" → "How much does this cost?"
- "Necesito ayuda" → "I need help"

---

Last updated: 2026-01-28
