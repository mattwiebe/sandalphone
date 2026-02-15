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
- Session control endpoint (`/sessions/control`)
- OpenClaw command relay (`/openclaw/command`)
- Provider factory with cloud/stub selection (Google Cloud STT + Translate + TTS)

## Run
1. Install deps: `npm install`
2. Build once: `npm run build`
3. Configure env interactively: `sandalphone install`
   - Installer can run Tailscale Funnel and auto-fill `PUBLIC_BASE_URL`.
4. Use CLI: `sandalphone help`
5. Typecheck: `sandalphone check`
6. Tests: `sandalphone test`
7. Start dev server: `sandalphone dev`

## VPS Install (Ubuntu 22.04 + Tailscale Funnel)
One-shot installer (runs as root, uses SSH repo clone):

```bash
curl -fsSL https://raw.githubusercontent.com/mattwiebe/sandalphone/main/scripts/install-vps.sh | sudo bash
```

Required env (pass as inline env vars to the command above):
- `TAILSCALE_AUTHKEY` (Tailscale auth key with reuse enabled)

The installer now shells into `node dist/cli.js install` and prompts you for
`OUTBOUND_TARGET_E164` and all other settings interactively.

If you do not have API keys yet, the installer prints a short guide with links to get them.

Example:

```bash
OUTBOUND_TARGET_E164=+15555550100 \
TAILSCALE_AUTHKEY=tskey-... \
TWILIO_AUTH_TOKEN=... \
GOOGLE_CLOUD_API_KEY=... \
curl -fsSL https://raw.githubusercontent.com/mattwiebe/sandalphone/main/scripts/install-vps.sh | sudo bash
```

Notes:
- The installer attempts `tailscale funnel --bg --yes 8080` and auto-detects the public URL.
- If Funnel is not enabled for the tailnet, enable it at https://login.tailscale.com/f/funnel then re-run.
- The systemd unit is installed as `sandalphone-vps-gateway`.

## CLI
Primary operator surface:

```bash
sandalphone help
```

If `sandalphone` is not found after build, use the local form:

```bash
node dist/cli.js <command>
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
sandalphone update
sandalphone update --test
sandalphone update --no-restart
sandalphone install
sandalphone --version
sandalphone funnel up --port 8080
sandalphone funnel status
sandalphone funnel reset --clear-env
sandalphone test
sandalphone test smoke
sandalphone test quick
sandalphone smoke live --base-url https://voice.yourdomain.com
sandalphone smoke twilio-stream
sandalphone smoke inbound --enable
sandalphone smoke inbound --status
sandalphone smoke inbound --disable
sandalphone smoke outbound --to +15551234567
sandalphone session passthrough --session-id <id>
sandalphone session translation on --session-id <id>
sandalphone session translation off --session-id <id>
sandalphone session translation toggle --session-id <id>
sandalphone session translation on --trusted
sandalphone session translation off --untrusted
sandalphone mode status
sandalphone mode translation on
sandalphone mode translation off
sandalphone mode translation toggle
sandalphone setup-asterisk
sandalphone session list
sandalphone session set --session-id <id> --mode passthrough
sandalphone session debug --session-id <id>
sandalphone urls
sandalphone openclaw command --command "start research project on vendor pricing"
sandalphone doctor deploy
sandalphone doctor local
sandalphone doctor callpath
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

If exactly one active session exists, session commands auto-select it and `--session-id` is optional.
Use `sandalphone mode translation on|off|toggle` to set the default for new calls when no session is active.
When mode is set to translation `on`, Sandalphone also auto-sets `TWILIO_VOICE_MODE=stream` for new calls.

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

### Inbound Leg-Only Test Mode
Enable inbound-only behavior for Twilio webhook: receive call, speak English + Spanish test strings, hang up, no forwarding.
`--enable` now stays attached, prints inbound events, waits for strict Twilio call completion, auto-disables test mode, then exits.

```bash
sandalphone smoke inbound --enable --message "Inbound test mode active."
# place a real call to your Twilio DID
sandalphone smoke inbound --status
sandalphone smoke inbound --disable
```

Optional flags:
- `--timeout 180000` max wait before auto-disable + exit failure
- `--no-watch` restore old behavior (enable and exit immediately)
- `--no-strict-completion` do not poll Twilio call status; rely on gateway completion event

### Outbound Leg-Only Test
Place a Twilio outbound call from your DID to your target and play English + Spanish prompt.

```bash
sandalphone smoke outbound --to +15551234567
```

If `--to` is omitted, it uses `OUTBOUND_TARGET_E164`. If that is missing, CLI prompts for destination interactively.

### Update Workflow
`sandalphone update` runs:
- `git pull --ff-only`
- dependency install (`npm ci` when lockfile exists)
- `npm run build`
- env migration checks (prompts to add missing required keys such as `TWILIO_VOICE_MODE`)
- env migration checks (prompts to add missing required keys such as `TWILIO_VOICE_MODE` and `DEFAULT_SESSION_MODE`)
- systemd restart on Linux when `sandalphone-vps-gateway.service` exists

Use `--no-restart` to skip service restart.

### Asterisk Setup Automation
Provision baseline Asterisk SIP ingress on Linux VPS:

```bash
sudo sandalphone setup-asterisk
```

This command:
- installs Asterisk (unless `--no-install`)
- writes managed `pjsip` + `extensions` include files
- opens SIP/RTP firewall rules via `ufw` (best-effort)
- restarts and reloads Asterisk
- infers and writes `TWILIO_UNTRUSTED_SIP_URI` using a public host/IP (avoids `.ts.net`); rerun with `--public-host` to force host selection
- defaults to `--mode bridge` (inbound SIP call answers and attempts to `Dial(...)` instead of test playback)

Bridge mode needs an outbound dial string. Set one of:
- `ASTERISK_OUTBOUND_DIAL_STRING` in `.env` (example: `PJSIP/+15555550100@twilio-out`)
- or pass `--bridge-dial-string ...` directly to `setup-asterisk`

Optional Twilio SIP endpoint generation in `pjsip_sandalphone.conf`:
- `TWILIO_SIP_TRUNK_HOST`
- `TWILIO_SIP_AUTH_USERNAME`
- `TWILIO_SIP_AUTH_PASSWORD`

Quick test mode is still available:

```bash
sudo sandalphone setup-asterisk --mode test
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

