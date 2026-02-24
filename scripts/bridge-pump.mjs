#!/usr/bin/env node

const baseUrl = (process.env.BRIDGE_BASE_URL ?? "").trim();
const callId = (process.env.BRIDGE_CALL_ID ?? "").trim();
const source = normalizeSource(process.env.BRIDGE_SOURCE ?? "voipms");
const from = (process.env.BRIDGE_FROM ?? "").trim();
const to = (process.env.BRIDGE_TO ?? "").trim();
const encoding = normalizeEncoding(process.env.BRIDGE_ENCODING ?? "mulaw");
const sampleRateHz = Number(process.env.BRIDGE_SAMPLE_RATE_HZ ?? "8000");
const chunkMs = Number(process.env.BRIDGE_MEDIA_CHUNK_MS ?? "20");
const pollMs = Number(process.env.BRIDGE_EGRESS_POLL_MS ?? "40");
const bootstrap = !isFalsey(process.env.BRIDGE_BOOTSTRAP ?? "1");
const explicitSessionId = (process.env.BRIDGE_SESSION_ID ?? "").trim();
const asteriskSecret = (process.env.BRIDGE_ASTERISK_SECRET ?? "").trim();

if (!baseUrl) fail("BRIDGE_BASE_URL is required");
if (!callId && !explicitSessionId) fail("BRIDGE_CALL_ID or BRIDGE_SESSION_ID is required");
if (!Number.isFinite(sampleRateHz) || sampleRateHz < 1000) {
  fail("BRIDGE_SAMPLE_RATE_HZ must be a valid number");
}
if (!Number.isFinite(chunkMs) || chunkMs < 10) {
  fail("BRIDGE_MEDIA_CHUNK_MS must be >= 10");
}
if (!Number.isFinite(pollMs) || pollMs < 10) {
  fail("BRIDGE_EGRESS_POLL_MS must be >= 10");
}

const framesPerChunk = Math.floor((sampleRateHz * chunkMs) / 1000);
const bytesPerSample = encoding === "mulaw" ? 1 : 2;
const bytesPerChunk = Math.max(framesPerChunk * bytesPerSample, bytesPerSample);
let mediaBuffer = Buffer.alloc(0);
let running = true;
let resolvedSessionId = explicitSessionId || "";
let mediaInFlight = 0;
let mediaSent = 0;
let egressReceived = 0;
let mediaDropped = 0;
let egressPollTimer;
let mediaFlushTimer;

function log(step, detail) {
  process.stderr.write(`[bridge-pump] ${step}${detail ? ` ${detail}` : ""}\n`);
}

function fail(message) {
  process.stderr.write(`[bridge-pump] FAIL ${message}\n`);
  process.exit(1);
}

function headers() {
  const out = { "content-type": "application/json" };
  if (asteriskSecret) out["x-asterisk-secret"] = asteriskSecret;
  return out;
}

function normalizeSource(value) {
  const normalized = value.trim().toLowerCase();
  if (normalized === "twilio" || normalized === "voipms") return normalized;
  fail(`unsupported BRIDGE_SOURCE: ${value}`);
}

function normalizeEncoding(value) {
  const normalized = value.trim().toLowerCase();
  if (normalized === "mulaw" || normalized === "pcm_s16le") return normalized;
  fail(`unsupported BRIDGE_ENCODING: ${value}`);
}

function isFalsey(value) {
  const normalized = value.trim().toLowerCase();
  return normalized === "0" || normalized === "false" || normalized === "no";
}

async function bootstrapSession() {
  if (!bootstrap || resolvedSessionId) return;
  if (!callId || !from || !to) {
    fail("bootstrap requires BRIDGE_CALL_ID, BRIDGE_FROM and BRIDGE_TO");
  }
  const response = await fetch(`${baseUrl}/asterisk/inbound`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      callId,
      source,
      from,
      to,
    }),
  });
  if (!response.ok) {
    const body = await response.text();
    fail(`/asterisk/inbound returned ${response.status}: ${body.slice(0, 300)}`);
  }
  const payload = await response.json();
  if (typeof payload.sessionId !== "string" || payload.sessionId.trim().length === 0) {
    fail("/asterisk/inbound missing sessionId");
  }
  resolvedSessionId = payload.sessionId;
  log("session", `${resolvedSessionId} source=${source}`);
}

