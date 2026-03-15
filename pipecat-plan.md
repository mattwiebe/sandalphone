# Pipecat Pivot Plan

Date: 2026-03-14
Owner: Matt Wiebe
Status: Draft for execution

## Purpose

This project is pivoting from custom call/session orchestration toward battle-tested runtime components:

- `Pipecat` becomes the realtime orchestration layer.
- `LiveKit` becomes the media plane and SIP edge.
- the existing `mac/` inference stack stays in play initially as a backend capability, not as the system orchestrator.
- the current custom telephony/control code is treated as transitional and should be retired phase by phase.

The immediate product remains the same:

- inbound and outbound phone calls
- private English/Spanish live translation
- modular STT / MT / TTS backends
- ambient voice mode as the next mode on the same core runtime
- assistant/event hooks designed in early, even if richer agent behavior ships later

## Non-Negotiable Delivery Rule

Every phase begins by adding or updating tests for the behavior being introduced.

Every phase ends only when the phase test suite is passing.

No phase is considered complete because code exists, services boot, or a manual demo kind of works. The exit condition is green tests plus the explicit phase acceptance criteria.

## Target Architecture

### Runtime

- `Pipecat bot/service` runs the session logic, audio branching, control events, and translation flow.
- `LiveKit` handles rooms, participant identity, SIP ingress/egress, and track publication/subscription.
- `Mac inference backend` continues to provide STT / translation / TTS early on, behind a stable adapter boundary.
- `Telegram` is optional transitional ingress/control only if it does not distort the target architecture.

### Core call model

Inbound:

1. PSTN call arrives through SIP trunk into LiveKit.
2. LiveKit places caller into a room.
3. Trusted participant joins via app/WebRTC.
4. Pipecat joins the room, subscribes to the caller track, runs translation, and publishes translated audio only to the trusted participant.

Outbound:

1. Trusted participant initiates an outbound call request.
2. LiveKit dials the PSTN leg through the configured SIP provider.
3. Pipecat uses the same room model and translation pipeline as inbound.

### Design constraints

- SIP provider must remain swappable.
- Private translation is the default.
- Translation providers must sit behind interfaces.
- Room/session state must be recoverable and observable.
- ambient mode must reuse the same session and pipeline abstractions rather than fork a separate architecture.
- event contracts for transcripts, session lifecycle, and assistant/task hooks should be typed early so later product expansion does not require re-plumbing the runtime.
- We do not deepen investment in bespoke websocket/media glue unless it directly supports the Pipecat/LiveKit target.

### Deployment decision

- `LiveKit Cloud` is the default for v1.
- self-hosting LiveKit is out of scope for the current 2 GB Hetzner footprint and should not shape early implementation.

## Repo Direction

### Keep and adapt

- [`/Users/matt/levi/mac/src`](/Users/matt/levi/mac/src) as inference services and adapters
- [`/Users/matt/levi/mac/tests`](/Users/matt/levi/mac/tests) as the seed of a real automated test suite
- [`/Users/matt/levi/cloud/src`](/Users/matt/levi/cloud/src) where transitional orchestration exists today

### Stop extending as core architecture

- custom call lifecycle orchestration in cloud code
- custom websocket protocol as the long-term media/control contract
- provider-specific call flow logic embedded directly into business logic

### Likely new structure

- `pipecat_app/` or `cloud/src/pipecat_app/` for Pipecat runtime code
- `shared/` for protocol/config/domain models if needed
- `shared/events/` or equivalent for typed session/transcript/task envelopes
- `tests/contract/` for adapter and protocol tests
- `tests/integration/` for room/session/call-flow tests

## Phase Template

Every phase follows this exact shape:

1. Write or update tests that describe the target behavior and fail for the right reason.
2. Implement the minimum code to satisfy that phase.
3. Run the phase test suite until green.
4. Capture the resulting contract changes in docs/config examples.

Recommended command pattern:

```bash
uv run --extra dev pytest
```

Use narrower commands inside a phase while iterating, but the phase closes only when its defined suite passes.

When a phase touches the existing Mac inference code or tests under `mac/`, include the `mac` extra as well.

## Phase 0: Test Harness and Architectural Baseline

### Goal

