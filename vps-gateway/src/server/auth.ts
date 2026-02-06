import type { IncomingMessage } from "node:http";
import { createHmac, timingSafeEqual } from "node:crypto";

export function hasValidAsteriskSecret(
  req: IncomingMessage,
  configuredSecret?: string,
): boolean {
  if (!configuredSecret) return true;
  const provided = req.headers["x-asterisk-secret"];
  return typeof provided === "string" && provided === configuredSecret;
}

export function hasValidTwilioSignature(
  req: IncomingMessage,
  formBody: Record<string, string>,
  authToken?: string,
  publicBaseUrl?: string,
): boolean {
  if (!authToken) return true;
  const signature = req.headers["x-twilio-signature"];
  if (typeof signature !== "string" || !req.url) return false;

  const url = buildPublicUrl(req.url, publicBaseUrl, req);
  const expected = computeTwilioSignature(url, formBody, authToken);
  return safeEqual(signature, expected);
}

function buildPublicUrl(
  requestPath: string,
  publicBaseUrl: string | undefined,
  req: IncomingMessage,
): string {
  if (publicBaseUrl) {
    return `${publicBaseUrl.replace(/\/$/, "")}${requestPath}`;
  }

  const host = req.headers.host ?? "localhost";
  return `http://${host}${requestPath}`;
}

export function computeTwilioSignature(
  url: string,
  formBody: Record<string, string>,
  authToken: string,
): string {
  const sortedKeys = Object.keys(formBody).sort();
  let payload = url;
  for (const key of sortedKeys) {
    payload += key + formBody[key];
  }

  return createHmac("sha1", authToken).update(payload).digest("base64");
}

function safeEqual(left: string, right: string): boolean {
  const leftBuf = Buffer.from(left);
  const rightBuf = Buffer.from(right);
  if (leftBuf.length !== rightBuf.length) return false;
  return timingSafeEqual(leftBuf, rightBuf);
}
