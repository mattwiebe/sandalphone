import assert from "node:assert/strict";
import test from "node:test";
import { extractFunnelUrl } from "../cli-funnel.js";

test("extractFunnelUrl reads AllowFunnel host", () => {
  const input = JSON.stringify({
    AllowFunnel: {
      "mymac.tailnet.ts.net:443": true,
    },
  });

  assert.equal(extractFunnelUrl(input), "https://mymac.tailnet.ts.net");
});

test("extractFunnelUrl reads Web host when AllowFunnel missing", () => {
  const input = JSON.stringify({
    Web: {
      "foo.tailnet.ts.net:443": { Handlers: {} },
    },
  });

  assert.equal(extractFunnelUrl(input), "https://foo.tailnet.ts.net");
});

test("extractFunnelUrl falls back to scanning nested strings", () => {
  const input = JSON.stringify({
    nested: {
      note: "url=https://bar.tailnet.ts.net/path",
    },
  });

  assert.equal(extractFunnelUrl(input), "https://bar.tailnet.ts.net/path");
});

test("extractFunnelUrl returns undefined for invalid json", () => {
  assert.equal(extractFunnelUrl("not-json"), undefined);
});
