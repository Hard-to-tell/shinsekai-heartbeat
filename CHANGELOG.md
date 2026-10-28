# Changelog

## 0.5.2 - 2026-10-29

- Allow ordinary heartbeat intervals from 30 seconds in settings and config loading, retaining bounded randomness and the 5–15 minute defaults. Study screen checks still require at least one minute.

## 0.5.1 - 2026-10-28

- Enforce a one-minute minimum idle interval in settings and legacy configuration loading; retain bounded randomness and the 5–15 minute defaults.
- Handle negated study-start commands, discard in-flight observations after user corrections, and stop counting rejected heartbeat inputs as successful.
- The Shinsekai 2.5.1 reply/TTS completion integration remains unavailable; the minimum interval is a mitigation, not a completion signal.

## 0.5.0 - 2026-10-28

- Bias initial random waits toward active companionship; gently favor longer waits after unanswered heartbeats without exceeding the configured range. User input resets the bias; disabling adaptive mode preserves uniform waits.
- Show expiring chat status only in settings, refreshed when reopening the page, and add QQ contact information.

- Fix ordinary heartbeats never becoming due when study supervision is disabled.
- Document the Shinsekai 2.5.1 compatibility gap: the retired Qt bridge no longer provides final reply/TTS completion notifications. SDK import success is not full runtime compatibility.

## 0.4.2 - 2026-08-24

- Make study classification lenient: ambiguous, unreadable, and ordinary chat screens now stay silent.
- Add configurable study-safe hints with one lightweight `chat` default covering AI chat interfaces.
- Trust corrections such as “没分心” or “你看错了”, skip the next check, and reset reminder escalation.

## 0.4.1 - 2026-08-23

- Make study supervision independently switchable, enabled by default.
- Prefer short one-line distraction reminders and cap them at two lines.
- Use a stricter two-label screen check, tell the character the configured session length, and support consecutive focus sessions.

## 0.4.0 - 2026-08-23

- Add a natural-language study mode: say “我要学习，请监督我” to start a quiet focus session, or ask to stop/休息 to end it.
- Check the screen at a separate low-frequency interval, stay silent for study or uncertain activity, and only speak for clear distraction.
- Escalate repeated distraction reminders from gentle to visibly annoyed while explicitly avoiding insults, humiliation, threats, or discriminatory language.
- End the default 25-minute focus session with a break reminder.
- Expand the built-in conversation question pool from 3 to 15 prompts.
- Refresh the plugin and community-registry descriptions around proactive companionship and study supervision.

## 0.3.3 - 2026-07-28

- Add a dedicated marketplace icon with a transparent background.
- Localize the marketplace and installed-plugin name, description, and search guidance for Chinese users.

## 0.3.2 - 2026-07-23

- Cancel a due heartbeat when user activity or shutdown wins the final emission race.
- Wait for final host reply completion and all queued replies before resuming idle scheduling.
- Share one thread-safe configuration store between runtime and settings, with atomic file replacement.
- Add a visible switch for adaptive short/medium/long idle behavior.
- Test plugin imports against the real Shinsekai 2.1.0 SDK in CI.

## 0.3.1 - 2026-07-03

- Add short, medium, and long idle policies so short heartbeats continue recent topics while long heartbeats favor screen context and fixed questions.
- Keep the last three user inputs as trimmed context for heartbeat prompts.
- Avoid field-level hover descriptions in the settings page to prevent tooltip overlap with the sidebar.
- Clarify how prompt text areas differ from line-based fixed text pools.
- Explain prompt separators, language choice, and Moondream's English default in the settings page.

## 0.3.0 - 2026-07-02

- Add a Shinsekai plugin configuration page for idle timing, mode weights, prompts, and fixed text pools.
- Convert user-friendly form values back into the existing hot-reloaded `config.json` format.

## 0.2.0 - 2026-07-01

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
