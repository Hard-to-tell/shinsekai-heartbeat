# Development and release

## Local integration

Install or link this repository as:

```text
<Shinsekai>/plugins/heartbeat_companion
```

Add the manifest entry from the README, restart Shinsekai, and confirm that the generated data file appears under `data/plugins/io.github.hard_to_tell.heartbeat_companion/`.

For a quick test, temporarily set `interval_minutes` to `0.1`. Restore a normal value before release.

## Verification

Run the standard-library test suite:

```powershell
& <Shinsekai>\runtime\python.exe -m unittest discover -s tests -v
```

Manual checks:

1. Monologue-only and question-only weights trigger the expected event type.
2. Sending a user message restarts the interval.
3. Config edits take effect without restarting.
4. Missing Moondream falls back without breaking the heartbeat.
5. Installed Moondream contributes a short screen summary.
6. Closing Shinsekai stops all future emission.

## Release

1. Update `__version__`, `plugin_version`, README, and CHANGELOG together.
2. Run tests and a V2.1.0 integration smoke test.
3. Commit, push, and create a matching `vX.Y.Z` GitHub release.
4. Submit `registry-submission.json` through the Shinsekai Plugin Registry publish flow.

The plugin source remains a separate repository. Changes to Shinsekai itself are not required.
