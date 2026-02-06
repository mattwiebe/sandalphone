import assert from "node:assert/strict";
import test from "node:test";
import { parseTwilioIncoming } from "../ingress/twilio.js";
import { validateAsteriskInboundPayload, validateAsteriskMediaPayload } from "../ingress/asterisk.js";

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
