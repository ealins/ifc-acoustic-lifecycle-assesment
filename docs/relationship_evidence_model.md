# Qualified Geometry-Measurement Relationship and Evidence Model

## Why the relationship is an entity

The domain claim is not simply `IfcWall linkedTo Measurement`. A measurement physically performed on an identified specimen, a derived result, a prediction, and a catalog value transferred by assembly equivalence have different evidential meanings. The prototype therefore models the relationship as `GeometryMeasurementRelationship` with its own identifier, type, rationale, source versions, evidence, review history, and reassessment triggers.

## Relationship types

| Type | Meaning | Evidential implication |
|---|---|---|
| `measuredOn` | physical measurement was performed on the identified specimen/component | strongest direct identity claim; still requires source evidence |
| `characterizes` | data characterize the selected component within a stated scope | may be direct or indirect; rationale required |
| `derivedFromMeasurementOf` | result derives from a measurement of the component/specimen | derivation/provenance must be visible |
| `applicableToEquivalentAssembly` | data are transferred from a justified equivalent assembly | matching and excluded attributes are central; not a direct measurement claim |
| `predictedFor` | data are predicted/simulated for the component | not a physical measurement |
| `references` | informational association only | no characterization claim implied |
| `unknownRelationship` | semantics not established | requires review before strong reuse claims |

## GeometryMeasurementRelationship fields

`relationship_id`, `subject_component_id`, `subject_ifc_global_id`, `subject_ifc_file_id`, `object_measurement_id`, `relationship_type`, `scope`, `rationale`, `evidence`, `matching_attributes`, `excluded_attributes`, `confidence_basis`, creation/approval/review provenance, `relationship_version`, `source_component_version`, `source_measurement_version`, lifecycle `status`, `trigger_history`, `decision_history`, `supersedes_relationship`, `invalidated_by`, and notes.

The prototype does not calculate a scientifically meaningful confidence score. `confidence_basis` may describe the basis for a human judgment, while evidence statuses remain transparent.

## EvidenceItem

Each item contains:

- `evidence_id`
- `evidence_type`
- `observed_value`
- `expected_value`
- `comparison_result`
- `source_asset`
- `source_location`
- `created_at`
- `created_by`
- `reliability`
- `notes`

Controlled comparison statuses:

- `SUPPORTS`
- `CONTRADICTS`
- `MISSING`
- `NOT_APPLICABLE`
- `NOT_VERIFIED`
- `REQUIRES_REVIEW`

Typical evidence types include specimen/test-report identifiers, IFC GlobalId, assembly identifier, material-layer match, thickness match, dimensions, construction type, manufacturer/product, project location, laboratory specimen reference, measurement grid, source-document reference, manual expert approval, and algorithmic candidate match.

## Transparent decision principle

The application may summarize evidence counts and highlight contradictions, but it does not transform those counts into an unvalidated numerical confidence score. A direct `measuredOn` relationship with supporting specimen/report evidence is qualitatively different from `applicableToEquivalentAssembly` even when both have several `SUPPORTS` items.

## Versioning and lifecycle

A relationship records the component and measurement source versions on which approval was based. Material source changes can create explicit `ReassessmentTrigger` records. Relationship target changes should be treated as retargeting/new-version events rather than invisible edits.

The pre-existing `MappingSeries` / immutable `MappingAssertion` lifecycle machinery remains the authoritative technical stewardship engine. `GeometryMeasurementRelationship` is the domain-facing qualified claim; the stewardship adapter records engine decisions and triggers against that claim rather than renaming or removing the original lifecycle concepts.
