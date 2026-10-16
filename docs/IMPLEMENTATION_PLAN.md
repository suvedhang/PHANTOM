# PHANTOM — Implementation Plan

Living checklist. Items are marked `[x]` only when implemented **and** verified.

## 1. Backend (`apps/api`)

- [x] FastAPI app, config, structured errors, CORS
- [x] Pydantic schemas (schema version `1.0`) and SQLite persistence
- [x] Repository layer over the database models
- [x] Deterministic rule engine
  - [x] Normalized geometry helpers (`rule_engine/geometry.py`)
  - [x] Engine state machine (`rule_engine/engine.py`) with cooldown + dedup
  - [x] Supported rule types: `region_entry`, `region_exit`, `dwell_time`,
        `wrong_way`, `count_threshold`
  - [x] Deterministic explanations (no LLM)
- [x] Adapter boundary
  - [x] Mock adapter (deterministic scenario, `is_simulated = true`)
  - [x] PipeGen adapter (transparent failure, preflight only)
- [x] Services: rules, events, run manager, analytics, evidence
- [x] WebSocket transport with heartbeat and slow-client handling
- [x] REST API v1: runs, regions, rules, events, analytics, pipeline, system,
      evidence, health
- [x] `datetime.utcnow()` removed in favour of timezone-aware UTC

### Backend tests (`apps/api/tests`)

- [x] `test_geometry.py`
- [x] `test_rule_engine.py`
- [x] `test_mock_adapter.py`
- [x] `test_schemas.py`
- [x] `test_pipegen_adapter.py`
- [x] `test_api.py`
- [x] Full suite green (only a library-level starlette/httpx deprecation warning)

## 2. Frontend (`apps/web`)

- [x] Vite + React + TypeScript workspace, dark operations-centre theme
- [x] Typed API client mirrored against the backend contract
- [x] Live WebSocket hook + app context (status polling, event/observation merge)
- [x] Design system components (Button, Badge, Card, Table, Dialog/Drawer,
      Toast, Charts, StatTile, SceneOverlay, states)
- [x] App shell, navigation, status strip, run control
- [x] Pages, all functional (no empty placeholders):
  - [x] Overview
  - [x] Live Scene (normalized overlays, trails, regions, active incidents)
  - [x] Rule Graph (entities → regions → rules)
  - [x] Events (filters, pagination, detail drawer, actions, export)
  - [x] Analytics (windowed aggregates + charts, labelled units)
  - [x] Rules (CRUD, config editor, versions, dry-run sample test)
  - [x] Regions (polygon editor, CRUD)
  - [x] Pipeline (status, preflight, run control, export paths)
  - [x] Settings (effective config, secret redaction, provenance legend)
  - [x] System Health (process, transport, pipeline, recent errors)
  - [x] Evidence (checklist, edit, verify/invalidate)
  - [x] About (scope, provenance, schema)
- [x] `npm run web:typecheck` passes
- [x] `npm run web:lint` passes (`--max-warnings=0`)
- [x] `npm run web:build` passes

## 3. Contracts

- [x] `packages/contracts/schema/event.schema.json`
- [x] `packages/contracts/schema/observation.schema.json`
- [x] `packages/contracts/schema/rule.schema.json`
- [x] `packages/contracts/schema/region.schema.json`

## 4. Docs

- [x] `README.md`
- [x] `docs/ARCHITECTURE.md` (Mermaid data-flow diagram)
- [x] `docs/EVENT_SCHEMA.md`
- [x] `docs/RULES.md`
- [x] `docs/API.md`
- [x] `docs/PIPEGEN_SETUP.md`
- [x] `docs/PIPEGEN_INTEGRATION.md`
- [x] `docs/DEMO_SCRIPT.md`
- [x] `docs/EVALUATION.md`
- [x] `docs/EVIDENCE_CHECKLIST.md`
- [x] `docs/ASSUMPTIONS_AND_LIMITATIONS.md`
- [x] `docs/TROUBLESHOOTING.md`
- [x] `docs/IMPLEMENTATION_PLAN.md` (this file)

## 5. Developer scripts & output

- [x] `scripts/` dev helpers (run backend, run web, run tests, check web,
      reset output)
- [x] `output/` structure (evidence, exports, logs, db) wired; `reset-output.ps1`
      clears generated artifacts only

## 6. Guardrails (must hold at all times)

- [x] No fabricated PipeGen APIs, metrics, or GPU telemetry
- [x] Simulated data visibly and programmatically labelled
- [x] Real pipeline path fails transparently
- [x] No empty placeholder pages; no inert primary buttons
- [x] No swallowed exceptions in the UI
- [x] Accessible labels, visible focus, labelled chart units
- [x] Geometry documented as normalized image-space, not metres

## Verification commands

Backend (from repo root, using the project venv):

```powershell
cd apps\api
..\..\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
npm run web:typecheck
npm run web:lint
npm run web:build
```
