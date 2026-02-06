import type { TtsProvider } from "../../domain/providers.js";
import type { TranslationChunk, TtsChunk } from "../../domain/types.js";

export class PollyStandardProvider implements TtsProvider {
  public readonly name = "aws-polly-standard";

  public async synthesize(chunk: TranslationChunk): Promise<TtsChunk | null> {
    if (!chunk.text.trim()) return null;

    // Stub for scaffold: replace with AWS Polly synthesis call and format conversion.
    return {
      sessionId: chunk.sessionId,
      encoding: "pcm_s16le",
      sampleRateHz: 16000,
      payload: Buffer.alloc(0),
      timestampMs: Date.now(),
    };
  }
}
