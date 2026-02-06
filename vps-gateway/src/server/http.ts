import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { Server } from "node:http";
import { URL } from "node:url";
import { WebSocketServer } from "ws";
import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import { handleTwilioInbound } from "../ingress/twilio.js";
import {
  handleAsteriskInbound,
  mapAsteriskMediaToFrame,
  resolveAsteriskEndSessionId,
  validateAsteriskEndPayload,
  validateAsteriskInboundPayload,
  validateAsteriskMediaPayload,
} from "../ingress/asterisk.js";
import { wireTwilioMediaSocket } from "../ingress/twilio-media-stream.js";
import { hasValidAsteriskSecret, hasValidControlSecret, hasValidTwilioSignature } from "./auth.js";
import type { Logger } from "./logger.js";
import type { EgressStore } from "../pipeline/egress-store.js";
import type { IngressSource, LanguageCode, SessionMode } from "../domain/types.js";
import type { OpenClawBridge } from "../integrations/openclaw.js";

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
  opts: {
    readonly asteriskSharedSecret?: string;
    readonly egressStore: EgressStore;
    readonly twilioAuthToken?: string;
    readonly publicBaseUrl?: string;
    readonly controlApiSecret?: string;
    readonly openClawBridge?: OpenClawBridge;
  },
): Server {
  const twilioWs = new WebSocketServer({ noServer: true });

  twilioWs.on("connection", (ws) => {
    wireTwilioMediaSocket(ws, orchestrator, logger);
  });

  const server = createServer(async (req, res) => {
    try {
      const method = req.method ?? "GET";
      const url = new URL(req.url ?? "/", "http://localhost");
      const pathname = url.pathname;

      if (method === "GET" && pathname === "/health") {
        return writeJson(res, 200, { ok: true, service: "sandalphone-vps-gateway" });
      }

      if (method === "GET" && pathname === "/sessions") {
        return writeJson(res, 200, { sessions: orchestrator.listSessions() });
      }

      if (method === "GET" && pathname === "/metrics") {
        return writeJson(res, 200, { metrics: orchestrator.listMetrics() });
      }

      if (method === "POST" && pathname === "/sessions/control") {
        if (!hasValidControlSecret(req, opts.controlApiSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const payload = await readJsonBody(req);
        if (!validateSessionControlPayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        const sessionId =
          payload.sessionId ??
          (payload.callId
            ? orchestrator.resolveSessionIdByExternal(payload.source ?? "voipms", payload.callId)
            : undefined);
        if (!sessionId) {
          return writeJson(res, 404, { error: "session_not_found" });
        }
        const updated = orchestrator.updateSessionControl(sessionId, {
          mode: payload.mode,
          sourceLanguage: payload.sourceLanguage,
          targetLanguage: payload.targetLanguage,
        });
        if (!updated) {
          return writeJson(res, 404, { error: "session_not_found" });
        }
        return writeJson(res, 200, { session: updated });
      }

      if (method === "POST" && pathname === "/openclaw/command") {
        if (!hasValidControlSecret(req, opts.controlApiSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const payload = await readJsonBody(req);
        if (!validateOpenClawCommandPayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        if (!opts.openClawBridge) {
          return writeJson(res, 503, { error: "openclaw_bridge_not_configured" });
        }
        await opts.openClawBridge.sendCommand(payload.command, {
          sessionId: payload.sessionId,
          callId: payload.callId,
          source: payload.source,
          issuedAtMs: Date.now(),
        });
        return writeJson(res, 202, { accepted: true });
      }

      if (method === "POST" && pathname === "/twilio/voice") {
        const body = await readFormBody(req);
        if (!hasValidTwilioSignature(req, body, opts.twilioAuthToken, opts.publicBaseUrl)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const result = handleTwilioInbound(orchestrator, body);
        res.statusCode = 200;
        res.setHeader("content-type", "application/xml");
        res.end(result.twiml);
        return;
      }

      if (method === "POST" && pathname === "/asterisk/inbound") {
        if (!hasValidAsteriskSecret(req, opts.asteriskSharedSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const payload = await readJsonBody(req);
        if (!validateAsteriskInboundPayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        const result = handleAsteriskInbound(orchestrator, payload);
        return writeJson(res, 200, result);
      }

      if (method === "POST" && pathname === "/asterisk/media") {
        if (!hasValidAsteriskSecret(req, opts.asteriskSharedSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
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

      if (method === "POST" && pathname === "/asterisk/end") {
        if (!hasValidAsteriskSecret(req, opts.asteriskSharedSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const payload = await readJsonBody(req);
        if (!validateAsteriskEndPayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        const sessionId = resolveAsteriskEndSessionId(orchestrator, payload);
        if (!sessionId) {
          return writeJson(res, 404, { error: "session_not_found" });
        }
        orchestrator.endSession(sessionId);
        opts.egressStore.clear(sessionId);
        return writeJson(res, 200, { ended: true, sessionId });
      }

      if (method === "GET" && pathname === "/asterisk/egress/next") {
        if (!hasValidAsteriskSecret(req, opts.asteriskSharedSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }

        const requestedSessionId = url.searchParams.get("sessionId");
        const callId = url.searchParams.get("callId");
        const source = url.searchParams.get("source") ?? "voipms";
        const sessionId =
          requestedSessionId ??
          (callId ? orchestrator.resolveSessionIdByExternal(source, callId) : undefined);
        if (!sessionId) {
          return writeJson(res, 404, { error: "session_not_found" });
        }

        const next = opts.egressStore.dequeue(sessionId);
        if (!next) {
          res.statusCode = 204;
          res.end();
          return;
        }

        return writeJson(res, 200, {
          sessionId,
          encoding: next.encoding,
          sampleRateHz: next.sampleRateHz,
          timestampMs: next.timestampMs,
          payloadBase64: next.payload.toString("base64"),
          remainingQueue: opts.egressStore.size(sessionId),
        });
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

  return server;
}

type SessionControlPayload = {
  sessionId?: string;
  callId?: string;
  source?: IngressSource;
  mode?: SessionMode;
  sourceLanguage?: LanguageCode;
  targetLanguage?: LanguageCode;
};

type OpenClawCommandPayload = {
  command: string;
  sessionId?: string;
  callId?: string;
  source?: IngressSource;
};

function validateSessionControlPayload(payload: unknown): payload is SessionControlPayload {
  if (!payload || typeof payload !== "object") return false;
  const p = payload as Record<string, unknown>;
  const hasLocator = typeof p.sessionId === "string" || typeof p.callId === "string";
  const hasPatch =
    p.mode !== undefined || p.sourceLanguage !== undefined || p.targetLanguage !== undefined;
  const sourceOk = p.source === undefined || p.source === "voipms" || p.source === "twilio";
  const modeOk =
    p.mode === undefined || p.mode === "private_translation" || p.mode === "passthrough";
  const sourceLanguageOk =
    p.sourceLanguage === undefined || p.sourceLanguage === "en" || p.sourceLanguage === "es";
  const targetLanguageOk =
    p.targetLanguage === undefined || p.targetLanguage === "en" || p.targetLanguage === "es";

  return hasLocator && hasPatch && sourceOk && modeOk && sourceLanguageOk && targetLanguageOk;
}

function validateOpenClawCommandPayload(payload: unknown): payload is OpenClawCommandPayload {
  if (!payload || typeof payload !== "object") return false;
  const p = payload as Record<string, unknown>;
  const sourceOk = p.source === undefined || p.source === "voipms" || p.source === "twilio";
  return typeof p.command === "string" && p.command.trim().length > 0 && sourceOk;
}
