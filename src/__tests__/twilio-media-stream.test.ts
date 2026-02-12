import assert from "node:assert/strict";
import test from "node:test";
import { EventEmitter } from "node:events";
import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { EgressStore } from "../pipeline/egress-store.js";
import { makeLogger } from "../server/logger.js";
import { wireTwilioMediaSocket } from "../ingress/twilio-media-stream.js";

class FakeWs extends EventEmitter {
  public readonly sent: string[] = [];

  public send(payload: string): void {
    this.sent.push(payload);
  }
}

function makeFakeOrchestrator(
  mode: "private_translation" | "passthrough",
): VoiceOrchestrator {
  return {
    resolveSessionIdByExternal: () => "session-1",
    onAudioFrame: async () => {},
    getSession: () => ({
      id: "session-1",
      source: "twilio",
      inboundCaller: "+15551234567",
      startedAtMs: Date.now(),
      targetPhoneE164: "+15550000001",
      mode,
      sourceLanguage: "es",
      targetLanguage: "en",
      state: "active",
    }),
    endSession: () => {},
  } as unknown as VoiceOrchestrator;
}

test("twilio media stream flushes mulaw egress back to websocket", async () => {
  const ws = new FakeWs();
  const egressStore = new EgressStore(8);
  egressStore.enqueue({
    sessionId: "session-1",
    encoding: "mulaw",
    sampleRateHz: 8000,
    payload: Buffer.from([0x01, 0x02, 0x03]),
    timestampMs: Date.now(),
  });

  wireTwilioMediaSocket(ws as unknown as Parameters<typeof wireTwilioMediaSocket>[0], makeFakeOrchestrator("private_translation"), makeLogger("error"), egressStore);

  ws.emit(
    "message",
    Buffer.from(
      JSON.stringify({
        event: "start",
        start: { callSid: "CA1", streamSid: "MZ1" },
      }),
      "utf8",
    ),
  );
  ws.emit(
    "message",
    Buffer.from(
      JSON.stringify({
        event: "media",
        media: { payload: "AQI=", timestamp: "1" },
      }),
      "utf8",
    ),
  );

  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(ws.sent.length, 1);
  const outbound = JSON.parse(ws.sent[0]) as {
    event: string;
    streamSid: string;
    media: { payload: string };
  };
  assert.equal(outbound.event, "media");
  assert.equal(outbound.streamSid, "MZ1");
  assert.equal(outbound.media.payload, Buffer.from([0x01, 0x02, 0x03]).toString("base64"));
});

test("twilio media stream clears queued egress in passthrough mode", async () => {
  const ws = new FakeWs();
  const egressStore = new EgressStore(8);
  egressStore.enqueue({
    sessionId: "session-1",
    encoding: "mulaw",
    sampleRateHz: 8000,
    payload: Buffer.from([0x01]),
    timestampMs: Date.now(),
  });

  wireTwilioMediaSocket(ws as unknown as Parameters<typeof wireTwilioMediaSocket>[0], makeFakeOrchestrator("passthrough"), makeLogger("error"), egressStore);

  ws.emit(
    "message",
    Buffer.from(
      JSON.stringify({
        event: "start",
        start: { callSid: "CA2", streamSid: "MZ2" },
      }),
      "utf8",
    ),
  );
  ws.emit(
    "message",
    Buffer.from(
      JSON.stringify({
        event: "media",
        media: { payload: "AQI=", timestamp: "1" },
      }),
      "utf8",
    ),
  );

  await new Promise((resolve) => setTimeout(resolve, 5));
  assert.equal(ws.sent.length, 0);
  assert.equal(egressStore.size("session-1"), 0);
});
