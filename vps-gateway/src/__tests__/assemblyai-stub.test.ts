import assert from "node:assert/strict";
import test from "node:test";
import { StubAssemblyAiProvider } from "../providers/stt/assemblyai.js";

test("StubAssemblyAiProvider emits configured transcript text", async () => {
  const provider = new StubAssemblyAiProvider("hola mundo");
  const chunk = await provider.transcribe({
    sessionId: "s1",
    source: "voipms",
    sampleRateHz: 8000,
    encoding: "mulaw",
    timestampMs: Date.now(),
    payload: Buffer.from([0x01]),
  });

  assert.equal(chunk?.text, "hola mundo");
  assert.equal(chunk?.isFinal, true);
});
