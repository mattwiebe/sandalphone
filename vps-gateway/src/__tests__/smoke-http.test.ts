import assert from "node:assert/strict";
import test from "node:test";
import { once } from "node:events";
import { createServer } from "node:http";
import type { AddressInfo } from "node:net";
import type { AudioFrame, TranscriptionChunk, TranslationChunk, TtsChunk } from "../domain/types.js";
import { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { SessionStore } from "../pipeline/session-store.js";
import { EgressStore } from "../pipeline/egress-store.js";
import { makeLogger } from "../server/logger.js";
import { startHttpServer } from "../server/http.js";
import { makeOpenClawBridge } from "../integrations/openclaw.js";

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
  eventSink: Array<Record<string, unknown>>;
  stop: () => Promise<void>;
};

async function startSmokeApp(): Promise<RunningApp> {
  const logger = makeLogger("error");
  const egressStore = new EgressStore(16);
  let orchestratorRef: VoiceOrchestrator | undefined;
  const orchestrator = new VoiceOrchestrator({
    logger,
    sessionStore: new SessionStore(),
    stt: new SmokeStt(),
    translator: new SmokeTranslator(),
    tts: new SmokeTts(),
    outboundTargetE164: "+15555550100",
    onTtsChunk: (chunk) => {
      const enqueue = egressStore.enqueue(chunk);
      orchestratorRef?.reportEgressStats(chunk.sessionId, enqueue);
    },
  });
  orchestratorRef = orchestrator;

  const eventSink: Array<Record<string, unknown>> = [];
  const bridgeReceiver = createServer(async (req, res) => {
    if (req.method !== "POST" || req.url !== "/bridge") {
      res.statusCode = 404;
      res.end();
      return;
    }
    const chunks: Buffer[] = [];
    for await (const chunk of req) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    const parsed = JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<string, unknown>;
    eventSink.push(parsed);
    res.statusCode = 200;
    res.setHeader("content-type", "application/json");
    res.end('{"ok":true}');
  });
  bridgeReceiver.listen(0);
  await once(bridgeReceiver, "listening");
  const bridgeAddress = bridgeReceiver.address() as AddressInfo;
  const openClawBridge = makeOpenClawBridge({
    endpointUrl: `http://127.0.0.1:${bridgeAddress.port}/bridge`,
    timeoutMs: 400,
    logger,
  });
  const server = startHttpServer(0, logger, orchestrator, {
    egressStore,
    asteriskSharedSecret: "smokesecret",
    controlApiSecret: "controlsecret",
    openClawBridge,
  });
  await once(server, "listening");
  const address = server.address() as AddressInfo;

  return {
    baseUrl: `http://127.0.0.1:${address.port}`,
    eventSink,
    stop: () =>
      new Promise((resolve, reject) => {
        server.close((error) => {
          if (error) {
            reject(error);
            return;
          }
          bridgeReceiver.close((bridgeError) => {
            if (bridgeError) reject(bridgeError);
            else resolve();
          });
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

    const debug = await fetch(
      `${app.baseUrl}/sessions/${encodeURIComponent(egressPayload.sessionId)}/debug`,
      {
        headers: { "x-control-secret": "controlsecret" },
      },
    );
    assert.equal(debug.status, 200);
    const debugPayload = (await debug.json()) as {
      metrics?: { egressQueuePeak?: number; translatedChunks?: number };
    };
    assert.equal((debugPayload.metrics?.egressQueuePeak ?? 0) >= 1, true);
    assert.equal((debugPayload.metrics?.translatedChunks ?? 0) >= 1, true);
  } finally {
    await app.stop();
  }
});

test("smoke: session control endpoint can switch to passthrough mode", async () => {
  const app = await startSmokeApp();
  try {
    const inbound = await fetch(`${app.baseUrl}/asterisk/inbound`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-asterisk-secret": "smokesecret",
      },
      body: JSON.stringify({ callId: "sip-control", from: "+15550000001", to: "+18005550199" }),
    });
    assert.equal(inbound.status, 200);
    const inboundPayload = (await inbound.json()) as { sessionId: string };

    const control = await fetch(`${app.baseUrl}/sessions/control`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-control-secret": "controlsecret",
      },
      body: JSON.stringify({
        sessionId: inboundPayload.sessionId,
        mode: "passthrough",
      }),
    });
    assert.equal(control.status, 200);

    const media = await fetch(`${app.baseUrl}/asterisk/media`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-asterisk-secret": "smokesecret",
      },
      body: JSON.stringify({
        callId: "sip-control",
        sampleRateHz: 8000,
        encoding: "mulaw",
        payloadBase64: "AQI=",
      }),
    });
    assert.equal(media.status, 202);

    const egress = await fetch(
      `${app.baseUrl}/asterisk/egress/next?callId=sip-control&source=voipms`,
      {
        headers: { "x-asterisk-secret": "smokesecret" },
      },
    );
    assert.equal(egress.status, 204);
  } finally {
    await app.stop();
  }
});

test("smoke: openclaw command endpoint relays command", async () => {
  const app = await startSmokeApp();
  try {
    const response = await fetch(`${app.baseUrl}/openclaw/command`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-control-secret": "controlsecret",
      },
      body: JSON.stringify({
        command: "research market rates for voip wholesale mexico",
        source: "twilio",
      }),
    });

    assert.equal(response.status, 202);
    await waitFor(() => app.eventSink.some((event) => event.type === "command"), 1000);
    assert.ok(app.eventSink.some((event) => event.type === "command"));
  } finally {
    await app.stop();
  }
});

function waitFor(predicate: () => boolean, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const started = Date.now();
    const interval = setInterval(() => {
      if (predicate()) {
        clearInterval(interval);
        resolve();
        return;
      }
      if (Date.now() - started > timeoutMs) {
        clearInterval(interval);
        reject(new Error("timeout waiting for condition"));
      }
    }, 25);
  });
}
