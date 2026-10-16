# Troubleshooting

## Startup

**The API exits with "PHANTOM cannot start with the current configuration".**

The message lists each failing check. The most common cause is
`PHANTOM_DEMO_MODE=false` without a configured PipeGen adapter. Either set
`PHANTOM_PIPEGEN_EXECUTABLE` and `PHANTOM_PIPEGEN_EXPORT_DIR` (see
`docs/PIPEGEN_SETUP.md`) or leave demo mode enabled.

**Nothing streams and the dashboard is empty.**

By default the mock source auto-starts in demo mode. If autostart is disabled
(`PHANTOM_AUTOSTART_MOCK=false`), start a run from the Overview or Pipeline page,
or `POST /api/v1/runs` with `{"mode": "mock"}`.

## The web app cannot reach the API

- Confirm the backend is running on the expected host/port (`PHANTOM_HOST`,
  `PHANTOM_PORT`, default `127.0.0.1:8000`).
- Check `VITE_API_BASE_URL` in `apps/web/.env`. The default is
  `http://127.0.0.1:8000`. The WebSocket origin is derived from it.
- CORS: the backend allows the origins in `PHANTOM_CORS_ORIGINS` (default
  includes the Vite dev server on port 5173).
- The System Health page shows socket state and the last heartbeat.

## The WebSocket connects then drops

The hub closes slow clients and may drop `observation` frames under load. Large
backlogs are dropped rather than blocking ingestion. Increase
`PHANTOM_INGEST_QUEUE_SIZE` or lower `PHANTOM_UI_FRAME_RATE` if needed.

## Events are not appearing

- A rule must be enabled and reference an enabled region where applicable.
- Region-entry and dwell rules require a track id on the observation.
- Cooldown suppresses repeats for `cooldown_seconds` after an event closes.
- In demo mode, events are tagged `is_simulated: true` and labelled `SIMULATED`.
- Use the rule **Test** action to run a dry-run sample and see whether the rule
  would trigger.

## Latency, FPS, or GPU figures show as "not reported"

This is expected and intentional. PHANTOM reports model id, precision, version,
FPS, latency, and GPU data only when a real adapter provides them. In
demo/mock mode these remain `null` and the UI states they are not reported. No
placeholder numbers are substituted.

## Resetting local state

Run `scripts/reset-output.ps1` to clear generated databases, logs, and exports
under `output/`. The app recreates the directory structure on next start.

## Tests

Run `scripts/run-tests.ps1` from the repository root. The venv is expected at
`.venv\Scripts\python.exe`. A starlette/httpx deprecation warning from a
dependency is expected and not caused by PHANTOM code.
