import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import type { IncomingCallEvent } from "../domain/types.js";

export function parseTwilioIncoming(body: Record<string, string>): IncomingCallEvent {
  return {
    source: "twilio",
    externalCallId: body.CallSid ?? "unknown",
    from: body.From ?? "unknown",
    to: body.To ?? "unknown",
    receivedAtMs: Date.now(),
  };
}

export function buildTwimlForBridge(outboundTargetE164: string): string {
  // v1 default: immediately dial destination phone leg.
  return [
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
    "<Response>",
    `  <Dial>${outboundTargetE164}</Dial>`,
    "</Response>",
  ].join("\n");
}

export function buildTwimlSayAndHangup(lines: Array<{ text: string; language: "en-US" | "es-MX" }>): string {
  const sayLines = lines
    .filter((line) => line.text.trim().length > 0)
    .map((line) => `  <Say language="${line.language}">${escapeXml(line.text)}</Say>`);
  return [
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
    "<Response>",
    ...sayLines,
    "  <Hangup/>",
    "</Response>",
  ].join("\n");
}

export function handleTwilioInbound(
  orchestrator: VoiceOrchestrator,
  body: Record<string, string>,
): { twiml: string; sessionId: string } {
  const event = parseTwilioIncoming(body);
  const session = orchestrator.onIncomingCall(event);
  return {
    twiml: buildTwimlForBridge(session.targetPhoneE164),
    sessionId: session.id,
  };
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&apos;");
}
