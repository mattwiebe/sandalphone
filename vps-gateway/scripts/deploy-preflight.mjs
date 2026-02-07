#!/usr/bin/env node

const optionalCloud = ["GOOGLE_CLOUD_API_KEY"];
const warnings = [];
const failures = [];

const outboundTarget = process.env.OUTBOUND_TARGET_E164 ?? process.env.DESTINATION_PHONE_E164 ?? "";
if (!outboundTarget) {
  failures.push("OUTBOUND_TARGET_E164 is required (legacy fallback: DESTINATION_PHONE_E164)");
}
if (outboundTarget && !/^\+[1-9]\d{7,14}$/.test(outboundTarget)) {
  failures.push(
    "OUTBOUND_TARGET_E164 must be E.164 format, e.g. +15555550100 (legacy fallback: DESTINATION_PHONE_E164)",
  );
}
if (!process.env.OUTBOUND_TARGET_E164 && process.env.DESTINATION_PHONE_E164) {
  warnings.push("Using legacy DESTINATION_PHONE_E164; migrate to OUTBOUND_TARGET_E164");
}

if (process.env.TWILIO_AUTH_TOKEN && !process.env.PUBLIC_BASE_URL) {
  warnings.push("PUBLIC_BASE_URL is recommended when TWILIO_AUTH_TOKEN is set");
}

if (!process.env.ASTERISK_SHARED_SECRET) {
  warnings.push("ASTERISK_SHARED_SECRET is not set; Asterisk ingress endpoints are unauthenticated");
}
if (!process.env.CONTROL_API_SECRET) {
  warnings.push("CONTROL_API_SECRET is not set; control endpoints are unauthenticated");
}
if (process.env.OPENCLAW_BRIDGE_URL && !/^https?:\/\//.test(process.env.OPENCLAW_BRIDGE_URL)) {
  failures.push("OPENCLAW_BRIDGE_URL must be http(s) URL");
}
if (process.env.OPENCLAW_BRIDGE_TIMEOUT_MS) {
  const timeout = Number(process.env.OPENCLAW_BRIDGE_TIMEOUT_MS);
  if (!Number.isFinite(timeout) || timeout < 100) {
    failures.push("OPENCLAW_BRIDGE_TIMEOUT_MS must be a number >= 100");
  }
}

if (!optionalCloud.some((key) => Boolean(process.env[key])) && process.env.STUB_STT_TEXT === undefined) {
  warnings.push(
    "No STT provider key set and STUB_STT_TEXT unset; translation egress may stay empty in smoke checks",
  );
}

process.stdout.write("[deploy-preflight] Environment check\n");
for (const warning of warnings) {
  process.stdout.write(`[deploy-preflight] WARN ${warning}\n`);
}

if (failures.length > 0) {
  for (const failure of failures) {
    process.stderr.write(`[deploy-preflight] FAIL ${failure}\n`);
  }
  process.exit(1);
}

process.stdout.write("[deploy-preflight] PASS\n");
