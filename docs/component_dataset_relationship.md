# Component-Dataset Relationship Model

## Purpose

An IFC model and an acoustic record can exist independently. Reuse requires an explicit, reviewable claim explaining which dataset concerns which IFC component and why.

The prototype represents that claim with `GeometryMeasurementRelationship`. Existing internal association/lifecycle code is retained for backward compatibility, while visible terminology uses **Component-Dataset Relationship** or **Geometry-Measurement Relationship**.

## Controlled relationship types

- `MEASURED_ON` (`measuredOn`) — direct/processed physical measurement data associated with the represented component/specimen. This type is restricted to measurement-origin data.
- `CHARACTERIZES` — the record characterizes the component without necessarily proving a direct specimen measurement.
- `DERIVED_FROM_MEASUREMENT_OF` — a derived result whose provenance traces to a measurement of the component/specimen.
- `PREDICTED_FOR` — prediction/simulation result for the component.
- `APPLICABLE_TO_EQUIVALENT_ASSEMBLY` — transfer-by-equivalence claim; matching and excluded attributes must be explicit.
- `REFERENCES` — weaker reference/catalog relationship that does not assert direct measurement.
- `UNKNOWN_RELATIONSHIP` — relationship semantics are not yet resolved.

A catalog, manufacturer, reference, or simulation result cannot be silently promoted to `MEASURED_ON`.

## Relationship fields

The domain record includes relationship ID, component ID/GlobalId/IFC asset, acoustic dataset ID, type, scope, rationale, structured evidence, source IFC and dataset versions/checksums, creator/reviewer, approval fields, relationship version, lifecycle status, decision history, trigger history, supersession and invalidation references, notes and recommended action.

## Evidence items

Evidence is transparent and qualitative; no arbitrary confidence score is introduced. Evidence types may include specimen/report identifiers, IFC GlobalId correspondence, assembly/type/material/layer/thickness/dimension correspondence, manufacturer/product/project/location correspondence, related document, expert approval, algorithmic candidate match, or explicitly unknown evidence.

Statuses are:

- `SUPPORTS`
- `CONTRADICTS`
- `MISSING`
- `NOT_APPLICABLE`
- `NOT_VERIFIED`
- `REQUIRES_REVIEW`

Each `EvidenceItem` records an evidence ID, type, observed and expected values, source asset/location, comparison result, qualitative reliability category, creator/reviewer where supplied, timestamp and notes.

## Decision semantics

Metadata completeness and relationship validity are independent. Missing licence metadata can make reuse metadata incomplete while the relationship remains acceptable. Conversely, a relationship can be invalid while metadata completeness remains high.

Direct evidence does not establish universal scientific suitability for reuse in another building component.

## Version and reassessment

The relationship records the source IFC/dataset versions used for the decision. Reassessment triggers capture relevant changes and append lifecycle/stewardship history rather than mutating away prior evidence.
