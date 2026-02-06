import type { SessionEvent } from "../domain/types.js";
import type { Logger } from "../server/logger.js";

export type OpenClawBridge = {
  publishSessionEvent: (event: SessionEvent) => Promise<void>;
  sendCommand: (command: string, context?: Record<string, unknown>) => Promise<void>;
};

type OpenClawBridgeOptions = {
  readonly endpointUrl: string;
  readonly apiKey?: string;
  readonly timeoutMs: number;
  readonly logger: Logger;
};

type OpenClawEnvelope = {
  readonly type: "session_event" | "command";
  readonly atMs: number;
  readonly sessionEvent?: SessionEvent;
  readonly command?: {
    text: string;
    context?: Record<string, unknown>;
  };
};

export function makeOpenClawBridge(opts: OpenClawBridgeOptions): OpenClawBridge {
  return {
    publishSessionEvent: async (event) => {
      await postEnvelope(opts, {
        type: "session_event",
        atMs: Date.now(),
        sessionEvent: event,
      });
    },
    sendCommand: async (command, context) => {
      await postEnvelope(opts, {
        type: "command",
        atMs: Date.now(),
        command: {
          text: command,
          context,
        },
      });
    },
  };
}

async function postEnvelope(opts: OpenClawBridgeOptions, body: OpenClawEnvelope): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs);
  try {
    const response = await fetch(opts.endpointUrl, {
      method: "POST",
      signal: controller.signal,
      headers: makeHeaders(opts.apiKey),
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      opts.logger.warn("openclaw bridge rejected event", {
        status: response.status,
      });
    }
  } catch (error) {
    opts.logger.warn("openclaw bridge request failed", {
      error: error instanceof Error ? error.message : String(error),
    });
  } finally {
    clearTimeout(timer);
  }
}

function makeHeaders(apiKey?: string): Record<string, string> {
  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (apiKey) {
    headers.authorization = `Bearer ${apiKey}`;
  }
  return headers;
}
