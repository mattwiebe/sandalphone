import type { TtsProvider } from "../../domain/providers.js";
import type { TranslationChunk, TtsChunk } from "../../domain/types.js";

type GoogleTtsOptions = {
  readonly apiKey: string;
  readonly voiceEn: string;
  readonly voiceEs: string;
};

type GoogleTtsResponse = {
  audioContent?: string;
};

export class GoogleTtsProvider implements TtsProvider {
  public readonly name = "google-tts";

  public constructor(private readonly opts: GoogleTtsOptions) {}

  public async synthesize(chunk: TranslationChunk): Promise<TtsChunk | null> {
    if (!chunk.text.trim()) return null;

    const voiceName = chunk.targetLanguage === "es" ? this.opts.voiceEs : this.opts.voiceEn;
    const languageCode = voiceName.split("-").slice(0, 2).join("-");

    const payload = {
      input: { text: chunk.text },
      voice: { languageCode, name: voiceName },
      audioConfig: { audioEncoding: "LINEAR16", sampleRateHertz: 16000 },
    };

    let response: Response;
    try {
      response = await fetch(
        `https://texttospeech.googleapis.com/v1/text:synthesize?key=${encodeURIComponent(
          this.opts.apiKey,
        )}`,
        {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        },
      );
    } catch {
      return null;
    }

    if (!response.ok) return null;

    let body: GoogleTtsResponse;
    try {
      body = (await response.json()) as GoogleTtsResponse;
    } catch {
      return null;
    }

    if (!body.audioContent) return null;

    const audio = Buffer.from(body.audioContent, "base64");
    if (audio.length === 0) return null;

    return {
      sessionId: chunk.sessionId,
      encoding: "pcm_s16le",
      sampleRateHz: 16000,
      payload: audio,
      timestampMs: Date.now(),
    };
  }
}
