import type { StreamingSttProvider } from "../../domain/providers.js";
import type { AudioFrame, LanguageCode, TranscriptionChunk } from "../../domain/types.js";

type GoogleSttOptions = {
  readonly apiKey: string;
  readonly chunkMs?: number;
  readonly model?: string;
  readonly endpoint?: string;
};

type SessionState = {
  buffers: Buffer[];
  totalBytes: number;
  sampleRateHz: number;
  encoding: AudioFrame["encoding"];
  sourceLanguage: LanguageCode;
};

type GoogleSttResponse = {
  results?: Array<{
    alternatives?: Array<{ transcript?: string }>;
    isFinal?: boolean;
  }>;
};

export class StubGoogleSttProvider implements StreamingSttProvider {
  public readonly name = "google-stt-stub";
  public constructor(private readonly text: string = "") {}

  public async transcribe(
    frame: AudioFrame,
    sourceLanguage: LanguageCode,
  ): Promise<TranscriptionChunk | null> {
    return {
      sessionId: frame.sessionId,
      text: this.text,
      isFinal: true,
      language: sourceLanguage,
      timestampMs: Date.now(),
    };
  }
}

export class GoogleSpeechProvider implements StreamingSttProvider {
  public readonly name = "google-stt";
  private readonly sessions = new Map<string, SessionState>();

  public constructor(private readonly opts: GoogleSttOptions) {}

  public async transcribe(
    frame: AudioFrame,
    sourceLanguage: LanguageCode,
  ): Promise<TranscriptionChunk | null> {
    if (frame.payload.length === 0) return null;

    const session = this.getSession(frame, sourceLanguage);
    session.buffers.push(frame.payload);
    session.totalBytes += frame.payload.length;

    const targetBytes = this.bytesForMs(
      session.sampleRateHz,
      session.encoding,
      this.opts.chunkMs ?? 800,
    );
    if (session.totalBytes < targetBytes) return null;

    const audio = Buffer.concat(session.buffers, session.totalBytes);
    session.buffers = [];
    session.totalBytes = 0;

    return this.recognize(frame.sessionId, audio, session);
  }

  private getSession(frame: AudioFrame, sourceLanguage: LanguageCode): SessionState {
    const existing = this.sessions.get(frame.sessionId);
    if (existing) {
      existing.sampleRateHz = frame.sampleRateHz;
      existing.encoding = frame.encoding;
      existing.sourceLanguage = sourceLanguage;
      return existing;
    }

    const session: SessionState = {
      buffers: [],
      totalBytes: 0,
      sampleRateHz: frame.sampleRateHz,
      encoding: frame.encoding,
      sourceLanguage,
    };
    this.sessions.set(frame.sessionId, session);
    return session;
  }

  private bytesForMs(sampleRateHz: number, encoding: AudioFrame["encoding"], ms: number): number {
    const bytesPerSample = encoding === "mulaw" ? 1 : 2;
    return Math.max(1, Math.round((sampleRateHz * bytesPerSample * ms) / 1000));
  }

  private async recognize(
    sessionId: string,
    audio: Buffer,
    session: SessionState,
  ): Promise<TranscriptionChunk | null> {
    const encoding = session.encoding === "mulaw" ? "MULAW" : "LINEAR16";
    const languageCode = session.sourceLanguage === "es" ? "es-US" : "en-US";
    const endpoint =
      this.opts.endpoint ??
      `https://speech.googleapis.com/v1/speech:recognize?key=${encodeURIComponent(this.opts.apiKey)}`;

    const payload = {
      config: {
        encoding,
        sampleRateHertz: session.sampleRateHz,
        languageCode,
        model: this.opts.model ?? "phone_call",
        enableAutomaticPunctuation: true,
      },
      audio: {
        content: audio.toString("base64"),
      },
    };

    let response: Response;
    try {
      response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
    } catch {
      return null;
    }

    if (!response.ok) return null;

    let body: GoogleSttResponse;
    try {
      body = (await response.json()) as GoogleSttResponse;
    } catch {
      return null;
    }

    const transcript = body.results?.[0]?.alternatives?.[0]?.transcript?.trim();
    if (!transcript) return null;

    return {
      sessionId,
      text: transcript,
      isFinal: true,
      language: session.sourceLanguage,
      timestampMs: Date.now(),
    };
  }
}
