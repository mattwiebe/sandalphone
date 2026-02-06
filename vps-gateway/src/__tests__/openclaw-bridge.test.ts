import assert from "node:assert/strict";
import test from "node:test";
import { createServer } from "node:http";
import { once } from "node:events";
import type { AddressInfo } from "node:net";
import { makeLogger } from "../server/logger.js";
import { makeOpenClawBridge } from "../integrations/openclaw.js";

test("openclaw bridge posts session event and command envelopes", async () => {
  const received: Array<Record<string, unknown>> = [];
  const server = createServer(async (req, res) => {
    const chunks: Buffer[] = [];
    for await (const chunk of req) {
      chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
    }
    received.push(JSON.parse(Buffer.concat(chunks).toString("utf8")) as Record<string, unknown>);
    res.statusCode = 200;
    res.end('{"ok":true}');
  });
  server.listen(0);
  await once(server, "listening");
  const address = server.address() as AddressInfo;

  const bridge = makeOpenClawBridge({
    endpointUrl: `http://127.0.0.1:${address.port}/events`,
    apiKey: "token-123",
    timeoutMs: 500,
    logger: makeLogger("error"),
  });

  await bridge.publishSessionEvent({
    type: "session.started",
    sessionId: "s-1",
    atMs: Date.now(),
    payload: { source: "twilio" },
  });
  await bridge.sendCommand("summarize last vendor call", { sessionId: "s-1" });

  await new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) reject(error);
      else resolve(undefined);
    });
  });

  assert.equal(received.length, 2);
  assert.equal(received[0]?.type, "session_event");
  assert.equal(received[1]?.type, "command");
});
