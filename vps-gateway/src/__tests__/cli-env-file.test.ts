import assert from "node:assert/strict";
import test from "node:test";
import { applyEnvUpdates, parseEnvFile } from "../cli-env-file.js";

test("parseEnvFile reads plain and quoted values", () => {
  const parsed = parseEnvFile([
    "DESTINATION_PHONE_E164=+15555550100",
    'PUBLIC_BASE_URL="https://voice.example.com"',
    "# ignored",
  ].join("\n"));

  assert.equal(parsed.DESTINATION_PHONE_E164, "+15555550100");
  assert.equal(parsed.PUBLIC_BASE_URL, "https://voice.example.com");
});

test("applyEnvUpdates replaces existing keys and appends missing ones", () => {
  const out = applyEnvUpdates(
    ["DESTINATION_PHONE_E164=+111", "ASTERISK_SHARED_SECRET=old", ""].join("\n"),
    {
      DESTINATION_PHONE_E164: "+222",
      TWILIO_AUTH_TOKEN: "abc123",
    },
  );

  assert.equal(out.includes("DESTINATION_PHONE_E164=+222"), true);
  assert.equal(out.includes("ASTERISK_SHARED_SECRET=old"), true);
  assert.equal(out.includes("TWILIO_AUTH_TOKEN=abc123"), true);
});

test("applyEnvUpdates quotes values with spaces", () => {
  const out = applyEnvUpdates("PUBLIC_BASE_URL=", {
    PUBLIC_BASE_URL: "https://voice.example.com/path with space",
  });

  assert.equal(
    out,
    'PUBLIC_BASE_URL="https://voice.example.com/path with space"',
  );
});
