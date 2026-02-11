#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const baseUrl = (process.env.BASE_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
const controlSecret = resolveValue("CONTROL_API_SECRET");
const mode = process.env.SMOKE_INBOUND_MODE ?? "status";
const message =
  process.env.SMOKE_INBOUND_MESSAGE ??
  "Hello. Inbound test mode is active. This verifies inbound call handling.";
let cachedEnvMap;
const envPathUsed = resolve(process.env.ENV_PATH ?? ".env");

function authHeaders(contentType = false) {
  const headers = {};
  if (contentType) headers["content-type"] = "application/json";
  if (controlSecret) headers["x-control-secret"] = controlSecret;
  return headers;
}

function log(step, detail) {
  process.stdout.write(`[smoke-inbound] ${step}${detail ? ` ${detail}` : ""}\n`);
}

async function run() {
  log("base-url", baseUrl);
  log("env-path", envPathUsed);
  log("control-secret", controlSecret ? "loaded" : "missing");

  if (mode === "status") {
    const response = await fetch(`${baseUrl}/test/inbound-mode`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      if (response.status === 403) {
        throw new Error(
          "/test/inbound-mode returned 403 (set CONTROL_API_SECRET in .env, or pass --secret ...)",
        );
      }
      throw new Error(`/test/inbound-mode returned ${response.status}`);
    }
    const payload = await response.json();
    log("status", `enabled=${Boolean(payload?.inboundTestMode?.enabled)}`);
    log("message", `"${payload?.inboundTestMode?.message ?? ""}"`);
    return;
  }

  if (mode !== "enable" && mode !== "disable") {
    throw new Error(`unsupported mode: ${mode}`);
  }

  const response = await fetch(`${baseUrl}/test/inbound-mode`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({
      enabled: mode === "enable",
      message,
    }),
  });
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error(
        "/test/inbound-mode returned 403 (set CONTROL_API_SECRET in .env, or pass --secret ...)",
      );
    }
    throw new Error(`/test/inbound-mode returned ${response.status}`);
  }
  const payload = await response.json();
  log("updated", `enabled=${Boolean(payload?.inboundTestMode?.enabled)}`);
  log("message", `"${payload?.inboundTestMode?.message ?? ""}"`);
  if (mode === "enable") {
    log("next", "call your Twilio DID now; it should speak and hang up without forwarding");
  }
}

run().catch((error) => {
  process.stderr.write(
    `[smoke-inbound] FAIL ${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
});

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
  if (!existsSync(envPathUsed)) {
    cachedEnvMap = {};
    return cachedEnvMap;
  }
  const out = {};
  const text = readFileSync(envPathUsed, "utf8");
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
