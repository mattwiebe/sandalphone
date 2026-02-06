import type { Logger } from "../server/logger.js";
import type { StreamingSttProvider, TranslationProvider, TtsProvider } from "../domain/providers.js";
import type {
  AudioFrame,
  CallSession,
  IncomingCallEvent,
  SessionControlUpdate,
  SessionEvent,
  SessionMetrics,
  TtsChunk,
} from "../domain/types.js";
import { SessionStore } from "./session-store.js";

export type OrchestratorDeps = {
  readonly logger: Logger;
  readonly sessionStore: SessionStore;
  readonly stt: StreamingSttProvider;
  readonly translator: TranslationProvider;
  readonly tts: TtsProvider;
  readonly outboundTargetE164: string;
  readonly minFrameIntervalMs?: number;
  readonly onTtsChunk?: (chunk: TtsChunk) => Promise<void> | void;
  readonly onSessionEvent?: (event: SessionEvent) => Promise<void> | void;
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

    const session = this.deps.sessionStore.createFromIncoming(event, this.deps.outboundTargetE164);
    this.deps.logger.info("incoming call accepted", {
      sessionId: session.id,
      source: event.source,
      from: event.from,
      to: event.to,
      ringTarget: session.targetPhoneE164,
    });
    this.deps.sessionStore.updateState(session.id, "active");
    void this.emitEvent({
      type: "session.started",
      sessionId: session.id,
      atMs: Date.now(),
      payload: {
        source: session.source,
        inboundCaller: session.inboundCaller,
        targetPhoneE164: session.targetPhoneE164,
        mode: session.mode,
        sourceLanguage: session.sourceLanguage,
        targetLanguage: session.targetLanguage,
      },
    });
    return session;
  }

  public resolveSessionIdByExternal(source: string, externalCallId: string): string | undefined {
    return this.deps.sessionStore.getByExternal(source, externalCallId)?.id;
  }

  public getSession(sessionId: string): CallSession | undefined {
    return this.deps.sessionStore.get(sessionId);
  }

  public getMetrics(sessionId: string): SessionMetrics | undefined {
    return this.metrics.get(sessionId);
  }

  public updateSessionControl(
    sessionId: string,
    patch: SessionControlUpdate,
  ): CallSession | undefined {
    const session = this.deps.sessionStore.updateControl(sessionId, patch);
    if (!session) return undefined;

    this.deps.logger.info("session control updated", {
      sessionId,
      mode: session.mode,
      sourceLanguage: session.sourceLanguage,
      targetLanguage: session.targetLanguage,
    });
    void this.emitEvent({
      type: "session.control.updated",
      sessionId,
      atMs: Date.now(),
      payload: {
        mode: session.mode,
        sourceLanguage: session.sourceLanguage,
        targetLanguage: session.targetLanguage,
      },
    });
    return session;
  }

  public async onAudioFrame(frame: AudioFrame): Promise<void> {
    const session = this.deps.sessionStore.get(frame.sessionId);
    if (!session) {
      this.deps.logger.warn("audio frame for unknown session", {
        sessionId: frame.sessionId,
        source: frame.source,
      });
      return;
    }
    if (session.mode === "passthrough") {
      this.incrementMetric(frame.sessionId, "passthroughFrames");
      return;
    }

    const minFrameIntervalMs = this.deps.minFrameIntervalMs ?? 0;
    const previousFrameTs = this.lastFrameAtMs.get(frame.sessionId);
    if (
      previousFrameTs !== undefined &&
      frame.timestampMs - previousFrameTs < minFrameIntervalMs
    ) {
      this.markFrameDropped(frame.sessionId);
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
    void this.emitEvent({
      type: "session.transcript",
      sessionId: frame.sessionId,
      atMs: transcript.timestampMs,
      payload: {
        text: transcript.text,
        isFinal: transcript.isFinal,
        language: transcript.language,
      },
    });

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
    void this.emitEvent({
      type: "session.translation",
      sessionId: frame.sessionId,
      atMs: translation.timestampMs,
      payload: {
        text: translation.text,
        sourceLanguage: translation.sourceLanguage,
        targetLanguage: translation.targetLanguage,
      },
    });

    const ttsStart = Date.now();
    const tts = await this.deps.tts.synthesize(translation);
    const ttsLatencyMs = Date.now() - ttsStart;

    if (tts && this.deps.onTtsChunk) {
      await this.deps.onTtsChunk(tts);
    }

    const pipelineLatencyMs = sttLatencyMs + translationLatencyMs + ttsLatencyMs;
    this.trackMetrics(frame.sessionId, {
      sessionId: frame.sessionId,
      sttLatencyMs,
      translationLatencyMs,
      ttsLatencyMs,
      pipelineLatencyMs,
    });
    this.incrementMetric(frame.sessionId, "translatedChunks");

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
    void this.emitEvent({
      type: "session.ended",
      sessionId,
      atMs: Date.now(),
      payload: {
        source: session.source,
        metrics: this.metrics.get(sessionId) ?? {},
      },
    });
  }

  public listSessions(): CallSession[] {
    return this.deps.sessionStore.all();
  }

  public listMetrics(): SessionMetrics[] {
    return [...this.metrics.values()];
  }

  public reportEgressStats(
    sessionId: string,
    stats: { queueSize: number; droppedOldest: boolean },
  ): void {
    const current = this.metrics.get(sessionId) ?? { sessionId };
    const egressQueuePeak = Math.max(current.egressQueuePeak ?? 0, stats.queueSize);
    const egressDropCount = (current.egressDropCount ?? 0) + (stats.droppedOldest ? 1 : 0);
    this.metrics.set(sessionId, {
      ...current,
      egressQueuePeak,
      egressDropCount,
    });
  }

  public markFrameDropped(sessionId: string): void {
    this.incrementMetric(sessionId, "droppedFrames");
  }

  private trackMetrics(sessionId: string, delta: SessionMetrics): void {
    const previous = this.metrics.get(sessionId) ?? { sessionId };
    this.metrics.set(sessionId, {
      ...previous,
      sessionId,
      sttLatencyMs: delta.sttLatencyMs ?? previous.sttLatencyMs,
      translationLatencyMs: delta.translationLatencyMs ?? previous.translationLatencyMs,
      ttsLatencyMs: delta.ttsLatencyMs ?? previous.ttsLatencyMs,
      pipelineLatencyMs: delta.pipelineLatencyMs ?? previous.pipelineLatencyMs,
    });
  }

  private incrementMetric(
    sessionId: string,
    field:
      | "droppedFrames"
      | "passthroughFrames"
      | "translatedChunks"
      | "egressDropCount",
  ): void {
    const current = this.metrics.get(sessionId) ?? { sessionId };
    const next = (current[field] ?? 0) + 1;
    this.metrics.set(sessionId, {
      ...current,
      [field]: next,
    });
  }

  private async emitEvent(event: SessionEvent): Promise<void> {
    if (!this.deps.onSessionEvent) return;
    try {
      await this.deps.onSessionEvent(event);
    } catch (error) {
      this.deps.logger.warn("session event hook failed", {
        type: event.type,
        sessionId: event.sessionId,
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }
}
