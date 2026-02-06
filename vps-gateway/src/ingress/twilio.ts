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

export function buildTwimlForBridge(destinationPhoneE164: string): string {
  // v1 default: immediately dial destination phone leg.
  return [
    "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
    "<Response>",
    `  <Dial>${destinationPhoneE164}</Dial>`,
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
