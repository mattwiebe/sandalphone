import assert from "node:assert/strict";
import test from "node:test";
import { parseTwilioIncoming } from "../ingress/twilio.js";
import {
  resolveAsteriskEndSessionId,
  validateAsteriskEndPayload,
  validateAsteriskInboundPayload,
  validateAsteriskMediaPayload,
} from "../ingress/asterisk.js";
import { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { SessionStore } from "../pipeline/session-store.js";
import { makeLogger } from "../server/logger.js";

function makeOrchestrator() {
  return new VoiceOrchestrator({
    logger: makeLogger("error"),
    sessionStore: new SessionStore(),
    stt: { name: "noop", transcribe: async () => null },
    translator: { name: "noop", translate: async () => null },
    tts: { name: "noop", synthesize: async () => null },
    outboundTargetE164: "+15555550100",
  });
}

test("parseTwilioIncoming maps required fields", () => {
  const evt = parseTwilioIncoming({
    CallSid: "CA123",
    From: "+15551234567",
    To: "+18005550199",
  });

  assert.equal(evt.source, "twilio");
  assert.equal(evt.externalCallId, "CA123");
  assert.equal(evt.from, "+15551234567");
  assert.equal(evt.to, "+18005550199");
  assert.ok(evt.receivedAtMs > 0);
});

test("validateAsteriskInboundPayload accepts valid payload", () => {
  const ok = validateAsteriskInboundPayload({
    callId: "sip-1",
    from: "+15550000001",
    to: "+18005550199",
  });
  assert.equal(ok, true);
});

test("validateAsteriskInboundPayload rejects invalid payload", () => {
  const bad = validateAsteriskInboundPayload({
    callId: "sip-1",
    from: "+15550000001",
  });
  assert.equal(bad, false);
});

test("validateAsteriskMediaPayload accepts valid payload", () => {
  const ok = validateAsteriskMediaPayload({
    callId: "sip-1",
    sampleRateHz: 8000,
    encoding: "mulaw",
    payloadBase64: Buffer.from([0x01, 0x02]).toString("base64"),
  });
  assert.equal(ok, true);
});

test("validateAsteriskEndPayload accepts callId or sessionId", () => {
  assert.equal(validateAsteriskEndPayload({ callId: "sip-1" }), true);
  assert.equal(validateAsteriskEndPayload({ sessionId: "session-1" }), true);
  assert.equal(validateAsteriskEndPayload({ source: "voipms" }), false);
});

test("resolveAsteriskEndSessionId resolves by callId mapping", () => {
  const orchestrator = makeOrchestrator();
  const session = orchestrator.onIncomingCall({
    source: "voipms",
    externalCallId: "sip-2",
    from: "+15550000001",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  });

  const resolved = resolveAsteriskEndSessionId(orchestrator, { callId: "sip-2" });
  assert.equal(resolved, session.id);
});
