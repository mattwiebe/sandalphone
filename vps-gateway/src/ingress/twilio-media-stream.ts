import type { WebSocket } from "ws";
import type { Logger } from "../server/logger.js";
import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import type { AudioFrame } from "../domain/types.js";

type TwilioEventBase = {
  event: "connected" | "start" | "media" | "stop";
  streamSid?: string;
};

type TwilioStartEvent = TwilioEventBase & {
  event: "start";
  start?: {
    callSid?: string;
    streamSid?: string;
  };
};

type TwilioMediaEvent = TwilioEventBase & {
  event: "media";
  media?: {
    payload?: string;
    timestamp?: string;
  };
};

type TwilioStopEvent = TwilioEventBase & {
  event: "stop";
};

type TwilioStreamMessage = TwilioEventBase | TwilioStartEvent | TwilioMediaEvent | TwilioStopEvent;

function parseMessage(raw: Buffer): TwilioStreamMessage | null {
  try {
    return JSON.parse(raw.toString("utf8")) as TwilioStreamMessage;
  } catch {
    return null;
  }
}

export function wireTwilioMediaSocket(
  ws: WebSocket,
  orchestrator: VoiceOrchestrator,
  logger: Logger,
): void {
  let sessionId: string | undefined;
  let callSid: string | undefined;

  ws.on("message", async (raw) => {
    if (!Buffer.isBuffer(raw)) {
      return;
    }

    const msg = parseMessage(raw);
    if (!msg) {
      logger.warn("twilio stream malformed payload");
      return;
    }

    if (msg.event === "start") {
      const start = (msg as TwilioStartEvent).start;
      callSid = start?.callSid;
      if (!callSid) {
        logger.warn("twilio start without callSid");
        return;
      }
      sessionId = orchestrator.resolveSessionIdByExternal("twilio", callSid);
      if (!sessionId) {
        logger.warn("twilio stream missing mapped session", { callSid });
      }
      return;
    }

    if (msg.event === "media") {
      if (!sessionId || !callSid) {
        return;
      }
      const media = (msg as TwilioMediaEvent).media;
      if (!media?.payload) {
        return;
      }
      const payload = Buffer.from(media.payload, "base64");
      const frame: AudioFrame = {
        sessionId,
        source: "twilio",
        sampleRateHz: 8000,
        encoding: "mulaw",
        timestampMs: Number(media.timestamp ?? Date.now()),
        payload,
      };
      await orchestrator.onAudioFrame(frame);
      return;
    }

    if (msg.event === "stop") {
      if (sessionId) {
        orchestrator.endSession(sessionId);
      }
    }
  });

  ws.on("error", (err) => {
    logger.warn("twilio media ws error", { error: err.message, callSid });
  });

  ws.on("close", () => {
    if (sessionId) {
      orchestrator.endSession(sessionId);
    }
  });
}
