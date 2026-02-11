#!/usr/bin/env node

const baseUrl = (process.env.BASE_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
const controlSecret = process.env.CONTROL_API_SECRET ?? "";
const mode = process.env.SMOKE_INBOUND_MODE ?? "status";
const message =
  process.env.SMOKE_INBOUND_MESSAGE ??
  "Hello. Inbound test mode is active. This verifies inbound call handling.";

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
  if (mode === "status") {
    const response = await fetch(`${baseUrl}/test/inbound-mode`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
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
