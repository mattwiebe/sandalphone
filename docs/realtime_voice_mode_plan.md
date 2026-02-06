# Realtime Voice Mode Plan (v1: Twilio + WhatsApp)

Date: 2026-01-31
Owner: Levi
Scope: Integrate realtime voice translation with OpenClaw nodes (iOS + macOS). v1 supports Twilio (voice-call plugin) and WhatsApp (macOS loopback capture). Target translation latency ~2s. HUD/UI deferred.

## Goals
- Centralize call control and audio routing on macOS.
- Provide a control plane via OpenClaw Canvas/A2UI (iOS + macOS nodes).
- Keep translation private by default; allow relay to vendor only when explicitly enabled.
- Support Twilio and WhatsApp in v1.

## Non-Goals (v1)
- Full Watch app UI (notifications and actions only).
- Native WhatsApp call APIs (use macOS automation + loopback audio).
- Perfect per-speaker diarization.

## Architecture Overview

### Components
- Gateway (OpenClaw): routes node events and exposes canvas host.
- iOS Node (OpenClaw): Canvas + A2UI actions, voice wake/talk mode for commands.
- macOS Node (OpenClaw): Canvas + system automation permissions.
- Audio Bus (Levi, macOS): central capture, translation, mix, and injection.
- Translation Pipeline (Levi): mac/ws/stream and cloud realtime pipeline.

### Audio Graph (v1)
- Inputs:
  - Twilio call audio (OpenClaw voice-call media stream).
  - WhatsApp call audio (macOS loopback capture).
  - Mic audio (self-translation).
- Processing:
  - VAD buffering -> STT -> MT -> TTS (reuse existing pipeline).
- Outputs:
  - Private mix (headphones): original speaker + translated audio (stereo split).
  - Vendor leg mix: your mic (always), translated TTS (relay mode only).

## Control Bus (Gateway <-> Audio Bus)

### Envelope
All messages are JSON objects:
```
{
  "type": "call.pending",
  "ts": 1738330625,
  "source": "twilio",
  "payload": { ... }
}
```
Fields:
- type: command or event name
- ts: unix epoch seconds (or ms)
- source: twilio | whatsapp | system | user | bus
- payload: type-specific object

### Commands (Gateway -> Audio Bus)
Call lifecycle:
- call.answer
- call.stall
- call.voicemail
- call.ghost
- call.hangup

Mode control:
- mode.set (tutor | relay)
- relay.set (true | false)
- translator.set (source_lang, target_lang)

Source routing:
- source.enable (twilio | whatsapp | mic)
- source.bridge (source -> privileged line)

Mixing:
- mix.set (private/vender mix targets)
- mix.duck (duck original during translation)

Example:
```
{ "type": "mode.set", "source": "user", "payload": { "mode": "tutor" } }
```

### Events (Audio Bus -> Gateway/UI)
Call events:
- call.pending
- call.active
- call.ended
- call.failed

Translation:
- translation.latency
- translation.state (idle | working | error)

Routing/levels:
- mix.state
- source.state

Example:
```
{
  "type": "translation.latency",
  "source": "bus",
  "payload": { "callId": "twilio:CA123", "p50_ms": 1400, "p95_ms": 2100 }
}
```

### A2UI Action Mapping
Canvas actions (A2UI) are mapped to control bus commands by the Gateway.
Example user action from canvas:
```
openclawSendUserAction({
  name: "call.answer",
  surfaceId: "main",
  sourceComponentId: "hud.answer",
  context: { callId: "twilio:CA123" }
});
```
Gateway sends:
```
{ "type": "call.answer", "payload": { "callId": "twilio:CA123" } }
```

## Twilio Integration (v1)
- Use OpenClaw voice-call plugin media streams for ingress (mu-law 8k) and optional egress.
- Feed Twilio audio into translation pipeline; inject translated TTS only when relay is enabled.

## WhatsApp Integration (v1)
- Capture audio via macOS loopback device.
- Use macOS automation (Hammerspoon/AppleScript) for answer/decline.
- Default: private mix only; bridge into privileged line only with explicit toggle.

## Latency Target (2s)
- Use streaming translation endpoint (mac/ws/stream).
- Keep VAD buffer ~0.5s; stream chunks at ~2s.
- Emit translation.latency telemetry per call.

## Implementation Milestones
- M0: Control bus schema + message router stub.
- M1: Twilio media stream -> translation -> private mix.
- M2: WhatsApp capture -> translation -> private mix.
- M3: Relay toggle -> vendor leg injection.
- M4: HUD Canvas + presets (deferred).

## Open Questions
- Exact audio bus implementation language (Python vs TS).
- WhatsApp capture method (Loopback vs BlackHole).
- Where to host control bus server (Levi mac app vs gateway plugin).


## Sequence Diagram (v1 call flow)
```
Participant: Vendor (PSTN)
Participant: Twilio
Participant: OpenClaw Gateway
Participant: Audio Bus (macOS)
Participant: Translation Pipeline (Levi)
Participant: User (Headphones)

Vendor -> Twilio: inbound call to BIZ
Twilio -> OpenClaw Gateway: voice-call webhook + media stream WS
OpenClaw Gateway -> Audio Bus: call.pending (source=twilio)
User -> OpenClaw Gateway: call.answer (via A2UI action)
OpenClaw Gateway -> Audio Bus: call.answer
Audio Bus -> Twilio: accept stream (ingress)
Audio Bus -> Translation Pipeline: audio chunks (VAD -> STT/MT/TTS)
Translation Pipeline -> Audio Bus: translated audio chunks
Audio Bus -> User (Headphones): private mix (original + translation)

[Optional Relay]
User -> OpenClaw Gateway: relay.set true
OpenClaw Gateway -> Audio Bus: relay.set true
Audio Bus -> Twilio: inject translated TTS to vendor leg
```

## State Machine (call handling)

States:
- idle
- pending
- active
- stalled
- voicemail
- ghost
- ended

Events:
- call.pending
- call.answer
- call.stall
- call.voicemail
- call.ghost
- call.hangup
- call.failed
- call.ended

Transitions:
- idle --call.pending--> pending
- pending --call.answer--> active
- pending --call.stall--> stalled
- pending --call.voicemail--> voicemail
- pending --call.ghost--> ghost
- stalled --call.answer--> active
- stalled --call.hangup--> ended
- active --call.hangup--> ended
- active --call.failed--> ended
- voicemail --call.ended--> ended
- ghost --call.ended--> ended
- any --call.failed--> ended
