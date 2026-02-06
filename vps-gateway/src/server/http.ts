import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { URL } from "node:url";
import { WebSocketServer } from "ws";
import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { handleTwilioInbound } from "../ingress/twilio.js";
import {
  handleAsteriskInbound,
  mapAsteriskMediaToFrame,
  validateAsteriskInboundPayload,
  validateAsteriskMediaPayload,
} from "../ingress/asterisk.js";
import { wireTwilioMediaSocket } from "../ingress/twilio-media-stream.js";
import type { Logger } from "./logger.js";

async function readJsonBody(req: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function readFormBody(req: IncomingMessage): Promise<Record<string, string>> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  const raw = Buffer.concat(chunks).toString("utf8");
  const params = new URLSearchParams(raw);
  const out: Record<string, string> = {};
  for (const [key, value] of params.entries()) {
    out[key] = value;
  }
  return out;
}

function writeJson(res: ServerResponse, code: number, payload: unknown): void {
  res.statusCode = code;
  res.setHeader("content-type", "application/json");
  res.end(JSON.stringify(payload));
}

export function startHttpServer(
  port: number,
  logger: Logger,
  orchestrator: VoiceOrchestrator,
): void {
  const twilioWs = new WebSocketServer({ noServer: true });

  twilioWs.on("connection", (ws) => {
    wireTwilioMediaSocket(ws, orchestrator, logger);
  });

  const server = createServer(async (req, res) => {
    try {
      const method = req.method ?? "GET";
      const pathname = new URL(req.url ?? "/", "http://localhost").pathname;

      if (method === "GET" && pathname === "/health") {
        return writeJson(res, 200, { ok: true, service: "levi-vps-gateway" });
      }

      if (method === "GET" && pathname === "/sessions") {
        return writeJson(res, 200, { sessions: orchestrator.listSessions() });
      }

      if (method === "POST" && pathname === "/twilio/voice") {
        const body = await readFormBody(req);
        const result = handleTwilioInbound(orchestrator, body);
        res.statusCode = 200;
        res.setHeader("content-type", "application/xml");
        res.end(result.twiml);
        return;
      }

      if (method === "POST" && pathname === "/asterisk/inbound") {
        const payload = await readJsonBody(req);
        if (!validateAsteriskInboundPayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        const result = handleAsteriskInbound(orchestrator, payload);
        return writeJson(res, 200, result);
      }

      if (method === "POST" && pathname === "/asterisk/media") {
        const payload = await readJsonBody(req);
        if (!validateAsteriskMediaPayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        const frame = mapAsteriskMediaToFrame(orchestrator, payload);
        if (!frame) {
          return writeJson(res, 404, { error: "session_not_found" });
        }
        await orchestrator.onAudioFrame(frame);
        return writeJson(res, 202, { accepted: true, sessionId: frame.sessionId });
      }

      writeJson(res, 404, { error: "not_found" });
    } catch (error) {
      logger.error("request failed", {
        error: error instanceof Error ? error.message : String(error),
      });
      writeJson(res, 500, { error: "internal_error" });
    }
  });

  server.on("upgrade", (req, socket, head) => {
    const pathname = new URL(req.url ?? "/", "http://localhost").pathname;

    if (pathname !== "/twilio/stream") {
      socket.destroy();
      return;
    }

    twilioWs.handleUpgrade(req, socket, head, (ws) => {
      twilioWs.emit("connection", ws, req);
    });
  });

  server.listen(port, () => {
    logger.info("http server started", { port, twilioWsPath: "/twilio/stream" });
  });
}
