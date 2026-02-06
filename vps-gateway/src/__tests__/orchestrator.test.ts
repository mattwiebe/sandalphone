import assert from "node:assert/strict";
import test from "node:test";
import { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { SessionStore } from "../pipeline/session-store.js";
import { makeLogger } from "../server/logger.js";
import type { AudioFrame, IncomingCallEvent } from "../domain/types.js";

class StubStt {
  public readonly name = "stub-stt";
  public calls = 0;
  public async transcribe(input: { sessionId: string }) {
    this.calls += 1;
    return {
      sessionId: input.sessionId,
      text: "hola",
      isFinal: true,
      language: "es" as const,
      timestampMs: Date.now(),
    };
  }
}

class StubTranslator {
  public readonly name = "stub-translator";
  public async translate(input: { sessionId: string }) {
    return {
      sessionId: input.sessionId,
      text: "hello",
      sourceLanguage: "es" as const,
      targetLanguage: "en" as const,
      timestampMs: Date.now(),
    };
  }
}

class StubTts {
  public readonly name = "stub-tts";
  public async synthesize(input: { sessionId: string }) {
    return {
      sessionId: input.sessionId,
      encoding: "pcm_s16le" as const,
      sampleRateHz: 16000,
      payload: Buffer.from([0x01]),
      timestampMs: Date.now(),
    };
  }
}

function makeOrchestrator(minFrameIntervalMs = 0, onTtsChunk?: (sessionId: string) => void) {
  const stt = new StubStt();
  return {
    stt,
    orchestrator: new VoiceOrchestrator({
      logger: makeLogger("error"),
      sessionStore: new SessionStore(),
      stt,
      translator: new StubTranslator(),
      tts: new StubTts(),
      outboundTargetE164: "+15555550100",
      minFrameIntervalMs,
      onTtsChunk: (chunk) => onTtsChunk?.(chunk.sessionId),
    }),
  };
}

test("onIncomingCall de-duplicates external call IDs", () => {
  const { orchestrator } = makeOrchestrator();
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
  const { orchestrator } = makeOrchestrator();
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
  const { orchestrator } = makeOrchestrator();
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
  assert.equal(orchestrator.listMetrics().length, 1);
});

test("onAudioFrame throttles frames under min interval", async () => {
  const { orchestrator, stt } = makeOrchestrator(100);
  const call: IncomingCallEvent = {
    source: "twilio",
    externalCallId: "CA777",
    from: "+15550000007",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  };
  const session = orchestrator.onIncomingCall(call);
  const now = Date.now();

  await orchestrator.onAudioFrame({
    sessionId: session.id,
    source: "twilio",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: now,
    payload: Buffer.from([0x01]),
  });
  await orchestrator.onAudioFrame({
    sessionId: session.id,
    source: "twilio",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: now + 50,
    payload: Buffer.from([0x02]),
  });
  await orchestrator.onAudioFrame({
    sessionId: session.id,
    source: "twilio",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: now + 150,
    payload: Buffer.from([0x03]),
  });

  assert.equal(stt.calls, 2);
  const metrics = orchestrator.listMetrics()[0];
  assert.equal((metrics?.droppedFrames ?? 0) >= 1, true);
});

test("onAudioFrame emits synthesized chunk to egress callback", async () => {
  const seen: string[] = [];
  const { orchestrator } = makeOrchestrator(0, (sessionId) => seen.push(sessionId));
  const call: IncomingCallEvent = {
    source: "twilio",
    externalCallId: "CA778",
    from: "+15550000008",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  };
  const session = orchestrator.onIncomingCall(call);
  await orchestrator.onAudioFrame({
    sessionId: session.id,
    source: "twilio",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: Date.now(),
    payload: Buffer.from([0x03]),
  });

  assert.deepEqual(seen, [session.id]);
});

test("updateSessionControl changes mode and passthrough skips pipeline", async () => {
  const { orchestrator, stt } = makeOrchestrator();
  const session = orchestrator.onIncomingCall({
    source: "twilio",
    externalCallId: "CA901",
    from: "+15550000009",
    to: "+18005550199",
    receivedAtMs: Date.now(),
  });

  const updated = orchestrator.updateSessionControl(session.id, { mode: "passthrough" });
  assert.equal(updated?.mode, "passthrough");

  await orchestrator.onAudioFrame({
    sessionId: session.id,
    source: "twilio",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: Date.now(),
    payload: Buffer.from([0x01, 0x02]),
  });

  assert.equal(stt.calls, 0);
  const metrics = orchestrator.listMetrics()[0];
  assert.equal((metrics?.passthroughFrames ?? 0) >= 1, true);
});
