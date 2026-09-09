# Acoustic Component Research-Object Package Specification

**Status:** prototype package specification, profile version 0.1.

## Package responsibilities

The research object is a structured information model, not merely a ZIP archive. The archive is one portable serialization of the in-memory domain model.

Metadata authorities are deliberately separated:

1. **In-memory domain model** — authoritative application state.
2. **`ro-crate-metadata.json`** — principal portable research-object representation using JSON-LD entity/relationship concepts.
3. **`metadata.ttl`** — domain RDF serialization for IFC identity references, acoustic data, qualified relationships, evidence, provenance, FAIR-support/lifecycle assessments, and preserved stewardship RDF.
4. **`manifest.json`** — simplified application/compatibility manifest derived from the same model.

The three files must not be independently edited as competing metadata authorities. Export regenerates them from the in-memory model.

## Preferred archive layout

```text
package-root/
  ro-crate-metadata.json
  metadata.ttl
  manifest.json
  geometry/
    <original-model.ifc>
  measurements/
    <original-acoustic-data.*>
  simulation/
    <optional solver inputs/outputs/meshes/logs>
  research/
    <optional scripts/notebooks/protocols/supporting data>
  reports/
    fair-assessment.json
    lifecycle-assessment.json
    relationship-evidence.json
    package-validation.json
  checksums/
    sha256sums.txt
  README.txt
```

The compatibility builder can still emit the historical root `geometry.ifc` and `measurement.<ext>` paths for older tests/integrations.

## Packaged assets

Each packaged source/research asset records where available:

- asset identifier;
- original filename;
- relative archive path;
- role;
- media type;
- byte size;
- SHA-256 checksum;
- source version; and
- `packaged: true`.

Relative paths must not be absolute and must not contain `..` traversal segments. Repository persistence applies the same restriction before writing nested resources.

## External assets

An external asset can be represented by URI without fabricated local bytes. External evidence should record:

- URI;
- role;
- version if known;
- access conditions;
- access status (`REACHABLE`, `UNREACHABLE`, `NOT_TESTED`/equivalent);
- status-check timestamp when a check actually occurred; and
- authentication requirements if known.

A checksum is never created for a resource that has not been retrieved. URI syntax alone is not evidence of reachability.

## Checksums

`checksums/sha256sums.txt` records SHA-256 hashes for retrievable package resources. The checksum-list file itself and the manifest are not self-hashed to avoid circular/self-referential checksum definitions. `manifest.json` exposes the same derived checksum evidence where applicable.

## Reports

### `reports/fair-assessment.json`

Stores the selected FAIR-support profile/version, assessment identity/date, overall prototype-readiness label, criterion statuses, evidence, recommendations, and limitations. It is not a certification report.

### `reports/lifecycle-assessment.json`

Stores the relationship stewardship state, MappingSeries/MappingAssertion references where generated, reassessment triggers, stewardship history, and the explicit scope note that lifecycle does not determine FAIRness or scientific validity.

### `reports/relationship-evidence.json`

Serializes qualified `GeometryMeasurementRelationship` entities and their structured `EvidenceItem` records.

### `reports/package-validation.json`

Stores structural validation results such as missing assets, unsafe paths, checksum failures, invalid RDF/JSON-LD, missing relationship rationale/evidence, and unresolved identifiers.

## `ro-crate-metadata.json`

The file uses RO-Crate-style JSON-LD entity graph concepts to represent:

- the root research object;
- profile declaration;
- IFC file and selected IFC component;
- acoustic dataset;
- research/simulation assets;
- qualified relationship and evidence entities;
- FAIR-support assessment;
- lifecycle assessment; and
- report/domain-RDF files.

The repository uses a self-contained context for offline prototype validation. This implementation should be described as **RO-Crate-style / RO-Crate-aligned prototype packaging**, not an assertion that the custom profile has been registered or approved by the RO-Crate community.

## `metadata.ttl`

Turtle uses established vocabularies where suitable (RDF, Dublin Core Terms, DCAT, PROV, Schema.org references) together with documented prototype `fairac:` terms. The system does not convert the full IFC model into RDF; the IFC component is represented using a lightweight identity/reference pattern.

## `manifest.json`

The application manifest includes:

- package/profile identity;
- synchronization/authority notes;
- indexed assets;
- geometry/acoustic resource summaries;
- relationships;
- research/simulation context;
- FAIR-support state;
- legacy FAIR compatibility evidence;
- lifecycle state/triggers;
- scientific-suitability state;
- validation evidence; and
- checksums.

It is a convenience export, not the primary portable metadata authority.

## Export validation

Strict research-object export fails when structural validation contains `ERROR` issues. Backward-compatible `export_fair_package()` continues to produce a ZIP with validation evidence even when older packages lack the new qualified relationship, allowing legacy code/tests to remain operable during migration.