### Twilio Stream Mode
Use stream mode to feed Twilio audio into the translation pipeline:

- Set `TWILIO_VOICE_MODE=stream`
- Set `PUBLIC_BASE_URL=https://...` **or** `TWILIO_STREAM_WS_URL=wss://.../twilio/stream`
- Keep `TWILIO_VOICE_MODE=dial` as fallback until stream path is fully validated
- In stream mode:
  - calls from `OUTBOUND_TARGET_E164` engage `<Connect><Stream>` (controller path)
  - all other callers use `<Start><Stream>` + `<Dial>` (forward + stream fork)
  - set `TWILIO_UNTRUSTED_SIP_URI=sip:...` to hand untrusted callers to your SIP/Asterisk bridge instead

Validate stream TwiML quickly:

```bash
sandalphone smoke twilio-stream
```

Live translation toggle during an active call:

```bash
sandalphone session passthrough --session-id <id>
sandalphone session translation on --session-id <id>
sandalphone session translation off --session-id <id>
sandalphone session translation toggle --session-id <id>
```

## Current Endpoints
- `GET /health`
- `GET /sessions/:sessionId/debug`
- `POST /sessions/control` (mode/language updates)
- `POST /openclaw/command` (relay instructions to configured OpenClaw bridge)
- `GET /test/inbound-mode` (show inbound test mode)
- `POST /test/inbound-mode` (enable/disable inbound test mode)
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
2. Clone repo and move into `/Users/matt/levi`.
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
- Missing Google Cloud API key degrades to stub providers.
- For local E2E testing without cloud keys, set `STUB_STT_TEXT`.
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
When inbound test mode is enabled, it instead returns TwiML `<Say>` + `<Hangup/>` and does not forward.

### Session Control Contract
`POST /sessions/control`

```json
{
  "sessionId": "uuid",
  "mode": "passthrough"
}
```

Alternative locator:

```json
{
  "callId": "sip-123",
  "source": "voipms",
  "mode": "private_translation"
}
```

### OpenClaw Command Contract
`POST /openclaw/command`