Create a reliable test baseline before introducing Pipecat/LiveKit code.

### Start with tests

- normalize existing tests so they can run unattended
- replace print-heavy scripts masquerading as tests with actual assertions
- add smoke tests for current translation adapters and websocket boundaries
- add fixture strategy for fake audio, fake backend responses, and deterministic config

### Implementation

- make `pytest` the standard runner
- separate real integration tests from hardware/model-dependent tests
- mark tests by level: `unit`, `contract`, `integration`, `hardware`
- define stable test entrypoints in repo docs or config

### Exit criteria

- a documented test matrix exists
- current automated tests run in CI/local without manual setup beyond declared extras
- existing red tests are either fixed or explicitly quarantined with rationale

### Phase close command

```bash
uv run --extra dev pytest
```

## Phase 1: Adapter Boundary Around Existing Inference Stack

### Goal

Turn the current Mac backend into a clean service boundary Pipecat can call without caring about implementation details.

### Start with tests

- contract tests for STT / translation / TTS adapter interfaces
- request/response tests for the existing websocket or replacement local transport
- failure-mode tests: timeout, invalid audio, empty transcript, backend unavailable
- contract tests for typed event envelopes such as `session.started`, `session.ended`, `transcript.partial`, `transcript.final`, and assistant-facing task events

### Implementation

- define explicit adapter interfaces for `SpeechToText`, `Translator`, and `SpeechSynthesizer`
- wrap current `mac/src` services behind those interfaces
- remove orchestration assumptions from adapter code
- add structured result objects instead of loose dicts where practical
- define typed event envelopes early, even if some are initially emitted by stubs

### Exit criteria

- Pipecat-facing code can invoke a single stable translation service boundary
- backend failures produce typed, test-covered errors
- no new orchestration logic leaks into `mac/src`
- core event contracts exist for session, transcript, and assistant/task integration points

### Phase close command

```bash
uv run --extra dev --extra mac pytest mac/tests tests/contract
```

## Phase 2: Pipecat Skeleton Without Telephony

### Goal

Stand up a Pipecat runtime that can process room audio and publish translated audio without SIP complexity.

### Start with tests

- unit tests for Pipecat pipeline construction
- contract tests for inbound audio frame -> translated output frame behavior
- tests for private-track routing decisions
- tests for session state transitions independent of LiveKit networking
- tests that the same runtime abstractions can support both call mode and ambient mode inputs

### Implementation

- introduce the Pipecat app module
- wire Pipecat processors to the adapter boundary from Phase 1
- model session state explicitly: `idle`, `connecting`, `active`, `degraded`, `ended`
- build the first private-translation pipeline for one caller and one trusted listener
- keep source/input abstraction broad enough for telephony audio now and ambient microphone audio next

### Exit criteria

- a local non-SIP test harness can feed audio into Pipecat and receive translated output
- the pipeline is modular enough to swap providers without editing orchestration logic
- private routing logic is encoded in tests, not just comments
- ambient mode does not require inventing a second pipeline architecture

### Phase close command

```bash
uv run --extra dev pytest tests/unit tests/contract tests/integration -k pipecat
```

## Phase 3: LiveKit Room Integration

### Goal

Replace bespoke media/session handling with LiveKit room semantics.

### Start with tests

- room participant mapping tests
- track subscription/publication policy tests
- tests that translated audio is only published to the trusted participant by default
- reconnection/state recovery tests at the session layer

### Implementation

- add LiveKit transport integration to the Pipecat runtime
- map caller/trusted/bot roles to explicit room identities
- centralize publication and subscription permissions
- add metrics and logs around join, publish, subscribe, and failure paths

### Exit criteria

- a trusted participant and caller can join the same room model in tests
- Pipecat consumes caller audio from LiveKit and publishes translated audio correctly
- custom media routing outside LiveKit is no longer required for the core path

### Phase close command

```bash
uv run --extra dev pytest tests/integration -k livekit
```

## Phase 4: Inbound SIP

### Goal

Support inbound DID calls through LiveKit SIP with provider-agnostic configuration.

### Start with tests

- config parsing tests for SIP trunk/provider selection
- inbound call session creation tests
- tests for mapping SIP metadata into domain session objects
- tests for default privacy behavior on inbound calls

