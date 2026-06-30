# Architecture

Heartbeat Companion deliberately uses only Shinsekai's public plugin surface.

## Data flow

```text
normal user input
  -> input processor records activity
  -> scheduler deadline moves forward

idle deadline
  -> hot-load config.json
  -> weighted mode selection
  -> optional moondream_query_screen call
  -> recheck user activity generation
  -> emit_user_text(...)
  -> Shinsekai LLM -> UI -> TTS
```

## Modules

- `plugin.py` provides metadata and registers the input trigger and processor.
- `runtime.py` owns the process-local scheduler instance and lifecycle.
- `config.py` creates, validates, and hot-loads `config.json`.
- `scheduler.py` owns idle timing, mode selection, cancellation, and message formatting.
- `vision.py` discovers and invokes Moondream's registered tool without importing its implementation.

The scheduler is a single daemon thread. It never calls the host LLM or TTS directly; it only uses the callback supplied through `register_user_input_trigger`. This keeps replies in the current conversation and preserves the selected character, LLM provider, output parser, UI, and TTS configuration.

## Cross-plugin integration

Moondream Vision is optional. The plugin searches `sdk.tool_registry.registered_tool_entries()` for `moondream_query_screen`. Missing tools, loading models, tool errors, or empty answers all return `None`, causing immediate selection of a non-screen heartbeat mode.

No screenshots or screen summaries are persisted by Heartbeat Companion. Screen handling remains owned by Moondream Vision.

## Lifecycle guarantees

- Startup waits a full interval before the first heartbeat.
- User input updates a monotonic activity timestamp and generation counter.
- A screen result is discarded if the generation changed during inference.
- Successful emission restarts the idle interval.
- Shutdown disables emission before requesting worker termination.
