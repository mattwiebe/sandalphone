import assert from "node:assert/strict";
import test from "node:test";
import type { AppConfig } from "../config.js";
import { makeProviders } from "../providers/factory.js";
import { makeLogger } from "../server/logger.js";

function baseConfig(): AppConfig {
  return {
    port: 8080,
    destination phoneE164: "+15555550100",
    logLevel: "error",
    asteriskSharedSecret: undefined,
    pipelineMinFrameIntervalMs: 400,
    assemblyAiApiKey: undefined,
    assemblyAiRealtimeUrl: undefined,
    googleTranslateApiKey: undefined,
    awsRegion: "us-west-2",
    pollyVoiceEn: "Joanna",
    pollyVoiceEs: "Lupe",
    egressMaxQueuePerSession: 64,
  };
}

test("makeProviders falls back to stubs when keys are missing", () => {
  const providers = makeProviders(baseConfig(), makeLogger("error"));
  assert.equal(providers.stt.name, "assemblyai-stub");
  assert.equal(providers.translator.name, "google-translate-stub");
  assert.equal(providers.tts.name, "aws-polly-standard");
});

test("makeProviders enables cloud providers when keys are present", () => {
  const providers = makeProviders(
    {
      ...baseConfig(),
      assemblyAiApiKey: "assembly-key",
      googleTranslateApiKey: "google-key",
    },
    makeLogger("error"),
  );

  assert.equal(providers.stt.name, "assemblyai-realtime");
  assert.equal(providers.translator.name, "google-translate-v2");
  assert.equal(providers.tts.name, "aws-polly-standard");
});
