# Changelog

## 0.2.0 - Unreleased

- Draw a new idle interval from a configurable random range after each interaction.
- Randomize the target reply length.
- Add JSON-editable fixed question and common expression pools.
- Log each newly scheduled interval for easier diagnostics.
- Avoid repeating the previous mode, fixed question, or expression when alternatives exist.
- Pause heartbeats until the current LLM reply and TTS playback finish.

## 0.1.0 - 2026-06-30

- Add idle-based heartbeat scheduling with JSON hot reload.
- Add weighted screen, monologue, and question modes.
- Add optional Moondream Vision tool integration with automatic fallback.
- Reset or cancel heartbeats when the user sends a message.
