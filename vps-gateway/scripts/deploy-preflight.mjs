#!/usr/bin/env node

const required = ["DESTINATION_PHONE_E164"];
const optionalCloud = ["ASSEMBLYAI_API_KEY", "GOOGLE_TRANSLATE_API_KEY"];
const warnings = [];
const failures = [];

for (const key of required) {
  if (!process.env[key]) failures.push(`${key} is required`);
}

const destination phone = process.env.DESTINATION_PHONE_E164 ?? "";
if (destination phone && !/^\+[1-9]\d{7,14}$/.test(destination phone)) {
  failures.push("DESTINATION_PHONE_E164 must be E.164 format, e.g. +15555550100");
}

if (process.env.TWILIO_AUTH_TOKEN && !process.env.PUBLIC_BASE_URL) {
  warnings.push("PUBLIC_BASE_URL is recommended when TWILIO_AUTH_TOKEN is set");
}

if (!process.env.ASTERISK_SHARED_SECRET) {
  warnings.push("ASTERISK_SHARED_SECRET is not set; Asterisk ingress endpoints are unauthenticated");
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