async function sendMediaChunk(chunk) {
  mediaInFlight += 1;
  try {
    const response = await fetch(`${baseUrl}/asterisk/media`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        callId,
        source,
        sampleRateHz,
        encoding,
        payloadBase64: chunk.toString("base64"),
      }),
    });
    if (response.status === 202) {
      mediaSent += 1;
      return;
    }
    const body = await response.text();
    log("media", `drop status=${response.status} body=${body.slice(0, 120)}`);
    mediaDropped += 1;
  } catch (error) {
    log("media", `error=${error instanceof Error ? error.message : String(error)}`);
    mediaDropped += 1;
  } finally {
    mediaInFlight -= 1;
  }
}

function drainBufferedMedia() {
  while (mediaBuffer.length >= bytesPerChunk) {
    const chunk = mediaBuffer.subarray(0, bytesPerChunk);
    mediaBuffer = mediaBuffer.subarray(bytesPerChunk);
    void sendMediaChunk(chunk);
  }
}

async function pollEgress() {
  if (!running) return;
  const query = resolvedSessionId
    ? `sessionId=${encodeURIComponent(resolvedSessionId)}`
    : `callId=${encodeURIComponent(callId)}&source=${encodeURIComponent(source)}`;
  try {
    const response = await fetch(`${baseUrl}/asterisk/egress/next?${query}`, {
      headers: asteriskSecret ? { "x-asterisk-secret": asteriskSecret } : {},
    });
    if (response.status === 204 || response.status === 404) {
      return;
    }
    if (!response.ok) {
      const body = await response.text();
      log("egress", `status=${response.status} body=${body.slice(0, 120)}`);
      return;
    }
    const payload = await response.json();
    if (typeof payload.sessionId === "string" && !resolvedSessionId) {
      resolvedSessionId = payload.sessionId;
    }
    if (typeof payload.payloadBase64 !== "string") {
      return;
    }
    const chunk = Buffer.from(payload.payloadBase64, "base64");
    if (chunk.length > 0) {
      process.stdout.write(chunk);
      egressReceived += 1;
    }
  } catch (error) {
    log("egress", `error=${error instanceof Error ? error.message : String(error)}`);
  }
}

async function endSession() {
  if (!resolvedSessionId && !callId) return;
  try {
    const body = resolvedSessionId
      ? { sessionId: resolvedSessionId, source }
      : { callId, source };
    const response = await fetch(`${baseUrl}/asterisk/end`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const text = await response.text();
      log("end", `status=${response.status} body=${text.slice(0, 120)}`);
      return;
    }
    log("end", "ok");
  } catch (error) {
    log("end", `error=${error instanceof Error ? error.message : String(error)}`);
  }
}

async function shutdown() {
  if (!running) return;
  running = false;
  if (mediaFlushTimer) clearInterval(mediaFlushTimer);
  if (egressPollTimer) clearInterval(egressPollTimer);
  if (mediaBuffer.length > 0) {
    await sendMediaChunk(mediaBuffer);
    mediaBuffer = Buffer.alloc(0);
  }
  while (mediaInFlight > 0) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  await endSession();
  log("stats", `media_sent=${mediaSent} media_dropped=${mediaDropped} egress=${egressReceived}`);
}

process.on("SIGINT", async () => {
  await shutdown();
  process.exit(0);
});
process.on("SIGTERM", async () => {
  await shutdown();
  process.exit(0);
});

async function main() {
  await bootstrapSession();

  process.stdin.on("data", (chunk) => {
    mediaBuffer = Buffer.concat([mediaBuffer, chunk]);
  });
  process.stdin.on("end", async () => {
    await shutdown();
    process.exit(0);
  });

  mediaFlushTimer = setInterval(drainBufferedMedia, Math.max(chunkMs / 2, 10));
  egressPollTimer = setInterval(() => {
    void pollEgress();
  }, pollMs);

  log(
    "start",
    `source=${source} encoding=${encoding}@${sampleRateHz} chunk=${bytesPerChunk}B poll=${pollMs}ms`,
  );
}

await main();
