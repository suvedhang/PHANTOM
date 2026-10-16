# Rules

PHANTOM ships a deterministic rule engine (`apps/api/phantom_api/rule_engine/engine.py`).
A rule is a versioned definition referencing a region (where applicable) and a
configuration with thresholds. Each triggering frame is evaluated; persistent
conditions emit at most one lifecycle per `dedup_key`.

## Supported rule types

Only these five types are executed by the engine. Any other type is rejected at
validation time with a clear message.

| Type | Requires | Config | Fires while… |
| --- | --- | --- | --- |
| `region_entry` | region | `region_id`, optional `class_filter` | a matching track is inside the region |
| `region_exit` | region | `region_id`, optional `class_filter` | a matching track transitions out of the region |
| `dwell_time` | region | `region_id`, `dwell_seconds > 0` | a matching track has been inside the region for at least `dwell_seconds` |
| `wrong_way` | — | `allowed_direction_deg`, `min_displacement > 0` | a track's displacement exceeds `min_displacement` and its bearing deviates more than 150° (180° − 30° tolerance) from `allowed_direction_deg` |
| `count_threshold` | region | `region_id`, `count_threshold > 0`, `sustain_seconds > 0` | the number of matching tracks inside the region stays `>= count_threshold` for `sustain_seconds` |

`SUPPORTED_RULE_TYPES` is enforced at rule creation and re-checked at runtime;
an unsupported type is skipped rather than crashing the pipeline.

## Rule configuration fields

| Field | Meaning |
| --- | --- |
| `region_id` | Region the rule applies to (required for all but `wrong_way`) |
| `class_filter` | Optional set of class labels to match |
| `dwell_seconds` | Required threshold for `dwell_time` |
| `allowed_direction_deg` | Expected heading in image space for `wrong_way` |
| `min_displacement` | Minimum image-space movement before `wrong_way` can trigger |
| `count_threshold` | Entity count threshold for `count_threshold` |
| `sustain_seconds` | How long the condition must hold continuously |
| `cooldown_seconds` | Re-trigger suppression window after an event clears |
| `dedup_seconds` | Minimum interval between `update` emissions while active |

## Lifecycle and de-duplication

- The engine keys active violations by `dedup_key` = `"{rule_id}:{track_id}"`
  (count rules use `"{rule_id}"`).
- First frame the condition holds → one `create`.
- While active, at most one `update` per `dedup_seconds`; later frames are
  suppressed until the interval elapses.
- When the condition no longer holds, a `clear` is emitted and a cooldown timer
  starts. Re-triggering is suppressed until it expires.
- A persistent condition does **not** re-`create` every frame.

The event service must be told the assigned event id for the clear to be
persisted: `RuleEngine.set_event_id(dedup_key, event_id)`. Cooldown is set on
clear even when no `event_id` exists (for example, an event that was never
persisted).

## Geometry

All geometry is image-space and normalized (`[0,1]`, origin top-left):

- A track's point is the **center of its bounding box**.
- Region containment uses ray-casting point-in-polygon (mirrored in
  `apps/web/src/lib/geometry.ts` for the UI overlay).
- Bearing is measured in image space; `wrong_way` compares bearing to the
  allowed direction with a 30° tolerance, so "wrong way" requires the track to
  be heading clearly opposite (deviation > 150°).

## Track history and stale expiry

- Each track keeps up to `HISTORY_LENGTH` (60) timestamped positions.
- A track unseen for more than `stale_track_seconds` (default 4.0) is dropped,
  along with its region membership and dwell bookkeeping.
- A rule deleted while its violation is active emits a `clear` with reason
  `rule_removed`.

## Limitations

- **Image-space only.** Directions and displacements are not in world metres;
  `wrong_way` compares bearings in the image plane.
- **Center-point membership.** Region tests use the bbox center, not full
  polygon overlap; a partially-entered object may not register.
- **Fixed tolerance.** The wrong-way tolerance (30°) and the stale-track window
  are documented constants, not per-rule tuning.
- **No cross-track correlation** beyond counting; rules do not model object
  identity across camera cuts.
- **Mock data is simulated.** Rule outcomes in demo mode reflect the scripted
  scenario, not real-world behaviour.
