#!/usr/bin/env node

import { createInterface } from "node:readline/promises";

const accountSid = process.env.TWILIO_ACCOUNT_SID ?? "";
const authToken = process.env.TWILIO_AUTH_TOKEN ?? "";
const from = process.env.SMOKE_OUTBOUND_FROM ?? process.env.TWILIO_PHONE_NUMBER ?? "";
let to = process.env.SMOKE_OUTBOUND_TO ?? process.env.OUTBOUND_TARGET_E164 ?? "";
const textEn =
  process.env.SMOKE_OUTBOUND_TEXT_EN ??
  "Hello. This is the outbound leg smoke test. English leg sounds good.";
const targetLanguage = process.env.SMOKE_OUTBOUND_TARGET_LANGUAGE ?? "es";
const googleApiKey = process.env.GOOGLE_CLOUD_API_KEY ?? "";

function log(step, detail) {
  process.stdout.write(`[smoke-outbound] ${step}${detail ? ` ${detail}` : ""}\n`);
}

function requireValue(name, value) {
  if (!value || value.trim().length === 0) {
    throw new Error(`${name} is required`);
  }
}

async function maybeTranslateToSpanish(text) {
  if (targetLanguage !== "es") return "";
  if (!googleApiKey) return "";

  const endpoint = `https://translation.googleapis.com/language/translate/v2?key=${encodeURIComponent(googleApiKey)}`;
  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      q: text,
      source: "en",
      target: "es",
      format: "text",
    }),
  });
  if (!response.ok) return "";
  const payload = await response.json();
  return payload?.data?.translations?.[0]?.translatedText ?? "";
}

function buildTwiml(lines) {
  const say = lines
    .filter((line) => line.text.trim().length > 0)
    .map(
      (line) =>
        `  <Say language="${line.language}">${escapeXml(line.text)}</Say>`,
    )
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n${say}\n  <Hangup/>\n</Response>`;
}

async function run() {
  requireValue("TWILIO_ACCOUNT_SID", accountSid);
  requireValue("TWILIO_AUTH_TOKEN", authToken);
  requireValue("SMOKE_OUTBOUND_FROM or TWILIO_PHONE_NUMBER", from);
  if (!to || to.trim().length === 0) {
    to = await promptForToIfMissing();
  }
  requireValue("SMOKE_OUTBOUND_TO or OUTBOUND_TARGET_E164", to);

  log("to", to);
  log("from", from);
  const translatedEs = await maybeTranslateToSpanish(textEn);

  const twiml = buildTwiml([
    { text: textEn, language: "en-US" },
    {
      text:
        translatedEs ||
        "Prueba del tramo saliente. Este mensaje confirma la salida en espanol.",
      language: "es-MX",
    },
  ]);

  const response = await fetch(
    `https://api.twilio.com/2010-04-01/Accounts/${encodeURIComponent(accountSid)}/Calls.json`,
    {
      method: "POST",
      headers: {
        authorization: `Basic ${Buffer.from(`${accountSid}:${authToken}`).toString("base64")}`,
        "content-type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        To: to,
        From: from,
        Twiml: twiml,
      }),
    },
  );

  const body = await response.text();
  if (!response.ok) {
    throw new Error(`Twilio calls.create failed ${response.status}: ${body.slice(0, 300)}`);
  }
  const payload = JSON.parse(body);
  log("queued", `callSid=${payload?.sid ?? "unknown"}`);
}

async function promptForToIfMissing() {
  if (!process.stdin.isTTY) {
    throw new Error("missing outbound destination: set OUTBOUND_TARGET_E164 or pass --to +E164");
  }
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  try {
    const answer = (await rl.question(
      "[smoke-outbound] outbound destination (E.164, e.g. +15555550100): ",
    )).trim();
    if (!/^\+[1-9]\d{7,14}$/.test(answer)) {
      throw new Error("invalid destination; must be E.164 format like +15555550100");
    }
    return answer;
  } finally {
    rl.close();
  }
}

function escapeXml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

run().catch((error) => {
  process.stderr.write(
    `[smoke-outbound] FAIL ${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
});
