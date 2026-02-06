import type { TranslationProvider } from "../../domain/providers.js";
import type { TranscriptionChunk, TranslationChunk } from "../../domain/types.js";

export class StubGoogleTranslationProvider implements TranslationProvider {
  public readonly name = "google-translate-stub";

  public async translate(chunk: TranscriptionChunk): Promise<TranslationChunk | null> {
    if (!chunk.text.trim()) return null;

    return {
      sessionId: chunk.sessionId,
      text: chunk.text,
      sourceLanguage: chunk.language,
      targetLanguage: chunk.language === "es" ? "en" : "es",
      timestampMs: Date.now(),
    };
  }
}

export type GoogleTranslateOptions = {
  readonly apiKey: string;
  readonly endpoint?: string;
};

export class GoogleTranslationProvider implements TranslationProvider {
  public readonly name = "google-translate-v2";

  public constructor(private readonly opts: GoogleTranslateOptions) {}

  public async translate(chunk: TranscriptionChunk): Promise<TranslationChunk | null> {
    if (!chunk.text.trim()) return null;

    const sourceLanguage = chunk.language;
    const targetLanguage = chunk.language === "es" ? "en" : "es";
    const endpoint =
      this.opts.endpoint ??
      `https://translation.googleapis.com/language/translate/v2?key=${encodeURIComponent(this.opts.apiKey)}`;

    let translated: string | undefined;
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          q: chunk.text,
          source: sourceLanguage,
          target: targetLanguage,
          format: "text",
        }),
      });

      if (!response.ok) return null;
      const data = (await response.json()) as {
        data?: { translations?: Array<{ translatedText?: string }> };
      };
      translated = data.data?.translations?.[0]?.translatedText;
    } catch {
      return null;
    }
    if (!translated) return null;

    return {
      sessionId: chunk.sessionId,
      text: translated,
      sourceLanguage,
      targetLanguage,
      timestampMs: Date.now(),
    };
  }
}
