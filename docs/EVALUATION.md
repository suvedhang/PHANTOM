# Evaluation

Measurable tests and metrics for PHANTOM. Only tests that were actually run are
reported as verified; anything requiring GPU/PipeGen hardware is listed as
unverified.

## Automated tests (verified)

Run with `scripts\run-tests.ps1` or
`.\.venv\Scripts\python.exe -m pytest apps\api -q`.

| Area | Module | What it proves |
| --- | --- | --- |
| Geometry | `test_geometry.py` | Point-in-polygon, bearing, displacement, angular difference |
| Rule engine | `test_rule_engine.py` | Deterministic outcomes, dedup, cooldown, lifecycle transitions |
| Mock adapter | `test_mock_adapter.py` | Simulated labelling, determinism, scenario output |
| Schemas | `test_schemas.py` | Contract validation and (de)serialization |
| PipeGen adapter | `test_pipegen_adapter.py` | Preflight/config behaviour, transparent failure |
| API | `test_api.py` | Route behaviour, error envelopes, event flow |

Current result on the development environment: **84 passed** (one dependency
deprecation warning from starlette/httpx, not from PHANTOM code).

## Frontend checks (verified)

| Check | Command | What it proves |
| --- | --- | --- |
| Typecheck | `npm run web:typecheck` | `strict` + `noUnused*` + `noUncheckedIndexedAccess` clean |
| Lint | `npm run web:lint` | ESLint with `--max-warnings=0` |
| Build | `npm run web:build` | Production build succeeds |

## Determinism metric

Given identical ordered observations and identical rule/region definitions, the
engine must produce an identical event sequence. This is asserted directly by
the rule-engine and mock-adapter tests (fixed scenarios, fixed expected events).

## Explainability metric

Every emitted event must contain:

- a human-readable `human` string, and
- a machine-readable predicate (`condition`, `observed`, `threshold`, `outcome`,
  `rule_type`).

Tests assert that created/cleared events carry both.

## Event-storm suppression

For a persistent condition the engine emits exactly one `create`, then at most
one `update` per `dedup_seconds`, and exactly one `clear` when it ends. Asserted
in `test_rule_engine.py`.

## Evidence integrity

The evidence registry must never report `verified` for an artifact that was only
configured. Setting a path yields `captured`; only an explicit verify yields
`verified`. Asserted in the API tests.

## Unverified (requires hardware/toolchain)

These cannot be measured in this environment (no NVIDIA GPU/host) and must be
completed on the demo machine:

- Real PipeGen end-to-end latency, FPS, and throughput.
- TensorRT speed report numbers.
- GPU utilisation / memory telemetry.
- Cross-adapter equivalence (mock vs real) on the same scene.

Do not report figures for the above until they are produced by the real
toolchain.
