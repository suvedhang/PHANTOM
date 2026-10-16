# PipeGen Integration

## Status

The real PipeGen inference path is **not verified in this repository**. It is
implemented behind a strict adapter boundary and fails transparently: nothing in
the UI or API fabricates PipeGen output, versions, or hardware telemetry.

The runnable, demonstrable path is the deterministic **mock adapter**, which is
always labelled `SIMULATED` in the interface and tagged `is_simulated: true` in
the data.

## What is known

- The platform consumes **normalized observations** — per-frame detections with a
  class label, an optional track id, an optional bounding box, and an optional
  confidence — and evaluates scene-specific rules against them.
- The boundary between the CV pipeline and PHANTOM is a single adapter
  interface (`apps/api/phantom_api/adapters/base.py`). Everything downstream of
  the adapter (rule engine, event service, transport, API) is pipeline-agnostic.
- A real integration must produce observations conforming to **schema version
  1.0** (`packages/contracts/schema/observation.schema.json`).

## What is assumed (unverified)

These are design assumptions, not verified PipeGen facts. They are isolated in
`adapters/pipegen.py` so they can be corrected without touching the platform:

- PipeGen exposes frames or per-frame detections through *some* Python-callable
  or file-based surface.
- An expected PipeGen version string may need to match a configured value.
- A model id and numeric precision may be reported by the pipeline.

Because these are unverified, the adapter does **not** assert any of them. Its
`preflight()` reports only local checks (configuration presence, expected version
string presence) and a `blocker` explaining what is missing. Its `start()` and
observation iterator are unimplemented and raise a clear, typed error rather than
returning fabricated data.

## What remains unverifiable here

- Whether PipeGen is present at all (no host/GPU in the authoring environment).
- Exact call signatures, return shapes, and version strings.
- Any hardware or GPU utilisation figures. PHANTOM reports **no** GPU metrics.

## Path to a real run

1. Implement `PipeGenAdapter.start()` and its observation iterator against the
   actual PipeGen API.
2. Fill in `preflight()` checks that reflect the real contract, keeping each
   check independent and its `detail` human-readable.
3. Set the adapter to emit observations under schema version 1.0.
4. Confirm `GET /api/v1/pipeline/preflight` reports `ready_to_run: true` and the
   UI's **Start real** control becomes enabled.
5. Only then do model id, precision, and version fields become non-null.

Until step 5, those fields remain `null` and the UI states that the value is not
reported rather than inventing one.

## Failure semantics

- When the adapter is not configured, the pipeline status is `not_configured`
  and the blocker explains why.
- When a real run is requested but preflight fails, the request is rejected with
  a structured error; the UI disables the action and shows the blocker.
- The mock adapter never claims to be the real pipeline: `adapter_kind` is
  `"mock"` and `is_simulated` is `true` while a simulated run is active.
