# Association Model v5 — availability-safe lifecycle handling

This version continues directly from the v4 lifecycle graph. The evidence hash model remains version 3, so existing v4 assertions r1–r3 are compatible.

## Why v5

When an external resource becomes unavailable, inaccessible fields must not be interpreted as deleted acoustic/provenance data. v5 retains the last successfully observed record evidence and records availability separately.

Expected outage change set:
- RESOURCE_AVAILABILITY_CHANGE: record.available true -> false
- ASSESSMENT_STATE_CHANGE: status -> BROKEN
- ASSESSMENT_STATE_CHANGE: rationale -> resource unavailable

Expected unchanged restoration:
- RESOURCE_AVAILABILITY_CHANGE: record.available false -> true
- ASSESSMENT_STATE_CHANGE: status BROKEN -> prior semantic assessment after reassessment
- no acoustic/provenance content changes unless the restored record truly differs from the last-known evidence

The `history` command now also shows `technical_resolution` and `requires_review`.

## Continue an existing v4 graph

Copy `association_lifecycle_final_v4.ttl` from the v4 folder into this folder as `association_lifecycle_final_v5.ttl`, then run the outage scenario with the provenance-changed registry used for r3.
