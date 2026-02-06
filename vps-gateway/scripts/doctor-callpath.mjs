#!/usr/bin/env node

const baseUrl = (process.env.BASE_URL ?? "http://127.0.0.1:8080").replace(/\/+$/, "");
const sessionId = process.env.SESSION_ID ?? "";
const controlSecret = process.env.CONTROL_API_SECRET;

function headers() {
  if (!controlSecret) return {};
  return { "x-control-secret": controlSecret };
}

async function run() {
  process.stdout.write(`[doctor-callpath] base-url ${baseUrl}\n`);
  const sessionsResponse = await fetch(`${baseUrl}/sessions`, { headers: headers() });
  if (!sessionsResponse.ok) {
    throw new Error(`/sessions returned ${sessionsResponse.status}`);
  }
  const payload = await sessionsResponse.json();
  const sessions = Array.isArray(payload.sessions) ? payload.sessions : [];
  process.stdout.write(`[doctor-callpath] sessions=${sessions.length}\n`);

  const target =
    sessionId ||
    sessions.find((session) => session.state !== "ended")?.id ||
    sessions[sessions.length - 1]?.id;
  if (!target) {
    process.stdout.write("[doctor-callpath] no session selected\n");
    return;
  }

  const debugResponse = await fetch(`${baseUrl}/sessions/${encodeURIComponent(target)}/debug`, {
    headers: headers(),
  });
  if (!debugResponse.ok) {
    throw new Error(`/sessions/${target}/debug returned ${debugResponse.status}`);
  }
  const debug = await debugResponse.json();
  const metrics = debug.metrics ?? {};
  process.stdout.write(`[doctor-callpath] session=${target}\n`);
  process.stdout.write(
    `[doctor-callpath] state=${debug.session?.state ?? "unknown"} mode=${debug.session?.mode ?? "unknown"} lang=${debug.session?.sourceLanguage ?? "?"}->${debug.session?.targetLanguage ?? "?"}\n`,
  );
  process.stdout.write(
    `[doctor-callpath] latency_ms pipeline=${metrics.pipelineLatencyMs ?? "n/a"} stt=${metrics.sttLatencyMs ?? "n/a"} mt=${metrics.translationLatencyMs ?? "n/a"} tts=${metrics.ttsLatencyMs ?? "n/a"}\n`,
  );
  process.stdout.write(
    `[doctor-callpath] frames dropped=${metrics.droppedFrames ?? 0} passthrough=${metrics.passthroughFrames ?? 0} translated_chunks=${metrics.translatedChunks ?? 0}\n`,
  );
  process.stdout.write(
    `[doctor-callpath] egress queue_peak=${metrics.egressQueuePeak ?? 0} drop_count=${metrics.egressDropCount ?? 0}\n`,
  );
}

run().catch((error) => {
  process.stderr.write(
    `[doctor-callpath] FAIL ${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exit(1);
});