### Implementation

- configure inbound SIP trunk support via LiveKit
- implement provider-neutral config for at least one initial trunk
- map inbound calls onto room/session creation
- keep provider-specific code at the edge only

### Exit criteria

- an inbound call can create a room/session and start the translation pipeline
- swapping trunk credentials/config does not require orchestration code changes
- inbound call handling is primarily LiveKit + Pipecat, not custom glue

### Phase close command

```bash
uv run --extra dev pytest tests/contract tests/integration -k inbound
```

## Phase 5: Outbound SIP

### Goal

Support outbound translated calls with the same room/session architecture.

### Start with tests

- outbound dial request validation tests
- session creation tests for trusted-first and callee-first flows
- tests for cancellation, busy, no-answer, and early hangup
- regression tests ensuring outbound and inbound share the same session model

### Implementation

- add outbound call orchestration through LiveKit SIP
- ensure one common session lifecycle for inbound and outbound
- expose a clean command surface for initiating outbound calls

### Exit criteria

- outbound dialing works through the same architecture as inbound
- no separate bespoke outbound runtime is introduced
- failure states are observable and test-covered

### Phase close command

```bash
uv run --extra dev pytest tests/contract tests/integration -k outbound
```

## Phase 6: Audio Policy and User Experience

### Goal

Ship the privacy and listening behavior that actually makes the product usable.

### Start with tests

- tests for private translation default
- tests for optional relay mode
- tests for ducking or stereo policy decisions
- tests for mode switching without tearing down the session incorrectly

### Implementation

- add explicit audio policy module
- implement private mix behavior first
- add optional relay mode only after private mode is stable
- add ducking/stereo handling behind testable policy decisions

### Exit criteria

- private mode is the default and enforced by tests
- relay mode is opt-in and isolated
- audio behavior is controlled by policy code, not scattered conditionals

### Phase close command

```bash
uv run --extra dev pytest tests/unit tests/integration -k audio
```

## Phase 7: Operability

### Goal

Make the system maintainable under real usage.

### Start with tests

- health check tests
- structured event/log schema tests
- metrics emission tests
- config validation and startup-failure tests

### Implementation

- add health/readiness endpoints or equivalents
- add structured logs for call/session/pipeline events
- add latency/error counters for each pipeline stage
- document deployment topology and required secrets

### Exit criteria

- broken config fails fast
- runtime health is inspectable
- enough telemetry exists to debug latency and call failures without guesswork

### Phase close command

```bash
uv run --extra dev pytest tests/unit tests/contract tests/integration
```

## Phase 8: Decommission Transitional Paths

### Goal

Remove or isolate old architecture so the repo reflects the new system instead of carrying two competing designs.

### Start with tests

- regression tests covering the supported production flows
- tests guarding any transitional compatibility layer still intentionally retained

### Implementation

- delete dead orchestration code
- move retained legacy components behind explicit compatibility boundaries
- update docs so the default setup path is Pipecat + LiveKit

### Exit criteria

- the supported path in the repo is unambiguous
- old custom orchestration is either gone or clearly marked non-core
- docs, config, and tests all describe the same architecture

### Phase close command

```bash
uv run --extra dev pytest
```

## Initial Execution Order

Do this in order:

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 3
5. Phase 4 and Phase 5
6. Phase 6
7. Phase 7
8. Phase 8

Phase 4 and Phase 5 can overlap only after the shared session model is stable.

## Immediate Next Slice

The highest-leverage first execution slice is:

1. fix the test harness
2. define adapter interfaces around the current Mac backend
3. type the core session/transcript/task event envelopes
4. stand up a Pipecat skeleton that can consume fake audio and emit translated output in tests

That sequence derisks the pivot before any SIP/provider work starts.

## Clarity Check

This plan is executable.

What is clear:

- the target architecture
- what code should be reused vs retired
- the order of migration
- the test-first rule for every phase
- the definition of done for each phase

What still needs confirmation during implementation, not before starting:

- exact package placement for the Pipecat app
- whether Telegram remains a supported ingress path or becomes a separate compatibility track

Those are execution details, not blockers for beginning Phase 0.
