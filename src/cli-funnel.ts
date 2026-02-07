export function extractFunnelUrl(statusJson: string): string | undefined {
  let parsed: unknown;
  try {
    parsed = JSON.parse(statusJson);
  } catch {
    return undefined;
  }

  const fromKnown = extractFromKnownFields(parsed);
  if (fromKnown) return fromKnown;

  const scanned = scanForHttpsUrl(parsed);
  return scanned;
}

export function extractFunnelUrlFromText(text: string): string | undefined {
  const https = text.match(/https:\/\/[^\s"']+/)?.[0];
  if (https) return https;

  // Common host forms in `tailscale funnel status` output.
  const host =
    text.match(/\b([a-zA-Z0-9.-]+\.ts\.net)\b/)?.[1] ??
    text.match(/\b([a-zA-Z0-9.-]+\.tailscale\.net)\b/)?.[1];
  if (host) return `https://${host}`;

  return undefined;
}

function extractFromKnownFields(input: unknown): string | undefined {
  if (!input || typeof input !== "object") return undefined;
  const obj = input as Record<string, unknown>;

  const allowFunnel = obj.AllowFunnel;
  if (allowFunnel && typeof allowFunnel === "object") {
    for (const [hostPort, enabled] of Object.entries(allowFunnel as Record<string, unknown>)) {
      if (enabled === true) {
        const host = hostPort.split(":")[0];
        if (host) return `https://${host}`;
      }
    }
  }

  const web = obj.Web;
  if (web && typeof web === "object") {
    const firstHostPort = Object.keys(web as Record<string, unknown>)[0];
    if (firstHostPort) {
      const host = firstHostPort.split(":")[0];
      if (host) return `https://${host}`;
    }
  }

  return undefined;
}

function scanForHttpsUrl(input: unknown): string | undefined {
  if (typeof input === "string") {
    const match = input.match(/https:\/\/[^\s"']+/);
    return match?.[0];
  }

  if (!input || typeof input !== "object") return undefined;

  if (Array.isArray(input)) {
    for (const item of input) {
      const found = scanForHttpsUrl(item);
      if (found) return found;
    }
    return undefined;
  }

  for (const value of Object.values(input as Record<string, unknown>)) {
    const found = scanForHttpsUrl(value);
    if (found) return found;
  }

  return undefined;
}
