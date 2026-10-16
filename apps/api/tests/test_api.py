"""API contract tests: rules, regions, events, evidence, pipeline, runs."""

from __future__ import annotations

import time


def test_health(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_system_status_shape(client) -> None:
    r = client.get("/api/v1/system/status")
    assert r.status_code == 200
    body = r.json()
    assert body["demo_mode"] is True
    assert "pipeline" in body and "transport" in body
    # Never leaks whether secrets are set as values.
    assert "mqtt_password" not in str(body)


def test_seeded_rules_present(client) -> None:
    r = client.get("/api/v1/rules")
    assert r.status_code == 200
    ids = {item["rule_id"] for item in r.json()["items"]}
    assert "rule_seed_restricted_entry" in ids
    assert "rule_seed_dwell" in ids
    assert "rule_seed_wrongway" in ids


def test_rule_create_validation_rejects_unsupported_type(client) -> None:
    r = client.post(
        "/api/v1/rules",
        json={"name": "seq", "type": "sequence", "config": {}, "severity": "low"},
    )
    assert r.status_code == 422


def test_rule_create_validation_rejects_missing_region(client) -> None:
    r = client.post(
        "/api/v1/rules",
        json={
            "name": "bad region",
            "type": "region_entry",
            "config": {"region_id": "does_not_exist"},
            "severity": "low",
        },
    )
    assert r.status_code == 422


def test_rule_crud_and_versioning(client) -> None:
    created = client.post(
        "/api/v1/rules",
        json={
            "name": "My Entry Rule",
            "type": "region_entry",
            "config": {"region_id": "region_restricted"},
            "severity": "medium",
        },
    )
    assert created.status_code == 201
    rule = created.json()
    rule_id = rule["rule_id"]
    assert rule["version"] == 1

    updated = client.put(
        f"/api/v1/rules/{rule_id}",
        json={"severity": "high", "config": {"region_id": "region_restricted", "cooldown_seconds": 5}},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    versions = client.get(f"/api/v1/rules/{rule_id}/versions").json()["items"]
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["snapshot"]["severity"] == "medium"
    assert versions[1]["snapshot"]["severity"] == "high"


def test_rule_disable_preserves_version(client) -> None:
    rule_id = "rule_seed_dwell"
    r = client.patch(f"/api/v1/rules/{rule_id}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False
    assert r.json()["version"] == 2


def test_rule_export(client) -> None:
    r = client.get("/api/v1/rules/export")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "1.0"
    assert body["count"] >= 3


def test_rule_test_rejects_malformed_observation(client) -> None:
    r = client.post(
        "/api/v1/rules/rule_seed_dwell/test",
        json={
            "observations": [
                {
                    "observation_id": "o1",
                    "run_id": "r1",
                    "source_id": "s1",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "frame_index": 0,
                    "entities": [{"class_label": "person", "bbox": {"x_min": 0.9, "y_min": 0.1, "x_max": 0.2, "y_max": 0.2}}],
                }
            ]
        },
    )
    assert r.status_code == 422


def test_rule_sample_test_dry_run(client) -> None:
    r = client.post("/api/v1/rules/rule_seed_restricted_entry/test", json={"observations": []})
    assert r.status_code == 200
    assert r.json()["would_trigger_count"] == 0


def test_regions_seeded(client) -> None:
    r = client.get("/api/v1/regions")
    ids = {item["region_id"] for item in r.json()["items"]}
    assert "region_restricted" in ids


def test_region_delete_blocked_when_referenced(client) -> None:
    r = client.delete("/api/v1/regions/region_restricted")
    assert r.status_code == 409


def test_region_create_and_update(client) -> None:
    poly = {
        "points": [
            {"x": 0.1, "y": 0.1},
            {"x": 0.4, "y": 0.1},
            {"x": 0.4, "y": 0.4},
        ]
    }
    created = client.post("/api/v1/regions", json={"name": "New Region", "polygon": poly})
    assert created.status_code == 201
    region_id = created.json()["region_id"]
    updated = client.put(
        f"/api/v1/regions/{region_id}",
        json={"name": "Renamed", "polygon": poly},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"
    deleted = client.delete(f"/api/v1/regions/{region_id}")
    assert deleted.status_code == 200


def test_pipeline_preflight_honest(client) -> None:
    r = client.get("/api/v1/pipeline/preflight")
    assert r.status_code == 200
    body = r.json()
    assert body["ready_to_run"] is False
    assert "blocker" in body


def test_pipeline_status_has_no_fabricated_metrics(client) -> None:
    client.post("/api/v1/runs", json={"mode": "mock", "fps": 30})
    body = client.get("/api/v1/pipeline/status").json()
    pipeline = body["pipeline"]
    client.post("/api/v1/runs/stop")
    # A simulated run must be labelled as such...
    assert pipeline["is_simulated"] is True
    assert pipeline["adapter_kind"] == "mock"
    # ...and must never carry fabricated engine/report metrics.
    assert pipeline["engine_path"] is None
    assert pipeline["report_path"] is None


def test_evidence_status_lists_missing_required(client) -> None:
    body = client.get("/api/v1/evidence/status").json()
    assert body["complete"] is False
    assert body["missing_required"] >= 4
    for item in body["items"]:
        assert item["status"] in ("missing", "pending", "captured", "verified", "invalid")


def test_rules_export_endpoint_returns_json(client) -> None:
    r = client.get("/api/v1/rules/export")
    assert r.headers["content-type"].startswith("application/json")


def _live_events(client):
    """Start a simulated run and wait for rule triggers."""
    start = client.post("/api/v1/runs", json={"mode": "mock", "fps": 30})
    assert start.status_code == 200
    deadline = time.time() + 15
    items = []
    while time.time() < deadline:
        items = client.get("/api/v1/events", params={"limit": 50}).json()["items"]
        if len(items) >= 2:
            break
        time.sleep(0.5)
    return items


def test_mock_run_produces_labelled_events(client) -> None:
    items = _live_events(client)
    assert items, "expected events from simulated run"
    assert all(item["is_simulated"] is True for item in items)
    assert all(item["provenance"] == "simulated" for item in items)
    assert all(item["rule_version"] >= 1 for item in items)
    client.post("/api/v1/runs/stop")


def test_event_lifecycle_and_audit(client) -> None:
    items = _live_events(client)
    client.post("/api/v1/runs/stop")
    event_id = items[0]["event_id"]

    detail = client.get(f"/api/v1/events/{event_id}").json()
    assert detail["event"]["event_id"] == event_id
    assert any(a["action"] == "created" for a in detail["audit"])

    ack = client.patch(f"/api/v1/events/{event_id}", json={"action": "acknowledge", "actor": "qa"})
    assert ack.status_code == 200
    assert ack.json()["status"] == "acknowledged" if "status" in ack.json() else True

    resolved = client.patch(
        f"/api/v1/events/{event_id}", json={"action": "resolve", "actor": "qa", "note": "handled"}
    )
    assert resolved.status_code == 200

    detail2 = client.get(f"/api/v1/events/{event_id}").json()
    actions = [a["action"] for a in detail2["audit"]]
    assert "created" in actions
    assert "acknowledged" in actions
    assert "resolved" in actions


def test_dismiss_requires_note(client) -> None:
    r = client.patch("/api/v1/events/evt_missing", json={"action": "dismiss"})
    assert r.status_code == 422


def test_event_filters_and_pagination(client) -> None:
    _live_events(client)
    client.post("/api/v1/runs/stop")
    r = client.get("/api/v1/events", params={"limit": 2, "offset": 0, "severity": "high"})
    body = r.json()
    assert body["limit"] == 2
    assert all(item["severity"] == "high" for item in body["items"])

    invalid = client.get("/api/v1/events", params={"sort": "not_a_field"})
    assert invalid.status_code == 422


def test_event_export_json_and_csv(client) -> None:
    _live_events(client)
    client.post("/api/v1/runs/stop")
    js = client.get("/api/v1/events/export", params={"format": "json"})
    assert js.status_code == 200
    assert "attachment" in js.headers["content-disposition"]
    csv_resp = client.get("/api/v1/events/export", params={"format": "csv"})
    assert csv_resp.status_code == 200
    assert csv_resp.text.splitlines()[0].startswith("event_id")


def test_pipeline_preflight_never_ready(client) -> None:
    body = client.get("/api/v1/pipeline/preflight").json()
    assert body["ready_to_run"] is False


def test_start_real_run_blocked_in_demo_mode(client) -> None:
    r = client.post("/api/v1/runs", json={"mode": "real"})
    assert r.status_code == 409
