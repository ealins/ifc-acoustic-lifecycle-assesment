# Lifecycle Stewardship of Geometry-Measurement Relationships

## Scope boundary

Lifecycle stewardship evaluates whether a declared geometry-measurement relationship remains defensible as source evidence changes. It does **not** determine whether the research object is FAIR and does **not** establish acoustic scientific suitability.

The original lifecycle implementation remains authoritative. The research-object layer adds explicit relationship identity, evidence, source versions, and reassessment triggers around the preserved `MappingSeries` / immutable `MappingAssertion` machinery.

## States

| State | Meaning |
|---|---|
| `ACCEPTABLE` | Current evidence supports the declared relationship, required assets are available or appropriately referenced, and no material source change invalidates the approval. |
| `SEMANTICALLY_STALE` | References may still resolve, but source changes weaken the original rationale or make reassessment necessary. |
| `BROKEN` | A required packaged asset is missing/corrupted or a required external resource is known to be unavailable. |
| `AMBIGUOUS` | Evidence is incomplete or contradictory and no defensible automated decision can be made. |
| `MULTIPLE_CANDIDATES` | More than one acoustic record satisfies minimum candidate criteria and selection needs further evidence/review. |
| `UNMATCHED` | No candidate measurement record satisfies minimum relationship criteria. |
| `INVALID` | Available evidence directly contradicts the declared relationship. |
| `MANUAL_REVIEW` | Domain expertise or non-machine-checkable evidence is required. |

The UI may display `STALE` as a compact alias of the preserved engine state `SEMANTICALLY_STALE`, but the serialized lifecycle status retains the engine term.

## Reassessment triggers

The research-object adapter records explicit trigger objects containing trigger ID, timestamp, old/new values, affected entity, category, severity, reassessment requirement, resulting state, and recommended action.

Implemented trigger categories include:

- IFC checksum changes;
- IFC schema changes;
- selected GlobalId changes;
- IFC entity/type assignment changes;
- material/layer summary changes;
- thickness changes;
- acoustic-data checksum changes;
- acoustic-data version changes;
- acoustic-data URI changes;
- provenance changes;
- licence/access-rights changes;
- research-object profile version changes;
- relationship type changes; and
- relationship evidence changes.

Changes are classified as editorial, descriptive, access, provenance, component-semantic, measurement-content, relationship-target, profile, or review changes. Access/licence edits do not automatically create semantic staleness; they primarily require FAIR/access reassessment unless another relationship-relevant condition also changed.

## Existing lifecycle engine preservation

For Rw-oriented records, `FairStewardshipService` continues to call the existing `engine.evaluate_lifecycle()` path and therefore preserves native/Pset link checks, MappingSeries validation, IDS-style readiness, bSDD-style alignment, semantic staleness, retargeting, change events, immutable MappingAssertions, and PROV history.

For generic acoustic datasets, the existing tiered validator remains in use. `RelationshipStewardshipService` wraps these engines to attach trigger and decision evidence to the qualified `GeometryMeasurementRelationship`; it does not replace the engines.

## Dual assessment rule

A package can legitimately be:

```text
FAIR-support: READY_FOR_PROTOTYPE_REUSE
Lifecycle: SEMANTICALLY_STALE
Scientific suitability: NOT_ASSESSED
```

or:

```text
FAIR-support: PARTIALLY_READY
Lifecycle: ACCEPTABLE
Scientific suitability: NOT_ASSESSED
```

No automatic inference is made from one status to another.
