export type IngressSource = "voipms" | "twilio";

export type SessionMode = "private_translation" | "passthrough";

export type LanguageCode = "en" | "es";

export type SessionState = "pending" | "active" | "ended" | "failed";

export interface AudioFrame {
  readonly sessionId: string;
  readonly source: IngressSource;
  readonly sampleRateHz: number;
  readonly encoding: "pcm_s16le" | "mulaw";
  readonly timestampMs: number;
  readonly payload: Buffer;
}

export interface TranscriptionChunk {
  readonly sessionId: string;
  readonly text: string;
  readonly isFinal: boolean;
  readonly language: LanguageCode;
  readonly timestampMs: number;
}

export interface TranslationChunk {
  readonly sessionId: string;
  readonly text: string;
  readonly sourceLanguage: LanguageCode;
  readonly targetLanguage: LanguageCode;
  readonly timestampMs: number;
}

export interface TtsChunk {
  readonly sessionId: string;
  readonly encoding: "pcm_s16le" | "mulaw";
  readonly sampleRateHz: number;
  readonly payload: Buffer;
  readonly timestampMs: number;
}

export interface CallSession {
  readonly id: string;
  readonly source: IngressSource;
  readonly inboundCaller: string;
  readonly startedAtMs: number;
  readonly targetPhoneE164: string;
  mode: SessionMode;
  sourceLanguage: LanguageCode;
  targetLanguage: LanguageCode;
  state: SessionState;
}

export interface IncomingCallEvent {
  readonly source: IngressSource;
  readonly externalCallId: string;
  readonly from: string;
  readonly to: string;
  readonly receivedAtMs: number;
}

export interface SessionMetrics {
  readonly sessionId: string;
  readonly sttLatencyMs?: number;
  readonly translationLatencyMs?: number;
  readonly ttsLatencyMs?: number;
  readonly pipelineLatencyMs?: number;
}

export interface SessionControlUpdate {
  readonly mode?: SessionMode;
  readonly sourceLanguage?: LanguageCode;
  readonly targetLanguage?: LanguageCode;
}

export interface SessionEvent {
  readonly type:
    | "session.started"
    | "session.ended"
    | "session.control.updated"
    | "session.transcript"
    | "session.translation";
  readonly sessionId: string;
  readonly atMs: number;
  readonly payload: Record<string, unknown>;
}
