import assert from "node:assert/strict";
import test from "node:test";
import { extractFunnelUrl, extractFunnelUrlFromText } from "../cli-funnel.js";

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

test("extractFunnelUrlFromText parses https url", () => {
  assert.equal(
    extractFunnelUrlFromText("Serve URL: https://abc.tailnet.ts.net"),
    "https://abc.tailnet.ts.net",
  );
});

test("extractFunnelUrlFromText parses bare ts.net host", () => {
  assert.equal(
    extractFunnelUrlFromText("https endpoint host abc.tailnet.ts.net configured"),
    "https://abc.tailnet.ts.net",
  );
});
