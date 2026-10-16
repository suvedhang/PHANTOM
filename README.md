# PHANTOM

**Physical AI scene intelligence for the Embedded SF CraftifAI Physical AI Hackathon (Track A).**

PHANTOM turns live computer-vision observations into deterministic, scene-specific
rule violations and explainable events. It is deliberately split into a
well-defined **PipeGen adapter boundary** so the vision pipeline can be swapped
without touching the rule engine, transport, or UI.

## Problem

Live vision pipelines produce raw detections, not decisions. Operators need to
know *what happened*, *why it was flagged*, and *what evidence supports it* —
deterministically and with a clear boundary between the vision toolchain and the
business logic. PHANTOM provides that layer.

## Concept

- Normalized observations (image-space `[0,1]` coordinates) are ingested from
  either the real PipeGen adapter or a clearly-labelled deterministic mock.
- A deterministic rule engine evaluates scene-specific rules (region entry/exit,
  dwell, wrong-way, count threshold) and emits explainable events with a
  human-readable reason and a machine-readable predicate.
- Events flow over WebSocket (and optionally MQTT) to a React dashboard with
  live scene overlay, rule graph, analytics, evidence tracking and pipeline
  status.

## Features

- **Deterministic rule engine** — same input frames always yield the same
  events; de-duplication and cooldowns prevent event storms.
- **Explainable events** — every event carries `human`, `machine (condition /
  observed / threshold)`, `severity`, `provenance`, and the triggering
  observation/track ids.
- **Live scene overlay** — normalized bboxes and region polygons rendered over
  the frame feed with accessible labels.
- **Rule graph** — visualizes rules, regions and currently-flagged tracks.
- **Analytics** — event volume over time and per-rule breakdowns from stored
  data (hand-rolled SVG charts, no fabricated live metrics).
- **Evidence registry** — mandatory submission artifacts with explicit
  `missing | pending | captured | verified | invalid` statuses.
- **Transport** — WebSocket hub with heartbeat and backpressure; optional MQTT
  publisher (`phantom` topic prefix).
- **Mock mode** — deterministic, self-labelling (`MOCK` / `SIMULATED`) adapter
  for rehearsed demos without GPU hardware.

## Architecture

See `docs/ARCHITECTURE.md` for the Mermaid data-flow diagram and the adapter
boundary. In short:

```
PipeGen (real)  ─┐
                 ├─▶ Adapter ─▶ Rule Engine ─▶ Event Service ─▶ WebSocket/MQTT ─▶ Web UI
Mock (labelled) ─┘                              │
                                                └─▶ SQLite (events, runs, evidence)
```

## Repository layout

```
apps/api/            FastAPI backend, rule engine, adapters, transport
apps/web/            React + Vite dashboard
packages/contracts/  JSON Schemas for observation/event/rule/region payloads
docs/                Architecture, schema, integration, and demo documentation
scripts/             PowerShell helper scripts
output/              Generated runtime artifacts (db, logs, exports, evidence)
```

## Setup

Prerequisites: **Node 20+**, **Python 3.11+**, PowerShell (Windows) or a shell.

```powershell
# 1. Python environment
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r apps\api\requirements.txt

# 2. Frontend dependencies (npm workspaces)
npm install
```

Copy the sample environment files and adjust as needed:

```powershell
Copy-Item apps\api\.env.example apps\api\.env
Copy-Item apps\web\.env.example apps\web\.env
```

## Operation

```powershell
# Backend (mock auto-starts by default in demo mode)
scripts\run-backend.ps1

# Frontend dev server
scripts\run-web.ps1
```

Open the Vite dev URL (default http://127.0.0.1:5173). The API listens on
http://127.0.0.1:8000 by default.

## Testing

```powershell
scripts\run-tests.ps1     # pytest (backend)
scripts\check-web.ps1     # typecheck + lint + build
```

Or directly:

```powershell
npm run web:typecheck
npm run web:lint
npm run web:build
.\.venv\Scripts\python.exe -m pytest apps\api -q
```

## Commands

| Command | Purpose |
| --- | --- |
| `npm run web:dev` | Vite dev server |
| `npm run web:typecheck` | `tsc --noEmit` |
| `npm run web:lint` | ESLint (`--max-warnings=0`) |
| `npm run web:build` | Typecheck + production build |

## Limitations (summary)

- The real PipeGen path cannot be verified in this environment (no NVIDIA
  GPU/host); it fails transparently rather than fabricating results.
- In demo mode all events are `is_simulated: true` and labelled `SIMULATED`;
  none of that is presented as real evidence.
- The mock adapter derives no model, precision, FPS, latency, or GPU metrics —
  those remain `null` and are shown as "not reported".
- Coordinates are normalized image-space, **not** metres.

See `docs/ASSUMPTIONS_AND_LIMITATIONS.md` for the full distinction between
verified facts, assumptions, and missing integrations.

## Documentation

- `docs/ARCHITECTURE.md` — data flow and boundary diagram
- `docs/PIPEGEN_INTEGRATION.md` — adapter contract and real-run workflow
- `docs/PIPEGEN_SETUP.md` — verified setup path
- `docs/EVENT_SCHEMA.md` — observation and event payloads
- `docs/RULES.md` — supported rules and limitations
- `docs/API.md` — key routes and error structures
- `docs/DEMO_SCRIPT.md` — timed demonstration sequence
- `docs/EVALUATION.md` — measurable tests and metrics
- `docs/EVIDENCE_CHECKLIST.md` — required PipeGen artifacts
- `docs/ASSUMPTIONS_AND_LIMITATIONS.md` — verified vs assumed vs missing
- `docs/TROUBLESHOOTING.md` — startup, source, transport, DB errors
