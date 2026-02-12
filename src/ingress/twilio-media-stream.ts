import type { WebSocket } from "ws";
import type { Logger } from "../server/logger.js";
import type { VoiceOrchestrator } from "../pipeline/orchestrator.js";
import type { AudioFrame } from "../domain/types.js";
import type { EgressStore } from "../pipeline/egress-store.js";

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
  egressStore: EgressStore,
): void {
  let sessionId: string | undefined;
  let callSid: string | undefined;
  let streamSid: string | undefined;
  let flushInFlight = false;

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
      streamSid = start?.streamSid;
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
      await flushTwilioEgress();
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

  async function flushTwilioEgress(): Promise<void> {
    if (!sessionId || !streamSid || flushInFlight) return;
    flushInFlight = true;
    try {
      while (true) {
        const session = orchestrator.getSession(sessionId);
        if (!session) return;
        if (session.mode !== "private_translation") {
          egressStore.clear(sessionId);
          return;
        }
        const chunk = egressStore.dequeue(sessionId);
        if (!chunk) return;
        const payload = mapTtsChunkToTwilioPayload(chunk.payload, chunk.encoding, chunk.sampleRateHz);
        if (!payload) {
          logger.warn("dropping tts chunk incompatible with twilio stream", {
            sessionId,
            callSid,
            encoding: chunk.encoding,
            sampleRateHz: chunk.sampleRateHz,
          });
          continue;
        }
        const outbound = {
          event: "media",
          streamSid,
          media: {
            payload: payload.toString("base64"),
          },
        };
        ws.send(JSON.stringify(outbound));
      }
    } finally {
      flushInFlight = false;
    }
  }
}

function mapTtsChunkToTwilioPayload(
  payload: Buffer,
  encoding: "pcm_s16le" | "mulaw",
  sampleRateHz: number,
): Buffer | undefined {
  if (encoding === "mulaw" && sampleRateHz === 8000) {
    return payload;
  }
  return undefined;
}
