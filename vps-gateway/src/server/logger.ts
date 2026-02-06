export type Logger = {
  debug: (msg: string, ctx?: Record<string, unknown>) => void;
  info: (msg: string, ctx?: Record<string, unknown>) => void;
  warn: (msg: string, ctx?: Record<string, unknown>) => void;
  error: (msg: string, ctx?: Record<string, unknown>) => void;
};

function serializeCtx(ctx?: Record<string, unknown>): string {
  if (!ctx || Object.keys(ctx).length === 0) return "";
  return ` ${JSON.stringify(ctx)}`;
}

export function makeLogger(level: "debug" | "info" | "warn" | "error"): Logger {
  const rank: Record<string, number> = { debug: 10, info: 20, warn: 30, error: 40 };

  function log(method: keyof Logger, msg: string, ctx?: Record<string, unknown>): void {
    if (rank[method] < rank[level]) return;
    const line = `[${new Date().toISOString()}] ${method.toUpperCase()} ${msg}${serializeCtx(ctx)}`;
    // Keep output simple for log shipping.
    process.stdout.write(`${line}\n`);
  }

  return {
    debug: (msg, ctx) => log("debug", msg, ctx),
    info: (msg, ctx) => log("info", msg, ctx),
    warn: (msg, ctx) => log("warn", msg, ctx),
    error: (msg, ctx) => log("error", msg, ctx),
  };
}
