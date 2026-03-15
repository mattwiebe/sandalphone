# LiveKit + Twilio Cutover

## Goal

Get to a real private-leg live call flow with:

- Twilio DID as the public phone number
- LiveKit Cloud as SIP/media plane
- Hetzner as the runtime/control plane
- trusted leg on a LiveKit client
- translated audio published only to the trusted participant

## Current State

- old Node gateway removed from Hetzner
- new runtime service deployed as `levi-runtime-cloud.service`
- new runtime app listening on port `8787`
- service root path: `/opt/levi-runtime-cloud`
- Twilio Elastic SIP trunk created: `levi-main`
- Twilio DID attached: `+523223080230`
- LiveKit inbound trunk created: `levi-main-inbound`
- LiveKit outbound trunk created: `levi-main-outbound`
- LiveKit dispatch rule sends inbound calls to room: `call-main`

## Recommended First Working Path

1. Use LiveKit Cloud.
2. Use Twilio Elastic SIP Trunking for the DID.
3. Use Google Cloud STT / Translation / TTS as the first cheap baseline.
4. Use a trusted LiveKit web/mobile client for the private translation leg.

## Required Credentials

### LiveKit Cloud

- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`

### Twilio

- Account SID
- Auth Token
- Twilio phone number / DID
- outbound termination username/password

### Google Cloud baseline

- STT credentials
- Translation credentials
- TTS credentials

## Hetzner Service

Edit:

```bash
ssh hetzner 'sudo nano /opt/levi-runtime-cloud/.env'
```

Then restart:

```bash
ssh hetzner 'sudo systemctl restart levi-runtime-cloud.service'
ssh hetzner 'systemctl status levi-runtime-cloud.service --no-pager'
ssh hetzner 'curl -s http://127.0.0.1:8787/health'
```

## Provisioning Command

From [`runtime-cloud`](/Users/matt/levi/runtime-cloud):

```bash
TWILIO_ACCOUNT_SID=... \
TWILIO_AUTH_TOKEN=... \
TWILIO_PHONE_NUMBER=+15551234567 \
TWILIO_TRUNK_STEM=levi-main \
LIVEKIT_URL=wss://your-project.livekit.cloud \
LIVEKIT_API_KEY=... \
LIVEKIT_API_SECRET=... \
LIVEKIT_ROOM_NAME=call-main \
uv run python -m runtime_cloud_service.provision
```

This provisions or reuses:

- the Twilio Elastic SIP trunk
- the Twilio origination URI pointing at LiveKit SIP
- the DID attachment to the Twilio trunk
- a Twilio credential list for outbound termination
- the LiveKit inbound trunk
- the LiveKit outbound trunk
- the LiveKit SIP dispatch rule

## Trusted Leg Token Endpoint

Current endpoint:

- `POST /tokens/trusted`

Payload:

```json
{
  "room_name": "call-123",
  "identity": "trusted-user-1",
  "name": "Matt"
}
```

## Twilio / LiveKit Build Order

1. Create Twilio Elastic SIP trunk.
2. Create LiveKit inbound trunk.
3. Create LiveKit outbound trunk.
4. Add dispatch rule to send inbound DID calls into a room.
5. Mint trusted participant token from Hetzner.
6. Join trusted participant from browser/phone.
7. Join Pipecat bot runtime to the same room.
8. Verify translated track is private to trusted participant.

## Acceptance Test

1. Call the Twilio DID from a second phone.
2. Join the trusted leg from LiveKit client.
3. Verify caller audio appears in room.
4. Verify translated audio is audible only to trusted participant.
5. Verify caller does not hear translated audio.
