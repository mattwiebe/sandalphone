#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createHmac } from "node:crypto";

const envPath = resolve(process.env.ENV_PATH ?? ".env");
let cachedEnvMap;

function log(step, detail) {
  process.stdout.write(`[smoke-twilio-stream] ${step}${detail ? ` ${detail}` : ""}\n`);
}

function resolveValue(key, fallback = "") {
  const fromProcess = process.env[key];
  if (fromProcess && fromProcess.trim().length > 0) return fromProcess.trim();
  const envMap = loadEnvMap();
  const fromFile = envMap[key];
  if (fromFile && fromFile.trim().length > 0) return fromFile.trim();
  return fallback;
}

function loadEnvMap() {
  if (cachedEnvMap !== undefined) return cachedEnvMap;
  if (!existsSync(envPath)) {
    cachedEnvMap = {};
    return cachedEnvMap;
  }
  const out = {};
  const text = readFileSync(envPath, "utf8");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const idx = line.indexOf("=");
    if (idx <= 0) continue;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    if (
      (value.startsWith("\"") && value.endsWith("\"")) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  cachedEnvMap = out;
  return cachedEnvMap;
}

async function run() {
  const baseUrl = resolveBaseUrl();
  const expectedMode = resolveValue("TWILIO_VOICE_MODE", "dial").toLowerCase();
  const expectedWsOverride = resolveValue("TWILIO_STREAM_WS_URL");
  const publicBaseUrl = resolveValue("PUBLIC_BASE_URL");
  const trustedCaller = resolveValue("OUTBOUND_TARGET_E164", "+15555550100");
  const twilioAuthToken = resolveValue("TWILIO_AUTH_TOKEN");
  const expectedWsUrl =
    expectedWsOverride ||
    (publicBaseUrl ? `wss://${publicBaseUrl.replace(/^https?:\/\//, "").replace(/\/+$/, "")}/twilio/stream` : "");

  log("base-url", baseUrl);
  log("env-path", envPath);

  await waitForGatewayReady(baseUrl);

  if (expectedMode !== "stream") {
    throw new Error("TWILIO_VOICE_MODE is not stream");
  }

  const formFields = {
    CallSid: "CA_STREAM_SMOKE",
    From: trustedCaller,
    To: "+18005550199",
  };
  const twilioHeaders = { "content-type": "application/x-www-form-urlencoded" };
  const signatureBaseUrl = (publicBaseUrl || baseUrl).replace(/\/+$/, "");
  if (twilioAuthToken) {
    twilioHeaders["x-twilio-signature"] = computeTwilioSignature(
      `${signatureBaseUrl}/twilio/voice`,
      formFields,
      twilioAuthToken,
    );
  }

  let twilio;
  try {
    twilio = await fetch(`${baseUrl}/twilio/voice`, {
      method: "POST",
      headers: twilioHeaders,
      body: new URLSearchParams(formFields),
    });
  } catch (error) {
    throw new Error(
      `fetch failed (gateway unreachable at ${baseUrl}; check service status and PORT/.env alignment): ${error instanceof Error ? error.message : String(error)}`,
    );
  }
  if (!twilio.ok) {
    throw new Error(`/twilio/voice returned ${twilio.status}`);
  }
  const twiml = await twilio.text();
  if (!twiml.includes("<Connect>") || !twiml.includes("<Stream")) {
    throw new Error("Twilio stream mode not active; /twilio/voice did not return <Connect><Stream>");
  }
  if (expectedWsUrl && !twiml.includes(expectedWsUrl)) {
    throw new Error(`stream URL mismatch; expected ${expectedWsUrl}`);
  }
  log("twilio-voice", "stream TwiML ok");
  log("result", "PASS");
}

function computeTwilioSignature(url, formFields, authToken) {
  const sorted = Object.keys(formFields).sort();
  let payload = url;
  for (const key of sorted) {
    payload += key + formFields[key];
  }
  return createHmac("sha1", authToken).update(payload).digest("base64");
}

function resolveBaseUrl() {
  const explicit = process.env.BASE_URL?.trim();
  if (explicit) return explicit.replace(/\/+$/, "");
  const port = resolveValue("PORT", "8080");
  return `http://127.0.0.1:${port}`.replace(/\/+$/, "");
}

async function waitForGatewayReady(baseUrl) {
  const deadlineMs = Date.now() + 15000;
  let lastError = "";
  while (Date.now() < deadlineMs) {
    try {
      const response = await fetch(`${baseUrl}/health`);
      if (response.ok) {
        return;
      }
      lastError = `/health returned ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await sleep(500);
  }
  throw new Error(`gateway health check failed at ${baseUrl}: ${lastError}`);
}

function sleep(ms) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

run().catch((error) => {
  process.stderr.write(
    `[smoke-twilio-stream] FAIL ${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
});
