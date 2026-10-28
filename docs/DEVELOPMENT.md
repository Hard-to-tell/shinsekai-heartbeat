# Development and release

## Local integration

Install or link this repository as:

```text
<Shinsekai>/plugins/heartbeat_companion
```

Add the manifest entry from the README, restart Shinsekai, and confirm that the generated data file appears under `data/plugins/io.github.hard_to_tell.heartbeat_companion/`.

For a quick test, temporarily set `interval_minutes_range` to `[0.5, 1]`. Restore a normal range before release.

## Verification

The SDK smoke check verifies imports, registration, and config persistence only, not reply/TTS completion tracking. The current CI host remains pinned to 2.1.0.

Run the standard-library test suite:

```powershell
& <Shinsekai>\runtime\python.exe -m unittest discover -s tests -v
& <Shinsekai>\runtime\python.exe tests\smoke_host_sdk.py <Shinsekai>
```

Manual checks:

1. Monologue-only and question-only weights trigger the expected event type.
2. Sending a user message restarts the interval.
3. Config edits take effect without restarting.
4. Missing Moondream falls back without breaking the heartbeat.
5. Installed Moondream contributes a short screen summary.
6. Closing Shinsekai stops all future emission.
7. “我要学习，请监督我” starts study mode and a stop phrase ends it.
8. STUDY, UNCERTAIN, safe-hint, and unavailable screen results stay silent; DISTRACTED emits one reminder.
9. User corrections skip one check and reset escalation; repeated clear distractions still escalate.
10. The focus deadline emits a break reminder once.

## Release

1. Update `__version__`, README, and CHANGELOG together; `plugin_version` reads `__version__` directly.
2. Run tests and a V2.1.0 integration smoke test.
3. Commit, push, and create a matching `vX.Y.Z` GitHub release.
4. Submit `registry-submission.json` through the Shinsekai Plugin Registry publish flow.

The plugin source remains a separate repository. Changes to Shinsekai itself are not required.
