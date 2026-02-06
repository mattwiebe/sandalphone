import assert from "node:assert/strict";
import test from "node:test";
import type { IncomingMessage } from "node:http";
import {
  computeTwilioSignature,
  hasValidAsteriskSecret,
  hasValidTwilioSignature,
} from "../server/auth.js";

function makeReq(opts: {
  secretHeader?: string;
  twilioSignature?: string;
  url?: string;
  host?: string;
} = {}): IncomingMessage {
  const headers: Record<string, string> = {};
  if (opts.secretHeader) headers["x-asterisk-secret"] = opts.secretHeader;
  if (opts.twilioSignature) headers["x-twilio-signature"] = opts.twilioSignature;
  if (opts.host) headers.host = opts.host;
  return {
    headers,
    url: opts.url ?? "/twilio/voice",
  } as IncomingMessage;
}

test("hasValidAsteriskSecret allows when no secret configured", () => {
  assert.equal(hasValidAsteriskSecret(makeReq(), undefined), true);
});

test("hasValidAsteriskSecret rejects missing or wrong header", () => {
  assert.equal(hasValidAsteriskSecret(makeReq(), "topsecret"), false);
  assert.equal(hasValidAsteriskSecret(makeReq({ secretHeader: "wrong" }), "topsecret"), false);
});

test("hasValidAsteriskSecret accepts matching header", () => {
  assert.equal(hasValidAsteriskSecret(makeReq({ secretHeader: "topsecret" }), "topsecret"), true);
});

test("hasValidTwilioSignature allows when auth token not configured", () => {
  assert.equal(hasValidTwilioSignature(makeReq(), { CallSid: "CA123" }, undefined), true);
});

test("hasValidTwilioSignature validates expected signature", () => {
  const formBody = { CallSid: "CA123", From: "+1555", To: "+1800" };
  const url = "https://voice.example.com/twilio/voice";
  const authToken = "test-token";
  const signature = computeTwilioSignature(url, formBody, authToken);

  const req = makeReq({
    twilioSignature: signature,
    url: "/twilio/voice",
  });

  assert.equal(
    hasValidTwilioSignature(req, formBody, authToken, "https://voice.example.com"),
    true,
  );
});

test("hasValidTwilioSignature rejects invalid signature", () => {
  const formBody = { CallSid: "CA123" };
  const req = makeReq({
    twilioSignature: "bad-signature",
    url: "/twilio/voice",
  });

  assert.equal(
    hasValidTwilioSignature(req, formBody, "test-token", "https://voice.example.com"),
    false,
  );
});
