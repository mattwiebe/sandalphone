import assert from "node:assert/strict";
import test from "node:test";
import { loadConfig } from "../config.js";

test("loadConfig prefers OUTBOUND_TARGET_E164", () => {
  const config = loadConfig({
    OUTBOUND_TARGET_E164: "+15550000001",
    DESTINATION_PHONE_E164: "+15550000002",
  });

  assert.equal(config.outboundTargetE164, "+15550000001");
});

test("loadConfig falls back to legacy DESTINATION_PHONE_E164", () => {
  const config = loadConfig({
    DESTINATION_PHONE_E164: "+15550000003",
  });

  assert.equal(config.outboundTargetE164, "+15550000003");
});
