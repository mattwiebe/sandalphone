# Levi VPS Gateway (TypeScript)

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
2. Copy envs: `cp .env.example .env` and set values
2. Typecheck: `npm run check`
3. Build: `npm run build`
4. Test: `npm test`
5. Start dev server: `npm run dev`

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

## Current Endpoints
- `GET /health`
- `GET /sessions`
- `GET /metrics`
- `POST /twilio/voice` (form-encoded webhook)
- `POST /asterisk/inbound` (JSON bridge payload)
- `POST /asterisk/media` (JSON audio frame payload)
- `WS /twilio/stream` (Twilio media stream)

## Deploy (VPS)
1. Install Docker + Compose plugin on VPS.
2. Clone repo and move into `/Users/matt/levi/vps-gateway`.
3. Create env file:
   - `cp .env.example .env`
   - Set `DESTINATION_PHONE_E164` and cloud credentials.
4. Start service:
   - `npm run docker:up`
5. Verify:
   - `curl -sS http://localhost:8080/health`
6. Point providers to VPS:
   - Twilio voice webhook -> `POST /twilio/voice`
   - Twilio media stream websocket -> `WS /twilio/stream`
   - Asterisk bridge -> `POST /asterisk/inbound` and `POST /asterisk/media`

## Runtime Notes
- This scaffold is stateless in-memory; restart loses active sessions.
- `SIGINT` and `SIGTERM` are handled for clean service shutdown.
- Missing provider keys degrade to stubs (except Polly, enabled by default unless `DISABLE_POLLY=1`).

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

### Twilio Voice Contract
`POST /twilio/voice` expects Twilio form fields including `CallSid`, `From`, and `To`.
It returns TwiML that immediately dials the configured destination phone E.164 target.

## Env
- `PORT` (default `8080`)
- `DESTINATION_PHONE_E164` (default `+15555550100`)
- `LOG_LEVEL` (default `info`)
- `ASTERISK_SHARED_SECRET` (recommended on public VPS; required as `x-asterisk-secret` header for `/asterisk/inbound` and `/asterisk/media` when set)
- `PIPELINE_MIN_FRAME_INTERVAL_MS` (default `400`; throttles STT calls per session to control API churn)
- `ASSEMBLYAI_API_KEY` (enables realtime AssemblyAI STT)
- `ASSEMBLYAI_REALTIME_URL` (optional override for realtime WS URL)
- `GOOGLE_TRANSLATE_API_KEY` (enables Google Translate v2 REST provider)
- `AWS_REGION` (default `us-west-2`)
- `POLLY_VOICE_EN` (default `Joanna`)
- `POLLY_VOICE_ES` (default `Lupe`)
- `DISABLE_POLLY` (`1` forces local stub TTS provider)
