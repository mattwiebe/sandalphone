import type { Logger } from "../server/logger.js";
import type { StreamingSttProvider, TranslationProvider, TtsProvider } from "../domain/providers.js";
import type { AudioFrame, CallSession, IncomingCallEvent, SessionMetrics } from "../domain/types.js";
import { SessionStore } from "./session-store.js";

export type OrchestratorDeps = {
  readonly logger: Logger;
  readonly sessionStore: SessionStore;
  readonly stt: StreamingSttProvider;
  readonly translator: TranslationProvider;
  readonly tts: TtsProvider;
  readonly destination phoneE164: string;
  readonly minFrameIntervalMs?: number;
};

export class VoiceOrchestrator {
  private readonly metrics = new Map<string, SessionMetrics>();
  private readonly lastFrameAtMs = new Map<string, number>();

  public constructor(private readonly deps: OrchestratorDeps) {}

  public onIncomingCall(event: IncomingCallEvent): CallSession {
    const existing = this.deps.sessionStore.getByExternal(event.source, event.externalCallId);
    if (existing) {
      this.deps.logger.warn("duplicate incoming call ignored", {
        sessionId: existing.id,
        source: event.source,
        externalCallId: event.externalCallId,
      });
      return existing;
    }

    const session = this.deps.sessionStore.createFromIncoming(event, this.deps.destination phoneE164);
    this.deps.logger.info("incoming call accepted", {
      sessionId: session.id,
      source: event.source,
      from: event.from,
      to: event.to,
      ringTarget: session.targetPhoneE164,
    });
    this.deps.sessionStore.updateState(session.id, "active");
    return session;
  }

  public resolveSessionIdByExternal(source: string, externalCallId: string): string | undefined {
    return this.deps.sessionStore.getByExternal(source, externalCallId)?.id;
  }

  public async onAudioFrame(frame: AudioFrame): Promise<void> {
    if (!this.deps.sessionStore.get(frame.sessionId)) {
      this.deps.logger.warn("audio frame for unknown session", {
        sessionId: frame.sessionId,
        source: frame.source,
      });
      return;
    }

    const minFrameIntervalMs = this.deps.minFrameIntervalMs ?? 0;
    const previousFrameTs = this.lastFrameAtMs.get(frame.sessionId);
    if (
      previousFrameTs !== undefined &&
      frame.timestampMs - previousFrameTs < minFrameIntervalMs
    ) {
      return;
    }
    this.lastFrameAtMs.set(frame.sessionId, frame.timestampMs);

    const sttStart = Date.now();
    const transcript = await this.deps.stt.transcribe(frame);
    const sttLatencyMs = Date.now() - sttStart;

    if (!transcript || !transcript.text.trim()) {
      this.trackMetrics(frame.sessionId, { sessionId: frame.sessionId, sttLatencyMs });
      return;
    }

    const translateStart = Date.now();
    const translation = await this.deps.translator.translate(transcript);
    const translationLatencyMs = Date.now() - translateStart;

    if (!translation) {
      this.trackMetrics(frame.sessionId, {
        sessionId: frame.sessionId,
        sttLatencyMs,
        translationLatencyMs,
      });
      return;
    }

    const ttsStart = Date.now();
    await this.deps.tts.synthesize(translation);
    const ttsLatencyMs = Date.now() - ttsStart;

    const pipelineLatencyMs = sttLatencyMs + translationLatencyMs + ttsLatencyMs;
    this.trackMetrics(frame.sessionId, {
      sessionId: frame.sessionId,
      sttLatencyMs,
      translationLatencyMs,
      ttsLatencyMs,
      pipelineLatencyMs,
    });

    this.deps.logger.debug("translated chunk", {
      sessionId: frame.sessionId,
      transcript: transcript.text,
      translated: translation.text,
      pipelineLatencyMs,
    });
  }

  public endSession(sessionId: string): void {
    const session = this.deps.sessionStore.updateState(sessionId, "ended");
    if (!session) return;

    this.deps.logger.info("session ended", {
      sessionId,
      source: session.source,
      metrics: this.metrics.get(sessionId),
    });
  }

  public listSessions(): CallSession[] {
    return this.deps.sessionStore.all();
  }

  private trackMetrics(sessionId: string, delta: SessionMetrics): void {
    const previous = this.metrics.get(sessionId) ?? { sessionId };
    this.metrics.set(sessionId, {
      sessionId,
      sttLatencyMs: delta.sttLatencyMs ?? previous.sttLatencyMs,
      translationLatencyMs: delta.translationLatencyMs ?? previous.translationLatencyMs,
      ttsLatencyMs: delta.ttsLatencyMs ?? previous.ttsLatencyMs,
      pipelineLatencyMs: delta.pipelineLatencyMs ?? previous.pipelineLatencyMs,
    });
  }
}
