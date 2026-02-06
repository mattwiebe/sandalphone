import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import type { AudioFrame, IncomingCallEvent } from "../domain/types.js";

export type AsteriskInboundPayload = {
  callId: string;
  from: string;
  to: string;
};

export type AsteriskMediaPayload = {
  callId: string;
  sampleRateHz: number;
  encoding: "pcm_s16le" | "mulaw";
  payloadBase64: string;
  timestampMs?: number;
};

export function validateAsteriskInboundPayload(payload: unknown): payload is AsteriskInboundPayload {
  if (!payload || typeof payload !== "object") return false;
  const p = payload as Record<string, unknown>;
  return typeof p.callId === "string" && typeof p.from === "string" && typeof p.to === "string";
}

export function validateAsteriskMediaPayload(payload: unknown): payload is AsteriskMediaPayload {
  if (!payload || typeof payload !== "object") return false;
  const p = payload as Record<string, unknown>;
  const encoding = p.encoding;
  return (
    typeof p.callId === "string" &&
    typeof p.sampleRateHz === "number" &&
    (encoding === "pcm_s16le" || encoding === "mulaw") &&
    typeof p.payloadBase64 === "string"
  );
}

export function parseAsteriskIncoming(payload: AsteriskInboundPayload): IncomingCallEvent {
  return {
    source: "voipms",
    externalCallId: payload.callId,
    from: payload.from,
    to: payload.to,
    receivedAtMs: Date.now(),
  };
}

export function handleAsteriskInbound(
  orchestrator: VoiceOrchestrator,
  payload: AsteriskInboundPayload,
): { sessionId: string; dialTarget: string } {
  const session = orchestrator.onIncomingCall(parseAsteriskIncoming(payload));
  return {
    sessionId: session.id,
    dialTarget: session.targetPhoneE164,
  };
}

export function mapAsteriskMediaToFrame(
  orchestrator: VoiceOrchestrator,
  payload: AsteriskMediaPayload,
): AudioFrame | null {
  const sessionId = orchestrator.resolveSessionIdByExternal("voipms", payload.callId);
  if (!sessionId) return null;

  return {
    sessionId,
    source: "voipms",
    sampleRateHz: payload.sampleRateHz,
    encoding: payload.encoding,
    timestampMs: payload.timestampMs ?? Date.now(),
    payload: Buffer.from(payload.payloadBase64, "base64"),
  };
}
