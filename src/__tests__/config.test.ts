import assert from "node:assert/strict";
import test from "node:test";
import { loadConfig } from "../config.js";

test("loadConfig uses OUTBOUND_TARGET_E164 when set", () => {
  const config = loadConfig({
    OUTBOUND_TARGET_E164: "+15550000001",
  });

  assert.equal(config.outboundTargetE164, "+15550000001");
});

test("loadConfig defaults OUTBOUND_TARGET_E164 when unset", () => {
  const config = loadConfig({
  });

  assert.equal(config.outboundTargetE164, "+15555550100");
  assert.equal(config.defaultSessionMode, "private_translation");
  assert.equal(config.twilioVoiceMode, "dial");
});

test("loadConfig rejects invalid OPENCLAW_BRIDGE_TIMEOUT_MS", () => {
  assert.throws(
    () =>
      loadConfig({
        OPENCLAW_BRIDGE_TIMEOUT_MS: "50",
      }),
    /Invalid OPENCLAW_BRIDGE_TIMEOUT_MS/,
  );
});

test("loadConfig accepts TWILIO_VOICE_MODE=stream", () => {
  const config = loadConfig({
    TWILIO_VOICE_MODE: "stream",
  });
  assert.equal(config.twilioVoiceMode, "stream");
});

test("loadConfig rejects invalid TWILIO_VOICE_MODE", () => {
  assert.throws(
    () =>
      loadConfig({
        TWILIO_VOICE_MODE: "bad",
      }),
    /Invalid TWILIO_VOICE_MODE/,
  );
});

test("loadConfig accepts DEFAULT_SESSION_MODE=passthrough", () => {
  const config = loadConfig({
    DEFAULT_SESSION_MODE: "passthrough",
  });
  assert.equal(config.defaultSessionMode, "passthrough");
});

test("loadConfig rejects invalid DEFAULT_SESSION_MODE", () => {
  assert.throws(
    () =>
      loadConfig({
        DEFAULT_SESSION_MODE: "bad",
      }),
    /Invalid DEFAULT_SESSION_MODE/,
  );
});
