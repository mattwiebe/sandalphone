import type { IncomingMessage } from "node:http";

export function hasValidAsteriskSecret(
  req: IncomingMessage,
  configuredSecret?: string,
): boolean {
  if (!configuredSecret) return true;
  const provided = req.headers["x-asterisk-secret"];
  return typeof provided === "string" && provided === configuredSecret;
}
