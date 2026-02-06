import type { StreamingSttProvider } from "../../domain/providers.js";
import type { AudioFrame, TranscriptionChunk } from "../../domain/types.js";
import WebSocket from "ws";

type PendingTranscription = {
  resolve: (chunk: TranscriptionChunk | null) => void;
  timer: NodeJS.Timeout;
};

type SessionSocket = {
  ws: WebSocket;
  queue: PendingTranscription[];
};

export class StubAssemblyAiProvider implements StreamingSttProvider {
  public readonly name = "assemblyai-stub";
  public constructor(private readonly text: string = "") {}

  public async transcribe(frame: AudioFrame): Promise<TranscriptionChunk | null> {
    return {
      sessionId: frame.sessionId,
      text: this.text,
      isFinal: true,
      language: "es",
      timestampMs: Date.now(),
    };
  }
}

export type AssemblyAiRealtimeOptions = {
  readonly apiKey: string;
  readonly url?: string;
  readonly timeoutMs?: number;
};

export class AssemblyAiRealtimeProvider implements StreamingSttProvider {
  public readonly name = "assemblyai-realtime";
  private readonly sessions = new Map<string, SessionSocket>();

  public constructor(private readonly opts: AssemblyAiRealtimeOptions) {}

  public async transcribe(frame: AudioFrame): Promise<TranscriptionChunk | null> {
    try {
      const socket = await this.getOrCreateSessionSocket(frame.sessionId, frame.encoding);

      const payload = JSON.stringify({
        audio_data: frame.payload.toString("base64"),
      });
      socket.ws.send(payload);

      return new Promise<TranscriptionChunk | null>((resolve) => {
        const timer = setTimeout(() => resolve(null), this.opts.timeoutMs ?? 240);
        socket.queue.push({ resolve, timer });
      });
    } catch {
      this.sessions.delete(frame.sessionId);
      return null;
    }
  }

  private async getOrCreateSessionSocket(
    sessionId: string,
    encoding: AudioFrame["encoding"],
  ): Promise<SessionSocket> {
    const existing = this.sessions.get(sessionId);
    if (existing && existing.ws.readyState === WebSocket.OPEN) {
      return existing;
    }

    const sampleRateHz = encoding === "mulaw" ? 8000 : 16000;
    const url =
      this.opts.url ??
      `wss://api.assemblyai.com/v2/realtime/ws?sample_rate=${sampleRateHz}&encoding=${encoding}`;

    const ws = new WebSocket(url, {
      headers: { Authorization: this.opts.apiKey },
    });

    const session: SessionSocket = { ws, queue: [] };
    this.sessions.set(sessionId, session);

    ws.on("message", (raw) => {
      const chunk = this.mapRealtimeEvent(raw, sessionId);
      if (!chunk) return;
      const next = session.queue.shift();
      if (!next) return;
      clearTimeout(next.timer);
      next.resolve(chunk);
    });

    ws.on("close", () => {
      this.flushQueue(session, null);
      this.sessions.delete(sessionId);
    });

    ws.on("error", () => {
      this.flushQueue(session, null);
      this.sessions.delete(sessionId);
    });

    await new Promise<void>((resolve, reject) => {
      ws.once("open", () => resolve());
      ws.once("error", (error) => reject(error));
    });

    return session;
  }

  private flushQueue(session: SessionSocket, chunk: TranscriptionChunk | null): void {
    while (session.queue.length > 0) {
      const next = session.queue.shift();
      if (!next) continue;
      clearTimeout(next.timer);
      next.resolve(chunk);
    }
  }

  private mapRealtimeEvent(raw: WebSocket.RawData, sessionId: string): TranscriptionChunk | null {
    const text = typeof raw === "string" ? raw : raw.toString("utf8");
    let parsed: {
      text?: string;
      message_type?: string;
      confidence?: number;
      speech_final?: boolean;
    };
    try {
      parsed = JSON.parse(text) as typeof parsed;
    } catch {
      return null;
    }

    if (!parsed.text?.trim()) return null;
    return {
      sessionId,
      text: parsed.text,
      isFinal: parsed.speech_final === true || parsed.message_type === "FinalTranscript",
      language: "es",
      timestampMs: Date.now(),
    };
  }
}
