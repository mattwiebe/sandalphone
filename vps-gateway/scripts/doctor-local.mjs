#!/usr/bin/env node

import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

const envPath = resolve(process.env.ENV_PATH ?? ".env");
const warnings = [];
const failures = [];

function parseEnv(text) {
  const out = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const idx = trimmed.indexOf("=");
    if (idx <= 0) continue;
    const key = trimmed.slice(0, idx).trim();
    let value = trimmed.slice(idx + 1).trim();
    if (
      (value.startsWith("\"") && value.endsWith("\"")) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

function runCapture(command, args) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: "pipe",
    timeout: 10000,
  });

  return {
    status: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
    error: result.error?.message,
  };
}

async function checkHttpHealth(url, timeoutMs = 1200) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, {
      method: "GET",
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

if (!existsSync(envPath)) {
  failures.push(`missing env file: ${envPath}`);
}

const env = existsSync(envPath) ? parseEnv(readFileSync(envPath, "utf8")) : {};
const outboundTarget = env.OUTBOUND_TARGET_E164 ?? env.DESTINATION_PHONE_E164 ?? "";
if (!outboundTarget) {
  failures.push("OUTBOUND_TARGET_E164 is missing");
} else if (!/^\+[1-9]\d{7,14}$/.test(outboundTarget)) {
  failures.push("OUTBOUND_TARGET_E164 must be E.164 (example: +15555550100)");
}

const publicBaseUrl = env.PUBLIC_BASE_URL ?? "";
if (publicBaseUrl && !/^https:\/\//.test(publicBaseUrl)) {
  failures.push("PUBLIC_BASE_URL must be HTTPS for Twilio webhooks");
}

if (env.TWILIO_AUTH_TOKEN && !publicBaseUrl) {
  warnings.push("TWILIO_AUTH_TOKEN is set but PUBLIC_BASE_URL is empty");
}
if (!env.CONTROL_API_SECRET) {
  warnings.push("CONTROL_API_SECRET is not set; /sessions/control and /openclaw/command are unauthenticated");
}
if (env.OPENCLAW_BRIDGE_URL) {
  try {
    const healthUrl = `${new URL(env.OPENCLAW_BRIDGE_URL).origin}/health`;
    const ok = await checkHttpHealth(healthUrl);
    if (!ok) {
      warnings.push(`OPENCLAW_BRIDGE_URL health check failed: ${healthUrl}`);
    }
  } catch {
    warnings.push("OPENCLAW_BRIDGE_URL is not a valid URL");
  }
}

const tailscaleVersion = runCapture("tailscale", ["version"]);
if (tailscaleVersion.status !== 0) {
  warnings.push("tailscale CLI not detected in PATH");
} else {
  const funnelStatus = runCapture("tailscale", ["funnel", "status"]);
  const combined = `${funnelStatus.stdout}\n${funnelStatus.stderr}`.trim();
  if (funnelStatus.status !== 0) {
    warnings.push("tailscale funnel status failed");
  } else if (!combined.includes("https://")) {
    warnings.push("tailscale funnel appears inactive or URL not visible in status output");
  }
}

process.stdout.write("[doctor-local] Local readiness check\n");
process.stdout.write(`[doctor-local] env-path ${envPath}\n`);

for (const warning of warnings) {
  process.stdout.write(`[doctor-local] WARN ${warning}\n`);
}

if (failures.length > 0) {
  for (const failure of failures) {
    process.stderr.write(`[doctor-local] FAIL ${failure}\n`);
  }
  process.exit(1);
}

process.stdout.write("[doctor-local] PASS\n");
