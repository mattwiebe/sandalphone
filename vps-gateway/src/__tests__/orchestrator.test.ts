import assert from "node:assert/strict";
import test from "node:test";
import { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { SessionStore } from "../pipeline/session-store.js";
import { makeLogger } from "../server/logger.js";
import type { AudioFrame, IncomingCallEvent } from "../domain/types.js";

class StubStt {
  public readonly name = "stub-stt";
  public async transcribe() {
    return {
      sessionId: "ignored",
      text: "hola",
      isFinal: true,
      language: "es" as const,
      timestampMs: Date.now(),
    };
  }
}

class StubTranslator {
  public readonly name = "stub-translator";
  public async translate() {
    return {
      sessionId: "ignored",
      text: "hello",
      sourceLanguage: "es" as const,
      targetLanguage: "en" as const,
      timestampMs: Date.now(),
    };
  }
}

class StubTts {
  public readonly name = "stub-tts";
  public async synthesize() {
    return {
      sessionId: "ignored",
      encoding: "pcm_s16le" as const,
      sampleRateHz: 16000,
      payload: Buffer.alloc(0),
      timestampMs: Date.now(),
    };
  }
}

function makeOrchestrator() {
  return new VoiceOrchestrator({
    logger: makeLogger("error"),
    sessionStore: new SessionStore(),
    stt: new StubStt(),
    translator: new StubTranslator(),
    tts: new StubTts(),
    destination phoneE164: "+15555550100",
  });
}

test("onIncomingCall de-duplicates external call IDs", () => {
  const orchestrator = makeOrchestrator();
  const call: IncomingCallEvent = {
    source: "twilio",
    externalCallId: "CA123",
    from: "+15551234567",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  };

  const s1 = orchestrator.onIncomingCall(call);
  const s2 = orchestrator.onIncomingCall(call);

  assert.equal(s1.id, s2.id);
  assert.equal(orchestrator.listSessions().length, 1);
});

test("resolveSessionIdByExternal returns mapped session", () => {
  const orchestrator = makeOrchestrator();
  const call: IncomingCallEvent = {
    source: "voipms",
    externalCallId: "sip-1",
    from: "+15550000001",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  };

  const session = orchestrator.onIncomingCall(call);
  const resolved = orchestrator.resolveSessionIdByExternal("voipms", "sip-1");
  assert.equal(resolved, session.id);
});

test("onAudioFrame processes pipeline without throwing", async () => {
  const orchestrator = makeOrchestrator();
  const call: IncomingCallEvent = {
    source: "twilio",
    externalCallId: "CA555",
    from: "+15550000005",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  };
  const session = orchestrator.onIncomingCall(call);

  const frame: AudioFrame = {
    sessionId: session.id,
    source: "twilio",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: Date.now(),
    payload: Buffer.from([0x00, 0x7f, 0x80]),
  };

  await orchestrator.onAudioFrame(frame);
  assert.equal(orchestrator.listSessions()[0]?.state, "active");
});
