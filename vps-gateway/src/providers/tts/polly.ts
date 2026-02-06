import type { TtsProvider } from "../../domain/providers.js";
import type { TranslationChunk, TtsChunk } from "../../domain/types.js";
import { PollyClient, SynthesizeSpeechCommand, type VoiceId } from "@aws-sdk/client-polly";

async function toBuffer(audioStream: unknown): Promise<Buffer> {
  if (!audioStream || typeof audioStream !== "object") {
    return Buffer.alloc(0);
  }

  if ("transformToByteArray" in audioStream && typeof audioStream.transformToByteArray === "function") {
    const bytes = await audioStream.transformToByteArray();
    return Buffer.from(bytes);
  }

  if (Symbol.asyncIterator in audioStream) {
    const chunks: Buffer[] = [];
    for await (const chunk of audioStream as AsyncIterable<Uint8Array>) {
      chunks.push(Buffer.from(chunk));
    }
    return Buffer.concat(chunks);
  }

  return Buffer.alloc(0);
}

export class StubPollyProvider implements TtsProvider {
  public readonly name = "aws-polly-stub";

  public async synthesize(chunk: TranslationChunk): Promise<TtsChunk | null> {
    if (!chunk.text.trim()) return null;

    return {
      sessionId: chunk.sessionId,
      encoding: "pcm_s16le",
      sampleRateHz: 16000,
      payload: Buffer.from([0x00, 0x00, 0x00, 0x00]),
      timestampMs: Date.now(),
    };
  }
}

export type PollyOptions = {
  readonly region: string;
  readonly voiceEn: string;
  readonly voiceEs: string;
};

export class PollyStandardProvider implements TtsProvider {
  public readonly name = "aws-polly-standard";
  private readonly client: PollyClient;

  public constructor(private readonly opts: PollyOptions) {
    this.client = new PollyClient({ region: opts.region });
  }

  public async synthesize(chunk: TranslationChunk): Promise<TtsChunk | null> {
    if (!chunk.text.trim()) return null;

    const voiceId = chunk.targetLanguage === "es" ? this.opts.voiceEs : this.opts.voiceEn;
    let payload: Buffer;
    try {
      const command = new SynthesizeSpeechCommand({
        Engine: "standard",
        OutputFormat: "pcm",
        SampleRate: "16000",
        Text: chunk.text,
        TextType: "text",
        VoiceId: voiceId as VoiceId,
      });
      const out = await this.client.send(command);
      payload = await toBuffer(out.AudioStream);
    } catch {
      return null;
    }

    if (payload.length === 0) return null;

    return {
      sessionId: chunk.sessionId,
      encoding: "pcm_s16le",
      sampleRateHz: 16000,
      payload,
      timestampMs: Date.now(),
    };
  }
}
