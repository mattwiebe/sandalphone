# Sandalphone VPS Gateway (TypeScript)

TypeScript-first runtime for the VPS architecture:
- Inbound call ingress (VoIP.ms via Asterisk bridge, Twilio webhook/stream)
- Streaming STT -> translation -> TTS orchestration
- Default behavior: inbound calls ring destination phone leg with private translation mix

## Status
Runnable gateway with:
- Session lifecycle tracking
- Twilio voice webhook handling (`/twilio/voice`)
- Twilio media stream websocket upgrade path (`/twilio/stream`)
- Asterisk inbound bridge endpoint (`/asterisk/inbound`)
- Asterisk media ingestion endpoint (`/asterisk/media`)
- Provider factory with cloud/stub selection (AssemblyAI realtime, Google Translate v2, Polly Standard)

## Run
1. Install deps: `npm install`
2. Build once: `npm run build`
3. Configure env interactively: `sandalphone install`
   - Installer can run Tailscale Funnel and auto-fill `PUBLIC_BASE_URL`.
4. Use CLI: `sandalphone help`
5. Typecheck: `sandalphone check`
6. Tests: `sandalphone test`
7. Start dev server: `sandalphone dev`

## CLI
Primary operator surface:

```bash
sandalphone help
```

If `sandalphone` is not found after build:

```bash
cd /Users/matt/levi/vps-gateway
npm link
```

Equivalent local invocation (no global link needed):

```bash
node dist/cli.js help
node dist/cli.js install
node dist/cli.js --version
```

Core commands:

```bash
sandalphone build
sandalphone check
sandalphone install
sandalphone --version
sandalphone funnel up --port 8080
sandalphone funnel status
sandalphone funnel reset --clear-env
sandalphone test
sandalphone test smoke
sandalphone test quick
sandalphone smoke live --base-url https://voice.yourdomain.com
sandalphone doctor deploy
sandalphone service print-unit
sandalphone service print-launchd
sandalphone service install-launchd
sandalphone service launchd-load
sandalphone service launchd-status
sandalphone service launchd-logs --lines 200
sandalphone service launchd-unload
sandalphone service status
sandalphone service logs --lines 200
```

## Smoke Test
With server running on port `8080`:

```bash
curl -sS http://localhost:8080/health
curl -sS -X POST http://localhost:8080/twilio/voice \
  -H 'content-type: application/x-www-form-urlencoded' \
  --data 'CallSid=CA123&From=%2B15551234567&To=%2B18005550199'
curl -sS -X POST http://localhost:8080/asterisk/inbound \
  -H 'content-type: application/json' \
  -d '{"callId":"sip-1","from":"+15550000001","to":"+18005550199"}'
curl -sS -X POST http://localhost:8080/asterisk/media \
  -H 'content-type: application/json' \
  -d '{"callId":"sip-1","sampleRateHz":8000,"encoding":"mulaw","payloadBase64":"AQI="}'
curl -sS http://localhost:8080/sessions
```

### Live Smoke Command
Run against a running gateway (local or VPS):

```bash
sandalphone smoke live --base-url http://127.0.0.1:8080
```

When Asterisk secret is enabled:

```bash
sandalphone smoke live \
  --base-url https://voice.yourdomain.com \
  --secret your-secret
```

Fail if egress has no chunk (`204`):

```bash
sandalphone smoke live --strict-egress
```

### Tailscale Funnel Commands
Manage local public ingress from CLI:

```bash
sandalphone funnel up --port 8080
sandalphone funnel status
sandalphone funnel reset --clear-env
```

`sandalphone funnel up` writes detected URL into `.env` as `PUBLIC_BASE_URL`.
If auto-detection fails, run `tailscale funnel status`, copy the `https://...` host, and paste it into `PUBLIC_BASE_URL`.

## Current Endpoints
- `GET /health`
- `GET /sessions`
- `GET /metrics`
- `POST /twilio/voice` (form-encoded webhook)
- `POST /asterisk/inbound` (JSON bridge payload)
- `POST /asterisk/media` (JSON audio frame payload)
- `POST /asterisk/end` (mark session ended and clear egress buffer)
- `GET /asterisk/egress/next` (poll next translated audio chunk)
- `WS /twilio/stream` (Twilio media stream)

## Deploy (VPS)
1. Install Node.js 22+ on VPS.
2. Clone repo and move into `/Users/matt/levi/vps-gateway`.
3. Create env file:
   - Run `sandalphone install`
   - Run `sandalphone doctor deploy`
4. Install and enable systemd service:
   - `sandalphone service print-unit`
   - `sudo sandalphone service install-unit`
   - `sudo sandalphone service reload`
   - `sudo sandalphone service enable`
   - `sudo sandalphone service restart`
5. Verify:
   - `sandalphone smoke live --base-url http://127.0.0.1:8080`
6. Point providers to VPS:
   - Twilio voice webhook -> `POST /twilio/voice`
   - Twilio media stream websocket -> `WS /twilio/stream`
   - Asterisk bridge -> `POST /asterisk/inbound` and `POST /asterisk/media`

