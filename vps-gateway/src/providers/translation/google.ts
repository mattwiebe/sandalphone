import type { TranslationProvider } from "../../domain/providers.js";
import type { TranscriptionChunk, TranslationChunk } from "../../domain/types.js";

export class GoogleTranslationProvider implements TranslationProvider {
  public readonly name = "google-translate";

  public async translate(chunk: TranscriptionChunk): Promise<TranslationChunk | null> {
    if (!chunk.text.trim()) return null;

    // Stub for scaffold: replace with Cloud Translation API client call.
    return {
      sessionId: chunk.sessionId,
      text: chunk.text,
      sourceLanguage: chunk.language,
      targetLanguage: chunk.language === "es" ? "en" : "es",
      timestampMs: Date.now(),
    };
  }
}
