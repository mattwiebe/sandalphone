# VPS Voice Gateway v1 (Twilio + VoIP.ms + Cloud APIs)

Date: 2026-01-31
Owner: Sandalphone
Scope: Always-on VPS voice gateway with SIP (VoIP.ms) + Twilio media streams, streaming STT/MT/TTS via cloud APIs, EN↔ES. Private translation mix injected into the outbound destination phone call leg by default; relay to vendor optional (v1.2+). Inbound calls auto-ring the destination phone number.

## Goals
- Stable, always-on call gateway on VPS.
- Inbound/outbound via VoIP.ms SIP + Twilio.
- Streaming translation with best accuracy (cloud APIs).
- Private translation mix on outbound destination phone call leg by default.
- Pluggable providers for STT/MT/TTS.

## Default Behavior (v1)
- Inbound calls to VoIP.ms or Twilio auto-ring the destination phone number.
- Translation is ON by default on the destination phone call leg.
- Prefer stereo split (original left, translation right) when available; fall back to mono mix.

## Non-Goals (v1)
- Local GPU inference.
- Persistent call recording (no storage by default).
- WhatsApp calling (v1.1).
- Full OpenClaw Canvas HUD (v1.2).

---

## Architecture Overview

### Components
- VPS (US West or TX):
  - Asterisk (SIP + RTP termination for VoIP.ms)
  - Voice Gateway service (TypeScript, HTTP + WS)
  - Audio Bus (TypeScript, mix/routing)
  - Streaming STT/MT/TTS adapters (TypeScript)
- Twilio: DID + Media Streams WebSocket
- VoIP.ms: DID -> SIP (VPS)
- Translation APIs:
  - STT: AssemblyAI Streaming
  - MT: Google Cloud Translation
  - TTS: Amazon Polly Standard

### Audio Graph
Inputs:
- SIP RTP from VoIP.ms (PCMU/PCMA 8k)
- Twilio Media Streams (mu-law 8k)
- Optional mic input (v1.1)

Outputs:
- Private mix (default): original + translated (destination phone call leg)
- Vendor mix: your live voice; translated TTS only when relay enabled (v1.2+)

Latency Target:
- <1s first translated audio for short phrases

---

## Network & Security

Ports (example):
- 5060/udp (SIP)
- 10000-20000/udp (RTP)
- 443/tcp (Gateway API + Twilio WS)

Notes:
- Use TLS/WSS for public endpoints.
- Restrict SIP IPs to VoIP.ms POP IPs when possible.

---

## Step-by-Step Build Checklist

### 0) VPS Provisioning
- Region: US West or TX.
- Instance: 4 vCPU / 8 GB RAM minimum.
- Install: Ubuntu LTS.
- DNS: provision A/AAAA for `voice.yourdomain.com`.

### Implementation Base (TypeScript)
- Runtime code lives in `/Users/matt/levi/vps-gateway`.
- Entry point: `/Users/matt/levi/vps-gateway/src/index.ts`.
- Dev run: `node dist/cli.js dev` (after `npm install` and `npm run build` in `/Users/matt/levi/vps-gateway`).
- Live endpoint smoke check: `node dist/cli.js smoke live --base-url https://voice.yourdomain.com`.
- VPS env sanity check: `node dist/cli.js doctor deploy`.
- Implemented and smoke-tested endpoints:
  - `GET /health`
  - `GET /sessions`
  - `POST /twilio/voice`
  - `POST /asterisk/inbound`
  - `POST /asterisk/media`
  - `POST /asterisk/end`
  - `GET /asterisk/egress/next`
  - `WS /twilio/stream`

### 1) Install Asterisk
- Install Asterisk + PJSIP modules.
- Open SIP + RTP ports.
- Configure basic dialplan for:
  - inbound SIP -> audio bus -> outbound destination phone leg
  - outbound SIP -> VoIP.ms

### 2) VoIP.ms SIP Trunk
- Create SIP account (subaccount) for VPS.
- Point DID routing to that SIP account.
- Set codecs: PCMU/PCMA.
- Reduce DID ring time (e.g., 5-10s).
- On inbound, Asterisk originates an outbound destination phone leg and injects private translation mix.

### 3) Twilio Media Streams
- Provision Twilio DID.
- Voice webhook -> `https://voice.yourdomain.com/twilio/voice`.
- Media Streams WS -> `wss://voice.yourdomain.com/twilio/stream`.
- On inbound, bridge to outbound destination phone leg and inject private translation mix.

### 4) Voice Gateway Service
- Outbound leg: auto-call destination phone on inbound (E.164 from config).
- HTTP endpoints:
  - /health
  - /twilio/voice (TwiML)
  - /twilio/stream (WS)
- SIP integration:
  - RTP -> Audio Bus
  - DTMF passthrough (optional)

### 5) Audio Bus (Core Logic)
- Normalize inputs to 16k PCM.
- VAD chunking for STT.
- Streaming STT -> MT -> TTS.
- Mix outputs:
  - Default: private mix on outbound destination phone call leg (stereo split when available)

### 6) Cloud API Adapters
- STT: AssemblyAI streaming (low-latency partials).
- MT: Google Cloud Translation (NMT).
- TTS: Amazon Polly Standard.

### 7) Monitoring
- Collect:
  - p50/p95 translation latency
  - call uptime + failures
  - audio levels
- Log call state transitions.

---

## Minimal Config Templates

### VoIP.ms (conceptual)
- DID routing: SIP account (VPS)
- Codec: PCMU/PCMA
- Ring time: 5-10 seconds

### Twilio (conceptual TwiML)
- Stream media to `wss://voice.yourdomain.com/twilio/stream`
- Call your phone leg on inbound

### destination phone Number (config)
- Store E.164 in config, e.g. `+52XXXXXXXXXX`.

---

## Acceptance Tests (v1)
- Inbound VoIP.ms call -> VPS auto-rings destination phone -> translated audio in call leg within <1s for short phrases.
- Inbound Twilio call -> Media Stream -> VPS auto-rings destination phone -> translated audio in call leg.

---

## v1.1 / v1.2
a) v1.1: WhatsApp calling ingress
b) v1.2: Multi-number routing + OpenClaw Canvas HUD

---

## Open Questions
- Asterisk dialplan design (single vs multi bridge).
- SIP security (IP allowlist, fail2ban).
- Whether to host SIP and WebSocket on same IP.
