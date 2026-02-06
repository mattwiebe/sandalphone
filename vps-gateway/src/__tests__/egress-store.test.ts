import assert from "node:assert/strict";
import test from "node:test";
import { EgressStore } from "../pipeline/egress-store.js";

test("EgressStore enqueue/dequeue is FIFO", () => {
  const store = new EgressStore(10);
  store.enqueue({
    sessionId: "s1",
    encoding: "pcm_s16le",
    sampleRateHz: 16000,
    payload: Buffer.from([0x01]),
    timestampMs: 1,
  });
  store.enqueue({
    sessionId: "s1",
    encoding: "pcm_s16le",
    sampleRateHz: 16000,
    payload: Buffer.from([0x02]),
    timestampMs: 2,
  });

  assert.equal(store.dequeue("s1")?.timestampMs, 1);
  assert.equal(store.dequeue("s1")?.timestampMs, 2);
  assert.equal(store.dequeue("s1"), undefined);
});

test("EgressStore drops oldest when queue exceeds max", () => {
  const store = new EgressStore(2);
  store.enqueue({
    sessionId: "s2",
    encoding: "pcm_s16le",
    sampleRateHz: 16000,
    payload: Buffer.from([0x01]),
    timestampMs: 1,
  });
  store.enqueue({
    sessionId: "s2",
    encoding: "pcm_s16le",
    sampleRateHz: 16000,
    payload: Buffer.from([0x02]),
    timestampMs: 2,
  });
  store.enqueue({
    sessionId: "s2",
    encoding: "pcm_s16le",
    sampleRateHz: 16000,
    payload: Buffer.from([0x03]),
    timestampMs: 3,
  });

  assert.equal(store.dequeue("s2")?.timestampMs, 2);
  assert.equal(store.dequeue("s2")?.timestampMs, 3);
});
