#!/usr/bin/env node

const baseUrl = (process.env.BASE_URL ?? "http://127.0.0.1:8080").replace(/\/$/, "");
const asteriskSecret = process.env.ASTERISK_SHARED_SECRET;
const controlSecret = process.env.CONTROL_API_SECRET;
const strictEgress = process.env.STRICT_EGRESS === "1";
const source = process.env.SMOKE_SOURCE ?? "voipms";
const callId = process.env.SMOKE_CALL_ID ?? `sip-live-${Date.now()}`;

function log(step, detail) {
  const suffix = detail ? ` ${detail}` : "";
  process.stdout.write(`[smoke-live] ${step}${suffix}\n`);
}

function fail(step, detail) {
  process.stderr.write(`[smoke-live] FAIL ${step}${detail ? `: ${detail}` : ""}\n`);
  process.exitCode = 1;
}

async function expectJson(response, step) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${step} returned non-JSON payload: ${text.slice(0, 200)}`);
  }
}

function asteriskHeaders() {
  const headers = { "content-type": "application/json" };
  if (asteriskSecret) {
    headers["x-asterisk-secret"] = asteriskSecret;
  }
  return headers;
}

async function run() {
  log("base-url", baseUrl);

  const health = await fetch(`${baseUrl}/health`);
  if (!health.ok) throw new Error(`/health returned ${health.status}`);
  const healthPayload = await expectJson(health, "/health");
  if (healthPayload.ok !== true) throw new Error("/health did not return ok=true");
  log("health", "ok");

  const twilio = await fetch(`${baseUrl}/twilio/voice`, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: "CallSid=CA_LIVE_SMOKE&From=%2B15551234567&To=%2B18005550199",
  });
  if (!twilio.ok) throw new Error(`/twilio/voice returned ${twilio.status}`);
  const twiml = await twilio.text();
  if (!twiml.includes("<Dial>")) throw new Error("/twilio/voice did not return TwiML Dial response");
  log("twilio-voice", "ok");

  const inbound = await fetch(`${baseUrl}/asterisk/inbound`, {
    method: "POST",
    headers: asteriskHeaders(),
    body: JSON.stringify({
      callId,
      from: "+15550000001",
      to: "+18005550199",
    }),
  });
  if (!inbound.ok) {
    if (inbound.status === 403 && !asteriskSecret) {
      throw new Error("/asterisk/inbound forbidden; set ASTERISK_SHARED_SECRET for smoke:live");
    }
    throw new Error(`/asterisk/inbound returned ${inbound.status}`);
  }
  const inboundPayload = await expectJson(inbound, "/asterisk/inbound");
  const sessionId = inboundPayload.sessionId;
  if (typeof sessionId !== "string") throw new Error("/asterisk/inbound missing sessionId");
  log("asterisk-inbound", `session=${sessionId}`);

  if (controlSecret) {
    const control = await fetch(`${baseUrl}/sessions/control`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-control-secret": controlSecret,
      },
      body: JSON.stringify({
        sessionId,
        mode: "private_translation",
      }),
    });
    if (!control.ok) throw new Error(`/sessions/control returned ${control.status}`);
    log("session-control", "ok");
  }

  const media = await fetch(`${baseUrl}/asterisk/media`, {
    method: "POST",
    headers: asteriskHeaders(),
    body: JSON.stringify({
      callId,
      sampleRateHz: 8000,
      encoding: "mulaw",
      payloadBase64: "AQI=",
    }),
  });
  if (media.status !== 202) throw new Error(`/asterisk/media returned ${media.status}`);
  log("asterisk-media", "accepted");

  const egress = await fetch(
    `${baseUrl}/asterisk/egress/next?callId=${encodeURIComponent(callId)}&source=${encodeURIComponent(source)}`,
    {
      headers: asteriskSecret ? { "x-asterisk-secret": asteriskSecret } : {},
    },
  );

  if (egress.status === 200) {
    const egressPayload = await expectJson(egress, "/asterisk/egress/next");
    if (typeof egressPayload.payloadBase64 !== "string") {
      throw new Error("/asterisk/egress/next missing payloadBase64");
    }
    log("asterisk-egress", "chunk=200");
  } else if (egress.status === 204) {
    if (strictEgress) {
      throw new Error("/asterisk/egress/next returned 204 with STRICT_EGRESS=1");
    }
    log("asterisk-egress", "empty=204 (allowed)");
  } else {
    throw new Error(`/asterisk/egress/next returned ${egress.status}`);
  }

  const end = await fetch(`${baseUrl}/asterisk/end`, {
    method: "POST",
    headers: asteriskHeaders(),
    body: JSON.stringify({
      callId,
      source,
    }),
  });
  if (!end.ok) throw new Error(`/asterisk/end returned ${end.status}`);
  log("asterisk-end", "ok");

  const sessions = await fetch(`${baseUrl}/sessions`);
  if (!sessions.ok) throw new Error(`/sessions returned ${sessions.status}`);
  const sessionsPayload = await expectJson(sessions, "/sessions");
  const ended = (sessionsPayload.sessions ?? []).find((session) => session.id === sessionId);
  if (!ended || ended.state !== "ended") {
    throw new Error(`/sessions did not show ended state for ${sessionId}`);
  }
  log("sessions", `ended=${sessionId}`);

  log("result", "PASS");
}

run().catch((error) => {
  fail("smoke-live", error instanceof Error ? error.message : String(error));
});
