#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

let cachedEnvMap;
const envPathUsed = resolve(process.env.ENV_PATH ?? ".env");
const baseUrl = (process.env.BASE_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
const controlSecret = resolveValue("CONTROL_API_SECRET");
const mode = process.env.SMOKE_INBOUND_MODE ?? "status";
const message =
  process.env.SMOKE_INBOUND_MESSAGE ??
  "Hello. Inbound test mode is active. English leg is speaking now.";
const strictCompletion = (process.env.SMOKE_INBOUND_STRICT_COMPLETION ?? "1") !== "0";
const watchEnabled = (process.env.SMOKE_INBOUND_WATCH ?? "1") !== "0";
const watchTimeoutMs = Number(process.env.SMOKE_INBOUND_TIMEOUT_MS ?? "180000");

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
  log("strict-completion", strictCompletion ? "enabled" : "disabled");

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
    if (payload?.inboundTestMode?.activeCallSid) {
      log("active-call", payload.inboundTestMode.activeCallSid);
    }
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
      messageEs: await resolveSpanishTestMessage(message),
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
    if (!watchEnabled) {
      log("next", "call your Twilio DID now; it should speak and hang up without forwarding");
      return;
    }
    await watchInboundCycle(payload?.inboundTestMode?.lastEventId ?? 0);
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

async function watchInboundCycle(initialEventId) {
  const startedAt = Date.now();
  let lastEventId = Number.isFinite(initialEventId) ? Number(initialEventId) : 0;
  let seenIncoming = false;
  let activeCallSid = "";

  const onSignal = async (signal) => {
    log("signal", `${signal}; disabling inbound test mode before exit`);
    try {
      await disableInboundMode();
    } catch (error) {
      log("warn", `failed to disable test mode: ${error instanceof Error ? error.message : String(error)}`);
    }
    process.exit(130);
  };
  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);

  log("watch", "waiting for inbound call...");
  try {
    while (true) {
      if (Date.now() - startedAt > watchTimeoutMs) {
        await disableInboundMode();
        throw new Error(`timed out waiting for inbound cycle (${watchTimeoutMs}ms)`);
      }

      const status = await fetchInboundModeStatus(lastEventId);
      const events = Array.isArray(status?.recentEvents) ? status.recentEvents : [];
      for (const event of events) {
        if (typeof event?.id === "number" && event.id > lastEventId) {
          lastEventId = event.id;
        }
        if (event?.type === "incoming") {
          seenIncoming = true;
          activeCallSid = event.callSid ?? "";
          log(
            "incoming",
            `from=${event.from ?? "unknown"} to=${event.to ?? "unknown"} callSid=${event.callSid ?? "unknown"}`,
          );
          if (strictCompletion) {
            const terminal = await waitForTwilioTerminalStatus(activeCallSid, startedAt + watchTimeoutMs);
            if (terminal) {
              log("call-status", terminal);
              await disableInboundMode();
              log("updated", "enabled=false");
              return;
            }
          }
        } else if (event?.type === "completed") {
          log("completed", `callSid=${event.callSid ?? "unknown"}`);
          await disableInboundMode();
          log("updated", "enabled=false");
          return;
        }
      }

      if (seenIncoming && !status?.enabled) {
        log("updated", "enabled=false");
        return;
      }

      await sleep(1000);
    }
  } finally {
    process.removeListener("SIGINT", onSignal);
    process.removeListener("SIGTERM", onSignal);
  }
}

async function fetchInboundModeStatus(sinceEventId) {
  const response = await fetch(
    `${baseUrl}/test/inbound-mode?sinceEventId=${encodeURIComponent(String(sinceEventId ?? 0))}`,
    {
      headers: authHeaders(),
    },
  );
  if (!response.ok) {
    if (response.status === 403) {
      throw new Error(
        "/test/inbound-mode returned 403 (set CONTROL_API_SECRET in .env, or pass --secret ...)",
      );
    }
    throw new Error(`/test/inbound-mode returned ${response.status}`);
  }
  const payload = await response.json();
  return payload?.inboundTestMode;
}

async function disableInboundMode() {
  const response = await fetch(`${baseUrl}/test/inbound-mode`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify({
      enabled: false,
    }),
  });
  if (!response.ok) {
    throw new Error(`/test/inbound-mode disable returned ${response.status}`);
  }
}

function sleep(ms) {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

async function resolveSpanishTestMessage(textEn) {
  const override = resolveValue("SMOKE_INBOUND_MESSAGE_ES");
  if (override) return override;

  const googleApiKey = resolveValue("GOOGLE_CLOUD_API_KEY");
  if (!googleApiKey) {
    return "Hola. El modo de prueba entrante esta activo. La traduccion al espanol esta sonando.";
  }
  try {
    const endpoint = `https://translation.googleapis.com/language/translate/v2?key=${encodeURIComponent(googleApiKey)}`;
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        q: textEn,
        source: "en",
        target: "es",
        format: "text",
      }),
    });
    if (!response.ok) {
      return "Hola. El modo de prueba entrante esta activo. La traduccion al espanol esta sonando.";
    }
    const payload = await response.json();
    const translated = payload?.data?.translations?.[0]?.translatedText;
    return translated && translated.trim().length > 0
      ? translated.trim()
      : "Hola. El modo de prueba entrante esta activo. La traduccion al espanol esta sonando.";
  } catch {
    return "Hola. El modo de prueba entrante esta activo. La traduccion al espanol esta sonando.";
  }
}

async function waitForTwilioTerminalStatus(callSid, deadlineMs) {
  if (!callSid) return "unknown";
  const accountSid = resolveValue("TWILIO_ACCOUNT_SID");
  const authToken = resolveValue("TWILIO_AUTH_TOKEN");
  if (!accountSid || !authToken) {
    log("warn", "strict completion requested but Twilio credentials missing; using event completion");
    return "";
  }

  while (Date.now() < deadlineMs) {
    const status = await fetchTwilioCallStatus(accountSid, authToken, callSid);
    if (
      status === "completed" ||
      status === "busy" ||
      status === "failed" ||
      status === "no-answer" ||
      status === "canceled"
    ) {
      return status;
    }
    await sleep(1000);
  }
  throw new Error(`timed out waiting for Twilio call terminal status for ${callSid}`);
}

async function fetchTwilioCallStatus(accountSid, authToken, callSid) {
  const response = await fetch(
    `https://api.twilio.com/2010-04-01/Accounts/${encodeURIComponent(accountSid)}/Calls/${encodeURIComponent(callSid)}.json`,
    {
      headers: {
        authorization: `Basic ${Buffer.from(`${accountSid}:${authToken}`).toString("base64")}`,
      },
    },
  );
  if (!response.ok) {
    throw new Error(`Twilio call status lookup failed ${response.status}`);
  }
  const payload = await response.json();
  return String(payload?.status ?? "").trim().toLowerCase();
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
