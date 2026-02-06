import { createHash, randomUUID } from "node:crypto";
import type { SessionEvent } from "../domain/types.js";
import type { Logger } from "../server/logger.js";

export type OpenClawBridge = {
  publishSessionEvent: (event: SessionEvent) => Promise<void>;
  sendCommand: (command: string, context?: Record<string, unknown>) => Promise<void>;
  healthCheck: () => Promise<boolean>;
};

type OpenClawBridgeOptions = {
  readonly endpointUrl: string;
  readonly apiKey?: string;
  readonly timeoutMs: number;
  readonly logger: Logger;
  readonly maxAttempts?: number;
  readonly initialBackoffMs?: number;
  readonly maxBackoffMs?: number;
};

type OpenClawEnvelope = {
  readonly type: "session_event" | "command";
  readonly idempotencyKey: string;
  readonly atMs: number;
  readonly sessionEvent?: SessionEvent;
  readonly command?: {
    text: string;
    context?: Record<string, unknown>;
  };
};

type QueueItem = {
  envelope: OpenClawEnvelope;
  attempts: number;
  nextAttemptAtMs: number;
};

export function makeOpenClawBridge(opts: OpenClawBridgeOptions): OpenClawBridge {
  const queue: QueueItem[] = [];
  let draining = false;
  let retryTimer: NodeJS.Timeout | undefined;
  const maxAttempts = opts.maxAttempts ?? 4;
  const initialBackoffMs = opts.initialBackoffMs ?? 250;
  const maxBackoffMs = opts.maxBackoffMs ?? 2000;

  const enqueue = (envelope: OpenClawEnvelope): void => {
    queue.push({
      envelope,
      attempts: 0,
      nextAttemptAtMs: Date.now(),
    });
    scheduleDrain(0);
  };

  const scheduleDrain = (delayMs: number): void => {
    if (draining) return;
    if (retryTimer) clearTimeout(retryTimer);
    retryTimer = setTimeout(() => {
      retryTimer = undefined;
      void drainQueue();
    }, Math.max(delayMs, 0));
  };

  const drainQueue = async (): Promise<void> => {
    if (draining) return;
    draining = true;
    try {
      while (queue.length > 0) {
        const now = Date.now();
        const next = queue[0];
        if (!next) break;
        if (next.nextAttemptAtMs > now) {
          scheduleDrain(next.nextAttemptAtMs - now);
          return;
        }

        const delivered = await postEnvelope(opts, next.envelope);
        if (delivered) {
          queue.shift();
          continue;
        }

        next.attempts += 1;
        if (next.attempts >= maxAttempts) {
          opts.logger.warn("openclaw bridge dropping envelope after retries", {
            idempotencyKey: next.envelope.idempotencyKey,
            type: next.envelope.type,
            attempts: next.attempts,
          });
          queue.shift();
          continue;
        }

        const backoff = Math.min(initialBackoffMs * 2 ** (next.attempts - 1), maxBackoffMs);
        next.nextAttemptAtMs = Date.now() + backoff;
        scheduleDrain(backoff);
        return;
      }
    } finally {
      draining = false;
    }
  };

  return {
    publishSessionEvent: async (event) => {
      enqueue({
        type: "session_event",
        idempotencyKey: makeSessionEventIdempotencyKey(event),
        atMs: Date.now(),
        sessionEvent: event,
      });
    },
    sendCommand: async (command, context) => {
      enqueue({
        type: "command",
        idempotencyKey: `cmd:${randomUUID()}`,
        atMs: Date.now(),
        command: {
          text: command,
          context,
        },
      });
    },
    healthCheck: async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), opts.timeoutMs);
      try {
        const healthUrl = normalizeHealthUrl(opts.endpointUrl);
        const response = await fetch(healthUrl, {
          method: "GET",
          signal: controller.signal,
          headers: makeHeaders(opts.apiKey, "health-check"),
        });
        return response.ok;
      } catch {
        return false;
      } finally {
        clearTimeout(timer);
      }
    },
  };
}

async function postEnvelope(opts: OpenClawBridgeOptions, body: OpenClawEnvelope): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs);
  try {
    const response = await fetch(opts.endpointUrl, {
      method: "POST",
      signal: controller.signal,
      headers: makeHeaders(opts.apiKey, body.idempotencyKey),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      opts.logger.warn("openclaw bridge rejected envelope", {
        status: response.status,
        idempotencyKey: body.idempotencyKey,
      });
      return false;
    }
    return true;
  } catch (error) {
    opts.logger.warn("openclaw bridge request failed", {
      idempotencyKey: body.idempotencyKey,
      error: error instanceof Error ? error.message : String(error),
    });
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function makeHeaders(apiKey: string | undefined, idempotencyKey: string): Record<string, string> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "idempotency-key": idempotencyKey,
  };
  if (apiKey) {
    headers.authorization = `Bearer ${apiKey}`;
  }
  return headers;
}

function makeSessionEventIdempotencyKey(event: SessionEvent): string {
  const hash = createHash("sha1").update(JSON.stringify(event.payload)).digest("hex").slice(0, 12);
  return `evt:${event.type}:${event.sessionId}:${event.atMs}:${hash}`;
}

function normalizeHealthUrl(endpointUrl: string): string {
  const url = new URL(endpointUrl);
  return `${url.origin}/health`;
}
