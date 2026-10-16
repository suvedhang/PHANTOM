# PipeGen Setup

This guide covers configuring the **real** PipeGen adapter. Until it is
completed and verified, run PHANTOM in demo mode with the clearly-labelled mock
adapter. See `docs/PIPEGEN_INTEGRATION.md` for the boundary contract and what is
verifiable.

## Prerequisites

- A host with the PipeGen pipeline installed and runnable.
- A writable export directory PipeGen can write its observations/metadata to.
- A known expected PipeGen version string you want to require.

## Configuration

Settings use the `PHANTOM_` prefix and are read from `apps/api/.env` (see
`apps/api/.env.example`).

| Variable | Purpose | Example |
| --- | --- | --- |
| `PHANTOM_DEMO_MODE` | Set to `false` to require a real adapter | `false` |
| `PHANTOM_PIPEGEN_EXECUTABLE` | Path to the PipeGen executable/entrypoint | `C:\pipegen\pipegen.exe` |
| `PHANTOM_PIPEGEN_EXPORT_DIR` | Directory PipeGen writes observations to | `C:\pipegen\export` |
| `PHANTOM_PIPEGEN_EXPECTED_VERSION` | Version the adapter expects | `0.5.1` |

`pipegen_configured` is true only when **both** the executable and the export
directory are set. With `demo_mode=false` and an unconfigured PipeGen, startup
fails with a clear message rather than silently falling back to the mock.

## Verify readiness

1. Start the backend (`scripts/run-backend.ps1`).
2. Call the preflight endpoint:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/api/v1/pipeline/preflight
   ```

3. Inspect each check. `ready_to_run` is `false` and `blocker` explains what is
   missing until the adapter's contract is verified in code.
4. In the web UI, open **Pipeline** — the **Start real** control stays disabled
   while `ready_to_run` is false, with the blocker shown.

## Enabling a real run

The adapter's `start()` deliberately refuses to run until its assumptions are
replaced with verified facts (see `apps/api/phantom_api/adapters/pipegen.py`).
To enable a real run:

1. Implement the observation stream against the actual PipeGen API.
2. Record the confirmed call signatures and output format in the adapter.
3. Remove the contract guard and keep the transparent error handling.
4. Re-run preflight until `ready_to_run` is `true`.

Do not report model id, precision, version, FPS, latency, or GPU figures that the
pipeline has not actually provided. Until they are provided, they remain `null`.
