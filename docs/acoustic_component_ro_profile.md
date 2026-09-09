# Prototype Acoustic Component Research-Object Profile

**Profile identifier:** `https://example.org/fair-acoustic/profile/acoustic-component-ro/0.1`

**Status:** research prototype. This is not an approved RO-Crate community profile or universal acoustic metadata standard.

## Purpose

The profile defines the minimum information model used by this repository to connect a selected IFC component with acoustic data while retaining explicit evidence about why the relationship is defensible. RO-Crate concepts provide the generic portable graph/package baseline; domain-specific terms describe IFC identity, acoustic-data origin, relationship evidence, FAIR-support assessment, and lifecycle stewardship.

## Authority and synchronization

1. The in-memory `AcousticComponentResearchObject` model is authoritative during application execution.
2. `ro-crate-metadata.json` is the principal portable research-object representation.
3. `metadata.ttl` is the domain-specific RDF/provenance/stewardship serialization.
4. `manifest.json` is a simplified application compatibility manifest derived from the same model.

No derived serialization may silently invent values missing from the in-memory model.

## Entity types

| Entity | Purpose | Prototype required properties | Recommended / conditional properties | Identifier strategy | Source / validation |
|---|---|---|---|---|---|
| `AcousticComponentResearchObject` | Root research asset | package ID, title, version, selected IFC component, primary acoustic dataset | external PID, creator, licence, access rights, citation | local package ID plus optional user/repository PID | domain model; package validator |
| `IfcModel` | Original IFC source | packaged/reference path, media type, checksum when packaged | schema, model version | asset path/URI | IfcOpenShell + checksum |
| `IfcComponent` | Selected component identity | IFC GlobalId, entity type, source IFC | name, type assignment, materials, thickness, spatial context | GlobalId scoped to source model | IfcOpenShell resolution |
| `MeasurementDataset` | Acoustic data asset | dataset ID, media type, origin classification, source asset/reference | method, quantity, units, frequency range, report, version | user/repository identifier; asset path | safe structural inspection + user metadata |
| `MeasurementActivity` | Activity producing a physical measurement | link to dataset/component where known | method, standard, date, operator, environment, boundary/excitation conditions | package fragment/URI | user/source metadata |
| `Instrument` | Acquisition equipment | identifier/name when instrument context is applicable | configuration, calibration reference | package fragment/external URI | user/source metadata |
| `Person` | Researcher/operator/reviewer | name when acting as responsible agent | ORCID, affiliation | ORCID or package fragment | user/source metadata |
| `Organization` | Lab/institution/publisher | name when supplied | identifier/URI | external URI/package fragment | user/source metadata |
| `MetadataRecord` | Domain RDF serialization | path, media type | checksum | asset path | RDF parser |
| `GeometryMeasurementRelationship` | Qualified claim connecting component and acoustic dataset | relationship ID, component ID, measurement ID, type, rationale, source versions | scope, matching/excluded attributes, review/approval, evidence | `REL-*` local ID or external URI | relationship validator |
| `EvidenceItem` | Structured reason for relationship | evidence ID, type, comparison status | values, source asset/location, creator, reliability, notes | `EVI-*` local ID | relationship validator |
| `FairSupportAssessment` | Selected FAIR indicator evidence | assessment ID/profile/version/date, criteria, summary, limitations | assessor | `FSA-*` local ID | bounded evaluator |
| `LifecycleAssessment` | Relationship stewardship decision | lifecycle status, relationship identity, decision evidence | mapping series/assertion, triggers | package fragment/mapping URI | existing lifecycle engines + adapter |
| `ReviewActivity` | Human/expert review | review date/status when review occurred | reviewer, decision, notes | package fragment | user/stewardship history |
| `SoftwareApplication` | Processing/simulation software | name/version when relevant | code repository/commit, solver module | package fragment/external URI | user/source metadata |
| `Licence` | Reuse terms | reference when supplied | rights holder/restrictions | URI or text | user/repository metadata |
| `ExternalResource` | Non-packaged asset | URI and role | access status/check time, version, access conditions | URI | syntax + optional access check |

## Relationship semantics

The following relationship types are controlled by this prototype:

- `measuredOn` — data were physically measured on the identified specimen/component.
- `characterizes` — data characterize the component under a documented scope but are not necessarily a direct physical measurement of that exact IFC instance.
- `derivedFromMeasurementOf` — the object is a derived result based on measurement of the referenced component/specimen.
- `applicableToEquivalentAssembly` — data are transferred from an explicitly justified equivalent assembly; matching and excluded attributes must be visible.
- `predictedFor` — data are a prediction/simulation for the component.
- `references` — informational reference without a characterization claim.
- `unknownRelationship` — relationship semantics have not been established.

These types are not treated as equivalent. In particular, `predictedFor` and `applicableToEquivalentAssembly` do not imply a physical measurement on the IFC component.

## Asset layout

New research-object exports prefer:

```text
package-root/
  ro-crate-metadata.json
  metadata.ttl
  manifest.json
  geometry/<original-model.ifc>
  measurements/<original-acoustic-file>
  simulation/<optional solver artefacts>
  research/<optional scripts/notebooks/supporting artefacts>
  reports/fair-assessment.json
  reports/lifecycle-assessment.json
  reports/relationship-evidence.json
  reports/package-validation.json
  checksums/sha256sums.txt
  README.txt
```

The legacy root `geometry.ifc` / `measurement.*` layout remains supported through the compatibility builder path.

## Validation behavior

Prototype validation checks structural integrity, identifiers, references, relationship evidence, checksums, RDF/JSON-LD parseability, and selected metadata requirements. It does not determine whether acoustic values are scientifically correct or suitable for a particular design decision.
