import assert from "node:assert/strict";
import test from "node:test";
import type { AppConfig } from "../config.js";
import { makeProviders } from "../providers/factory.js";
import { makeLogger } from "../server/logger.js";

function baseConfig(): AppConfig {
  return {
    port: 8080,
    outboundTargetE164: "+15555550100",
    logLevel: "error",
    asteriskSharedSecret: undefined,
    pipelineMinFrameIntervalMs: 400,
    googleCloudApiKey: undefined,
    googleTtsVoiceEn: "en-US-Standard-C",
    googleTtsVoiceEs: "es-US-Standard-A",
    egressMaxQueuePerSession: 64,
    stubSttText: undefined,
    openClawBridgeTimeoutMs: 1200,
  };
}

test("makeProviders falls back to stubs when keys are missing", () => {
  const providers = makeProviders(baseConfig(), makeLogger("error"));
  assert.equal(providers.stt.name, "google-stt-stub");
  assert.equal(providers.translator.name, "google-translate-stub");
  assert.equal(providers.tts.name, "google-tts-stub");
});

test("makeProviders enables cloud providers when keys are present", () => {
  const providers = makeProviders(
    {
      ...baseConfig(),
      googleCloudApiKey: "google-key",
    },
    makeLogger("error"),
  );

  assert.equal(providers.stt.name, "google-stt");
  assert.equal(providers.translator.name, "google-translate-v2");
  assert.equal(providers.tts.name, "google-tts");
});
