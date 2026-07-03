# Changelog

## 0.3.1 - Unreleased

- Add short, medium, and long idle policies so short heartbeats continue recent topics while long heartbeats favor screen context and fixed questions.
- Keep the last three user inputs as trimmed context for heartbeat prompts.
- Avoid field-level hover descriptions in the settings page to prevent tooltip overlap with the sidebar.
- Clarify how prompt text areas differ from line-based fixed text pools.
- Explain prompt separators, language choice, and Moondream's English default in the settings page.

## 0.3.0 - 2026-07-02

- Add a Shinsekai plugin configuration page for idle timing, mode weights, prompts, and fixed text pools.
- Convert user-friendly form values back into the existing hot-reloaded `config.json` format.

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
