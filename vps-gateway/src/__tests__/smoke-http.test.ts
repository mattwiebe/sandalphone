import assert from "node:assert/strict";
import test from "node:test";
import { once } from "node:events";
import type { AddressInfo } from "node:net";
import type { AudioFrame, TranscriptionChunk, TranslationChunk, TtsChunk } from "../domain/types.js";
import { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { SessionStore } from "../pipeline/session-store.js";
import { EgressStore } from "../pipeline/egress-store.js";
import { makeLogger } from "../server/logger.js";
import { startHttpServer } from "../server/http.js";

class SmokeStt {
  public readonly name = "smoke-stt";

  public async transcribe(frame: AudioFrame): Promise<TranscriptionChunk | null> {
    return {
      sessionId: frame.sessionId,
      text: "hola",
      isFinal: true,
      language: "es",
      timestampMs: Date.now(),
    };
  }
}

class SmokeTranslator {
  public readonly name = "smoke-translator";

  public async translate(chunk: TranscriptionChunk): Promise<TranslationChunk | null> {
    return {
      sessionId: chunk.sessionId,
      text: "hello",
      sourceLanguage: "es",
      targetLanguage: "en",
      timestampMs: Date.now(),
    };
  }
}

class SmokeTts {
  public readonly name = "smoke-tts";

  public async synthesize(chunk: TranslationChunk): Promise<TtsChunk | null> {
    return {
      sessionId: chunk.sessionId,
      encoding: "pcm_s16le",
      sampleRateHz: 16000,
      payload: Buffer.from([0x00, 0x00, 0x00, 0x00]),
      timestampMs: Date.now(),
    };
  }
}

type RunningApp = {
  baseUrl: string;
  stop: () => Promise<void>;
};

async function startSmokeApp(): Promise<RunningApp> {
  const logger = makeLogger("error");
  const egressStore = new EgressStore(16);
  const orchestrator = new VoiceOrchestrator({
    logger,
    sessionStore: new SessionStore(),
    stt: new SmokeStt(),
    translator: new SmokeTranslator(),
    tts: new SmokeTts(),
    destinationPhoneE164: "+15555550100",
    onTtsChunk: (chunk) => egressStore.enqueue(chunk),
  });

  const server = startHttpServer(0, logger, orchestrator, {
    egressStore,
    asteriskSharedSecret: "smokesecret",
  });
  await once(server, "listening");
  const address = server.address() as AddressInfo;

  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    stop: () =>
      new Promise((resolve, reject) => {
        server.close((error) => {
          if (error) reject(error);
          else resolve();
        });
      }),
  };
}

test("smoke: health + twilio voice endpoint", async () => {
  const app = await startSmokeApp();
  try {
    const health = await fetch(`${app.baseUrl}/health`);
    assert.equal(health.status, 200);
    const healthPayload = (await health.json()) as { ok: boolean };
    assert.equal(healthPayload.ok, true);

    const twilio = await fetch(`${app.baseUrl}/twilio/voice`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: "CallSid=CA_TEST&From=%2B15551234567&To=%2B18005550199",
    });
    assert.equal(twilio.status, 200);
    const twiml = await twilio.text();
    assert.ok(twiml.includes("+15555550100"));
  } finally {
    await app.stop();
  }
});

test("smoke: asterisk inbound/media/egress/end lifecycle", async () => {
  const app = await startSmokeApp();
  try {
    const commonHeaders = {
      "content-type": "application/json",
      "x-asterisk-secret": "smokesecret",
    };

    const inbound = await fetch(`${app.baseUrl}/asterisk/inbound`, {
      method: "POST",
      headers: commonHeaders,
      body: JSON.stringify({ callId: "sip-smoke", from: "+15550000001", to: "+18005550199" }),
    });
    assert.equal(inbound.status, 200);

    const media = await fetch(`${app.baseUrl}/asterisk/media`, {
      method: "POST",
      headers: commonHeaders,
      body: JSON.stringify({
        callId: "sip-smoke",
        sampleRateHz: 8000,
        encoding: "mulaw",
        payloadBase64: "AQI=",
      }),
    });
    assert.equal(media.status, 202);

    const egress = await fetch(
      `${app.baseUrl}/asterisk/egress/next?callId=sip-smoke&source=voipms`,
      {
        headers: { "x-asterisk-secret": "smokesecret" },
      },
    );
    assert.equal(egress.status, 200);
    const egressPayload = (await egress.json()) as {
      sampleRateHz: number;
      encoding: string;
      payloadBase64: string;
      sessionId: string;
    };
    assert.equal(egressPayload.sampleRateHz, 16000);
    assert.equal(egressPayload.encoding, "pcm_s16le");
    assert.ok(egressPayload.payloadBase64.length > 0);

    const end = await fetch(`${app.baseUrl}/asterisk/end`, {
      method: "POST",
      headers: commonHeaders,
      body: JSON.stringify({ sessionId: egressPayload.sessionId }),
    });
    assert.equal(end.status, 200);

    const sessions = await fetch(`${app.baseUrl}/sessions`);
    assert.equal(sessions.status, 200);
    const sessionsPayload = (await sessions.json()) as {
      sessions: Array<{ id: string; state: string }>;
    };
    const ended = sessionsPayload.sessions.find((s) => s.id === egressPayload.sessionId);
    assert.equal(ended?.state, "ended");
  } finally {
    await app.stop();
  }
});
