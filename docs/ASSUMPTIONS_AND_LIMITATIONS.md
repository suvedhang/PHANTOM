# Assumptions and Limitations

This document separates **verified facts**, **assumptions**, and **missing
integrations**. Do not present an assumption as verified.

## Verified facts (tested on the development environment)

- Backend imports and runs; the full test suite passes: **84 tests**.
- The web app passes `typecheck`, `lint` (`--max-warnings=0`), and a production
  `build`.
- The deterministic rule engine produces identical events for identical ordered
  observations, with dedup/cooldown lifecycle behaviour, proven by tests.
- The mock adapter produces clearly-labelled `SIMULATED` observations and is
  deterministic.
- Evidence statuses only advance to `verified` after an explicit verify call.
- Environment verified: **Windows + PowerShell**, **Node v24.19.0**,
  **npm 11.17.0**, **Python 3.12.10**.

Not verified: any Linux/macOS setup, and any real PipeGen run.

## Assumptions

- PipeGen exposes its pipeline output as files in an export directory, including
  a metadata file named `run_metadata.json` with the fields PHANTOM expects. This
  file name and schema are **assumptions**, not confirmed.
- PipeGen accepts a `--version` flag for version probing. If it does not, the
  probe merely reports failure; PHANTOM does not guess.
- The host has a supported NVIDIA GPU and a working PipeGen install for the
  real-run demonstration.
- Observations are delivered as normalized image-space coordinates with a stable
  track id per object.

## Missing integrations

- **PipeGen run contract is unverified.** `adapters/pipegen.py` refuses to start
  a run and raises a transparent error until the exact command/output contract
  is recorded. It never invents CLI flags.
- **No real observation stream.** `pipegen.observe()` yields nothing; the run
  manager surfaces a disconnected state instead of fake data.
- **No fixtures.** `adapters/pipegen/fixtures` is empty — no captured real runs
  are available to test the mapping.
- **No GPU telemetry.** Model id, precision, FPS, latency, and GPU metrics are
  `null` in demo/mock mode and shown as "not reported".

## Limitations

- Coordinates are normalized image-space `[0,1]` with origin top-left — **not
  metres**. Directions and displacements are in the image plane.
- Region membership uses the bounding-box center (ray casting), not full polygon
  overlap.
- The wrong-way tolerance (30°) and stale-track window (default 4.0s) are fixed
  constants, not per-rule tuning.
- SQLite is the store; no horizontal scaling is attempted.
- WebSocket `observation` frames may be dropped under load, and slow clients are
  closed rather than blocking ingestion.
- The final hackathon demonstration's live vision portion must use the real
  PipeGen pipeline; the mock is for development and rehearsal only.
