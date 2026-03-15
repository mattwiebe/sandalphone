# Testing

## Default suite

Run the unattended baseline with:

```bash
uv run --extra dev pytest
```

This runs fast unit tests and skips tests that require a live service or local media/model tooling.

## Test levels

- `unit`: fast isolated tests
- `contract`: typed interface and payload contract tests
- `integration`: cross-component or running-service tests
- `hardware`: tests that require local models, macOS media tooling, or heavier runtime setup

## Opt-in suites

Enable integration tests:

```bash
RUN_INTEGRATION_TESTS=1 uv run --extra dev pytest -m integration
```

Use custom websocket endpoints if needed:

```bash
TEST_TRANSLATE_WS_URL=ws://localhost:8000/ws/translate
TEST_STREAM_WS_URL=ws://localhost:8000/ws/stream
```

Enable hardware-backed tests:

```bash
RUN_HARDWARE_TESTS=1 uv run --extra dev pytest -m hardware
```

When running tests under `mac/` that exercise real inference or media paths, include the `mac` extra:

```bash
RUN_HARDWARE_TESTS=1 uv run --extra dev --extra mac pytest -m hardware
```
