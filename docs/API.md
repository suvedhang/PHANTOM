# API Reference

Base URL: `http://127.0.0.1:8000`. Application routes are under `/api/v1`.
Interactive docs: `/docs` (OpenAPI).

## Health

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/health` | API readiness; checks DB with `SELECT 1`. Returns `status` and a `db` state |

## System

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/system/status` | Aggregate system state |
| `GET` | `/api/v1/system/config` | Effective non-secret configuration |
| GET | `/api/v1/system/errors` | Recent recorded errors |

## Runs

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/runs` | List runs |
| `GET` | `/api/v1/runs/active` | Current active run (or null) |
| `GET` | `/api/v1/runs/{run_id}` | Run detail |
| `POST` | `/api/v1/runs` | Start a run |
| `POST` | `/api/v1/runs/stop` | Stop the active run |

Start request body:

```json
{ "mode": "mock", "fps": 15 }
```

`mode` is `"mock"` or `"real"`. In non-demo deployments a `real` run requires a
configured and verified PipeGen adapter.

## Observations and events

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/events` | List/query events |
| `GET` | `/api/v1/events/export` | Export events (JSON or CSV) |
| `GET` | `/api/v1/events/{event_id}` | Event detail |
| `PATCH` | `/api/v1/events/{event_id}` | Update lifecycle/notes |
| `GET` | `/api/v1/events/{event_id}/audit` | Audit trail for an event |

Export query params include format selection and filters mirroring the list
endpoint.

## Rules

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/rules` | List rules |
| `POST` | `/api/v1/rules` | Create a rule (validated against supported types) |
| `GET` | `/api/v1/rules/{rule_id}` | Rule detail |
| `PUT` | `/api/v1/rules/{rule_id}` | Replace a rule |
| `PATCH` | `/api/v1/rules/{rule_id}` | Partial update (e.g. enable/disable) |
| `GET` | `/api/v1/rules/export` | Export rule set |
| `GET` | `/api/v1/rules/{rule_id}/versions` | Version history |
| `GET` | `/api/v1/rules/{rule_id}/versions/{version}` | Specific version snapshot |
| `POST` | `/api/v1/rules/{rule_id}/test` | Dry-run a test observation |
| `POST` | `/api/v1/rules/{rule_id}/sample-test` | Dry-run against a bundled sample |

`GET /api/v1/rules/{rule_id}/versions` returns:

```json
{ "items": [ { "version": 1, "snapshot": { }, "created_at": "..." } ] }
```

## Regions

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/regions` | List regions |
| `POST` | `/api/v1/regions` | Create a region |
| `PUT` | `/api/v1/regions/{region_id}` | Update a region |
| `DELETE` | `/api/v1/regions/{region_id}` | Delete a region |

## Analytics

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/analytics/summary` | Totals, per-rule breakdown, event time series |

`events_over_time` is returned as hourly buckets:

```json
[ { "bucket_start": "2026-01-01T00:00:00Z", "count": 4 } ]
```

## Evidence

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/evidence/status` | Artifact registry and completeness |
| `PUT` | `/api/v1/evidence/{artifact_id}` | Record artifact path/notes |
| `POST` | `/api/v1/evidence/{artifact_id}/verify` | Explicitly verify an artifact |

Artifact statuses: `missing`, `pending`, `captured`, `verified`, `invalid`.
Setting a path marks an artifact `captured`; only an explicit verify marks it
`verified`.

## Pipeline

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/pipeline/status` | Adapter/run status and provenance |
| `GET` | `/api/v1/pipeline/preflight` | Configuration readiness checks |
| `GET` | `/api/v1/pipeline/export` | Export pipeline/report metadata |

## System health

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness + database check |

## Transport

WebSocket: `GET /ws` (upgrade). The server emits `connected`, `heartbeat`,
`observation`, `run_status`, `event_created`, `event_updated`. Clients must send
text periodically to keep the socket open; `observation` frames may be dropped
under load and slow clients are closed rather than blocking ingestion.

Optional MQTT publishing uses the `phantom` topic prefix.

## Error structure

Unhandled server errors return a non-leaking envelope:

```json
{
  "error": "internal_error",
  "code": "internal_error",
  "detail": "An internal error occurred. Check server logs.",
  "correlation_id": "..."
}
```

Request validation errors use FastAPI's standard `422` shape (`detail` array of
field errors). Domain validation (for example an unsupported rule type or a
missing region) returns a `4xx` with a human-readable `detail`.