```json
{
  "command": "research supplier options for Guadalajara logistics",
  "source": "twilio"
}
```

## Env
- `PORT` (default `8080`)
- `OUTBOUND_TARGET_E164` (default `+15555550100`)
- `DEFAULT_SESSION_MODE` (`private_translation` or `passthrough`; default `private_translation`)
- `TWILIO_ACCOUNT_SID` (required for `sandalphone smoke outbound`)
- `TWILIO_PHONE_NUMBER` (optional metadata for your Twilio DID)
- `VOIPMS_DID` (optional metadata for your VoIP.ms DID)
- `LOG_LEVEL` (default `info`)
- `ASTERISK_SHARED_SECRET` (recommended on public VPS; required as `x-asterisk-secret` header for `/asterisk/inbound` and `/asterisk/media` when set)
- `CONTROL_API_SECRET` (recommended; required as `x-control-secret` header for `/sessions/control` and `/openclaw/command` when set)
- `PIPELINE_MIN_FRAME_INTERVAL_MS` (default `400`; throttles STT calls per session to control API churn)
- `EGRESS_MAX_QUEUE_PER_SESSION` (default `64`; bounds queued translated chunks per call)
- `GOOGLE_CLOUD_API_KEY` (enables Google Cloud STT + Translate + TTS)
- `GOOGLE_TTS_VOICE_EN` (default `en-US-Standard-C`)
- `GOOGLE_TTS_VOICE_ES` (default `es-US-Standard-A`)
- `STUB_STT_TEXT` (optional text emitted by stub STT provider for local e2e validation)
- `TWILIO_AUTH_TOKEN` (optional; enables Twilio signature validation)
- `PUBLIC_BASE_URL` (optional override for signature URL, e.g. `https://voice.yourdomain.com`)
- `TWILIO_VOICE_MODE` (`dial` or `stream`; default `dial`)
- `TWILIO_STREAM_WS_URL` (optional explicit stream websocket URL; when empty derives from `PUBLIC_BASE_URL` as `/twilio/stream`)
- `TWILIO_UNTRUSTED_SIP_URI` (optional SIP URI for untrusted inbound handoff when stream mode is enabled)
- `ASTERISK_OUTBOUND_DIAL_STRING` (Asterisk bridge dial target; default pattern `PJSIP/<OUTBOUND_TARGET_E164>@twilio-out`)
- `TWILIO_SIP_TRUNK_HOST` (optional Twilio SIP trunk host used by `setup-asterisk` to build `twilio-out`)
- `TWILIO_SIP_AUTH_USERNAME` (optional SIP auth user; defaults to `TWILIO_ACCOUNT_SID` when missing)
- `TWILIO_SIP_AUTH_PASSWORD` (optional SIP auth password; defaults to `TWILIO_AUTH_TOKEN` when missing)
- `OPENCLAW_BRIDGE_URL` (optional HTTP endpoint for call/session events and command relay)
- `OPENCLAW_BRIDGE_API_KEY` (optional bearer token for bridge endpoint)
- `OPENCLAW_BRIDGE_TIMEOUT_MS` (default `1200`)
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

## Local Readiness Check
Before live call tests on macOS:

```bash
sandalphone doctor local
```

Checks:
- `.env` presence and required target phone format
- `PUBLIC_BASE_URL` HTTPS validity
- Tailscale CLI/funnel status visibility

## Callpath Doctor
Quickly inspect a live/recent call and quality metrics:

```bash
sandalphone doctor callpath
sandalphone doctor callpath --session-id <session-id>
```

Includes:
- mode/language state
- latency snapshot (STT/MT/TTS/pipeline)
- dropped frame and passthrough counters
- egress queue peak + drop count

## Twilio URL Output
Print exact URLs to paste in Twilio console:

```bash
sandalphone urls
# or override explicitly
sandalphone urls --base-url https://your-funnel-host.ts.net
```

## OpenClaw Command Relay
If `OPENCLAW_BRIDGE_URL` is configured:

```bash
sandalphone openclaw command --command "queue research task for bilingual vendor shortlist"
```

Optional targeting:

```bash
sandalphone openclaw command \
  --command "summarize current call and propose next questions" \
  --session-id <session-id> \
  --source twilio
```