### Deployment Templates
- `deploy/systemd/sandalphone-vps-gateway.service` for non-container systemd deployments
- `deploy/nginx/voice-gateway.conf` reverse-proxy baseline (includes WebSocket upgrade headers)

## Runtime Notes
- This scaffold is stateless in-memory; restart loses active sessions.
- `SIGINT` and `SIGTERM` are handled for clean service shutdown.
- Missing provider keys degrade to stubs (except Polly, enabled by default unless `DISABLE_POLLY=1`).
- For local E2E testing without cloud keys, set `STUB_STT_TEXT` and `DISABLE_POLLY=1`.
- If `TWILIO_AUTH_TOKEN` is set, `/twilio/voice` enforces `X-Twilio-Signature`.

## Integration Contracts
### Asterisk Inbound Contract
`POST /asterisk/inbound`

```json
{
  "callId": "sip-123",
  "from": "+15550000001",
  "to": "+18005550199"
}
```

Response:

```json
{
  "sessionId": "uuid",
  "dialTarget": "+15555550100"
}
```

### Asterisk Media Contract
`POST /asterisk/media`

```json
{
  "callId": "sip-123",
  "sampleRateHz": 8000,
  "encoding": "mulaw",
  "payloadBase64": "AQI=",
  "timestampMs": 1736337000000
}
```

Response:

```json
{
  "accepted": true,
  "sessionId": "uuid"
}
```

### Asterisk Egress Contract
`GET /asterisk/egress/next?callId=sip-123&source=voipms`

- Requires `x-asterisk-secret` when `ASTERISK_SHARED_SECRET` is configured.
- Returns `204` when no translated audio is queued yet.

Response (`200`):

```json
{
  "sessionId": "uuid",
  "encoding": "pcm_s16le",
  "sampleRateHz": 16000,
  "timestampMs": 1736337000100,
  "payloadBase64": "AQI=",
  "remainingQueue": 0
}
```

### Asterisk End Contract
`POST /asterisk/end`

```json
{
  "callId": "sip-123",
  "source": "voipms"
}
```

Alternative payload:

```json
{
  "sessionId": "uuid"
}
```

### Twilio Voice Contract
`POST /twilio/voice` expects Twilio form fields including `CallSid`, `From`, and `To`.
It returns TwiML that immediately dials the configured outbound target phone E.164.

## Env
- `PORT` (default `8080`)
- `OUTBOUND_TARGET_E164` (default `+15555550100`)
- `DESTINATION_PHONE_E164` (legacy fallback only; migrate to `OUTBOUND_TARGET_E164`)
- `TWILIO_PHONE_NUMBER` (optional metadata for your Twilio DID)
- `VOIPMS_DID` (optional metadata for your VoIP.ms DID)
- `LOG_LEVEL` (default `info`)
- `ASTERISK_SHARED_SECRET` (recommended on public VPS; required as `x-asterisk-secret` header for `/asterisk/inbound` and `/asterisk/media` when set)
- `PIPELINE_MIN_FRAME_INTERVAL_MS` (default `400`; throttles STT calls per session to control API churn)
- `EGRESS_MAX_QUEUE_PER_SESSION` (default `64`; bounds queued translated chunks per call)
- `ASSEMBLYAI_API_KEY` (enables realtime AssemblyAI STT)
- `ASSEMBLYAI_REALTIME_URL` (optional override for realtime WS URL)
- `GOOGLE_TRANSLATE_API_KEY` (enables Google Translate v2 REST provider)
- `AWS_REGION` (default `us-west-2`)
- `POLLY_VOICE_EN` (default `Joanna`)
- `POLLY_VOICE_ES` (default `Lupe`)
- `DISABLE_POLLY` (`1` forces local stub TTS provider)
- `STUB_STT_TEXT` (optional text emitted by stub STT provider for local e2e validation)
- `TWILIO_AUTH_TOKEN` (optional; enables Twilio signature validation)
- `PUBLIC_BASE_URL` (optional override for signature URL, e.g. `https://voice.yourdomain.com`)
To write to a non-default env file:

```bash
sandalphone install --env-path /path/to/.env
```

## macOS Background Service (launchd)
Run as a user agent on macOS without Docker:

```bash
sandalphone service install-launchd
sandalphone service launchd-load
sandalphone service launchd-status
sandalphone service launchd-logs --lines 200
```

Defaults:
- Label: `com.sandalphone.vps-gateway`
- Plist path: `~/Library/LaunchAgents/com.sandalphone.vps-gateway.plist`
- Logs: `/tmp/sandalphone-vps-gateway.out.log`, `/tmp/sandalphone-vps-gateway.err.log`

Override example:

```bash
sandalphone service install-launchd \
  --label com.sandalphone.gateway.dev \
  --env-path .env \
  --stdout-log /tmp/sandalphone-dev.out.log \
  --stderr-log /tmp/sandalphone-dev.err.log
```
