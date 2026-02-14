import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import type { Server } from "node:http";
import { URL } from "node:url";
import { WebSocketServer } from "ws";
import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import {
  buildTwimlForBridgeWithStream,
  buildTwimlForStream,
  buildTwimlSayAndHangup,
  handleTwilioInbound,
} from "../ingress/twilio.js";
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
    readonly twilioVoiceMode?: "dial" | "stream";
    readonly twilioStreamWsUrl?: string;
    readonly controlApiSecret?: string;
    readonly openClawBridge?: OpenClawBridge;
  },
): Server {
  const twilioWs = new WebSocketServer({ noServer: true });
  const inboundTestMode: {
    enabled: boolean;
    message: string;
    messageEs: string;
    activeCallSid?: string;
    lastEventId: number;
    recentEvents: InboundTestEvent[];
    completionTimer?: NodeJS.Timeout;
  } = {
    enabled: false,
    message: "Hello. Inbound test mode is active. This verifies inbound call handling.",
    messageEs:
      "Hola. El modo de prueba entrante esta activo. Esta llamada verifica la recepcion.",
    lastEventId: 0,
    recentEvents: [],
  };

  twilioWs.on("connection", (ws) => {
    wireTwilioMediaSocket(ws, orchestrator, logger, opts.egressStore);
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

      const debugMatch = pathname.match(/^\/sessions\/([^/]+)\/debug$/);
      if (method === "GET" && debugMatch) {
        const sessionId = decodeURIComponent(debugMatch[1] ?? "");
        const session = orchestrator.getSession(sessionId);
        if (!session) {
          return writeJson(res, 404, { error: "session_not_found" });
        }
        return writeJson(res, 200, {
          session,
          metrics: orchestrator.getMetrics(sessionId) ?? { sessionId },
        });
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
        if (updated.mode === "passthrough") {
          opts.egressStore.clear(updated.id);
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

      if (method === "GET" && pathname === "/test/inbound-mode") {
        if (!hasValidControlSecret(req, opts.controlApiSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const sinceEventIdRaw = url.searchParams.get("sinceEventId");
        const sinceEventId = sinceEventIdRaw ? Number(sinceEventIdRaw) : undefined;
        const recentEvents =
          sinceEventId !== undefined && Number.isFinite(sinceEventId)
            ? inboundTestMode.recentEvents.filter((event) => event.id > sinceEventId)
            : inboundTestMode.recentEvents;
        return writeJson(res, 200, {
          inboundTestMode: {
            enabled: inboundTestMode.enabled,
            message: inboundTestMode.message,
            messageEs: inboundTestMode.messageEs,
            activeCallSid: inboundTestMode.activeCallSid,
            lastEventId: inboundTestMode.lastEventId,
            recentEvents,
          },
        });
      }

      if (method === "POST" && pathname === "/test/inbound-mode") {
        if (!hasValidControlSecret(req, opts.controlApiSecret)) {
          return writeJson(res, 403, { error: "forbidden" });
        }
        const payload = await readJsonBody(req);
        if (!validateInboundTestModePayload(payload)) {
          return writeJson(res, 400, { error: "invalid_payload" });
        }
        inboundTestMode.enabled = payload.enabled;
        if (!payload.enabled) {
          inboundTestMode.activeCallSid = undefined;
          if (inboundTestMode.completionTimer) {
            clearTimeout(inboundTestMode.completionTimer);
            inboundTestMode.completionTimer = undefined;
          }
        }
        if (payload.message !== undefined) {
          inboundTestMode.message = payload.message;
        }
        if (payload.messageEs !== undefined) {
          inboundTestMode.messageEs = payload.messageEs;
        }
        logger.info("inbound test mode updated", {
          enabled: inboundTestMode.enabled,
          message: inboundTestMode.message,
          messageEs: inboundTestMode.messageEs,
        });
        return writeJson(res, 200, { inboundTestMode });
      }

      if (method === "POST" && pathname === "/twilio/voice") {
        const body = await readFormBody(req);
        if (!hasValidTwilioSignature(req, body, opts.twilioAuthToken, opts.publicBaseUrl)) {
          logger.warn("twilio signature rejected", {
            callSid: body.CallSid ?? "unknown",
            from: body.From ?? "unknown",
            to: body.To ?? "unknown",
            hasAuthToken: Boolean(opts.twilioAuthToken),
            hasPublicBaseUrl: Boolean(opts.publicBaseUrl),
          });
          return writeJson(res, 403, { error: "forbidden" });
        }
        if (inboundTestMode.enabled) {
          const callSid = body.CallSid ?? "unknown";
          inboundTestMode.activeCallSid = callSid;
          pushInboundTestEvent(inboundTestMode, {
            type: "incoming",
            callSid,
            from: body.From ?? "unknown",
            to: body.To ?? "unknown",
            atMs: Date.now(),
          });
          logger.info("twilio inbound received in inbound-test mode", {
            from: body.From ?? "unknown",
            to: body.To ?? "unknown",
            callSid,
          });
          if (inboundTestMode.completionTimer) {
            clearTimeout(inboundTestMode.completionTimer);
          }
          const completionDelayMs = estimateInboundTestCompletionDelayMs(inboundTestMode.message);
          inboundTestMode.completionTimer = setTimeout(() => {
            if (!inboundTestMode.enabled) return;
            inboundTestMode.activeCallSid = undefined;
            pushInboundTestEvent(inboundTestMode, {
              type: "completed",
              callSid,
              from: body.From ?? "unknown",
              to: body.To ?? "unknown",
              atMs: Date.now(),
            });
            inboundTestMode.completionTimer = undefined;
          }, completionDelayMs);
          res.statusCode = 200;
          res.setHeader("content-type", "application/xml");
          res.end(
            buildTwimlSayAndHangup([
              {
                text: inboundTestMode.message,
                language: "en-US",
              },
              {
                text: inboundTestMode.messageEs,
                language: "es-MX",
              },
            ]),
          );
          return;
        }
        const result = handleTwilioInbound(orchestrator, body);
        const voiceMode = opts.twilioVoiceMode ?? "dial";
        let twiml = result.twiml;
        if (voiceMode === "stream") {
          const session = orchestrator.getSession(result.sessionId);
          const from = body.From ?? "unknown";
          const streamEligible = session
            ? normalizePhoneForCompare(from) === normalizePhoneForCompare(session.targetPhoneE164)
            : false;
          const streamWsUrl = resolveTwilioStreamWsUrl(opts.twilioStreamWsUrl, opts.publicBaseUrl);
          if (streamEligible) {
            if (streamWsUrl) {
              twiml = buildTwimlForStream(streamWsUrl);
              logger.info("twilio stream mode engaged for trusted caller", {
                callSid: body.CallSid ?? "unknown",
                from,
                target: session?.targetPhoneE164 ?? "unknown",
              });
            } else {
              logger.warn("twilio stream mode requested without stream URL; falling back to dial", {
                callSid: body.CallSid ?? "unknown",
              });
            }
          } else {
            if (streamWsUrl && session?.targetPhoneE164) {
              twiml = buildTwimlForBridgeWithStream(
                session.targetPhoneE164,
                streamWsUrl,
              );
              logger.info("twilio stream fork engaged for untrusted caller (dial + stream)", {
                callSid: body.CallSid ?? "unknown",
                from,
                expectedFrom: session?.targetPhoneE164 ?? "unknown",
              });
            } else {
              logger.info("twilio stream mode skipped; missing stream URL or target for untrusted caller", {
                callSid: body.CallSid ?? "unknown",
                from,
                expectedFrom: session?.targetPhoneE164 ?? "unknown",
              });
            }
          }
        }
        res.statusCode = 200;
        res.setHeader("content-type", "application/xml");
        res.end(twiml);
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

type InboundTestModePayload = {
  enabled: boolean;
  message?: string;
  messageEs?: string;
};

type InboundTestEvent = {
  id: number;
  type: "incoming" | "completed";
  callSid: string;
  from: string;
  to: string;
  atMs: number;
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

function validateInboundTestModePayload(payload: unknown): payload is InboundTestModePayload {
  if (!payload || typeof payload !== "object") return false;
  const p = payload as Record<string, unknown>;
  if (typeof p.enabled !== "boolean") return false;
  if (p.message !== undefined && typeof p.message !== "string") return false;
  if (p.messageEs !== undefined && typeof p.messageEs !== "string") return false;
  return true;
}

function pushInboundTestEvent(
  state: {
    lastEventId: number;
    recentEvents: InboundTestEvent[];
  },
  event: Omit<InboundTestEvent, "id">,
): void {
  state.lastEventId += 1;
  state.recentEvents.push({
    id: state.lastEventId,
    ...event,
  });
  if (state.recentEvents.length > 32) {
    state.recentEvents = state.recentEvents.slice(-32);
  }
}

function estimateInboundTestCompletionDelayMs(message: string): number {
  // Coarse voice duration estimate so smoke mode can auto-exit after playback.
  const chars = Math.max(message.trim().length, 1);
  const speechMs = Math.ceil((chars / 13) * 1000);
  return Math.max(2500, speechMs + 1500);
}

function resolveTwilioStreamWsUrl(
  configuredWsUrl: string | undefined,
  publicBaseUrl: string | undefined,
): string | undefined {
  const explicit = configuredWsUrl?.trim();
  if (explicit) return explicit;
  const base = publicBaseUrl?.trim();
  if (!base) return undefined;
  if (/^https:\/\//.test(base)) {
    return `wss://${base.slice("https://".length).replace(/\/+$/, "")}/twilio/stream`;
  }
  if (/^http:\/\//.test(base)) {
    return `ws://${base.slice("http://".length).replace(/\/+$/, "")}/twilio/stream`;
  }
  return undefined;
}

function normalizePhoneForCompare(raw: string): string {
  return raw.replace(/\D/g, "");
}
