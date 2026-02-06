import assert from "node:assert/strict";
import test from "node:test";
import type { IncomingMessage } from "node:http";
import { hasValidAsteriskSecret } from "../server/auth.js";

function makeReq(secretHeader?: string): IncomingMessage {
  return {
    headers: secretHeader ? { "x-asterisk-secret": secretHeader } : {},
  } as IncomingMessage;
}

test("hasValidAsteriskSecret allows when no secret configured", () => {
  assert.equal(hasValidAsteriskSecret(makeReq(), undefined), true);
});

test("hasValidAsteriskSecret rejects missing or wrong header", () => {
  assert.equal(hasValidAsteriskSecret(makeReq(), "topsecret"), false);
  assert.equal(hasValidAsteriskSecret(makeReq("wrong"), "topsecret"), false);
});

test("hasValidAsteriskSecret accepts matching header", () => {
  assert.equal(hasValidAsteriskSecret(makeReq("topsecret"), "topsecret"), true);
});
