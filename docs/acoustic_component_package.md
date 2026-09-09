# Acoustic Component Research-Object / Package Model

## Primary artifact

The primary software artifact is `AcousticComponentResearchObject` (with `FairAcousticPackage` / `FairAcousticComponentPackage` compatibility names retained for existing integrations).

The object is a domain model first. A ZIP file is only an exchange serialization of that model.

## Information layers

### IFC component representation

The original IFC file remains authoritative for geometry, placement, material relationships, spatial context and component identity. The package stores the source IFC and metadata describing the selected component, including its actual GlobalId and source checksum. It does not duplicate complete IFC geometry in RDF.

### Acoustic datasets

The object can contain one primary acoustic dataset and related acoustic resources. The primary source can be packaged bytes or a metadata-only external reference. Dataset origin is explicitly classified and is not inferred from file structure.

### FAIR-oriented metadata

The package carries the executable acoustic metadata-profile version, provenance, access/rights, quality/reuse context and selected FAIR-support results.

### Qualified component-dataset relationship

The link between the selected IFC component and acoustic dataset is a versioned `GeometryMeasurementRelationship` containing relationship type, rationale, evidence, source versions/checksums, review fields and lifecycle state.

## Authoritative in-memory representation

The application model contains, among other fields:

- local package ID and optional repository/PID identifier;
- title, description and package version;
- metadata-profile ID/version;
- IFC asset/component information;
- one or more acoustic-dataset descriptions;
- provenance;
- access and rights;
- quality/reuse information;
- qualified relationships and evidence;
- metadata-completeness assessment;
- FAIR-support assessment;
- relationship-lifecycle assessment/history;
- package-validation results;
- warnings and packaged source files.

## Independent outcomes

The model intentionally keeps these outcomes separate:

1. metadata completeness;
2. selected FAIR support;
3. relationship lifecycle status;
4. acoustic scientific suitability (`NOT_ASSESSED` unless an actual external/manual assessment is recorded).

A package can therefore be metadata-complete while its relationship becomes stale, or have an acceptable relationship while reuse metadata are incomplete.

## Serialization responsibilities

1. **In-memory Python model** — authoritative application state.
2. **`ro-crate-metadata.json`** — principal portable research-object representation using a self-contained JSON-LD context and RO-Crate-style entity graph.
3. **`metadata.ttl`** — domain RDF, provenance, relationship evidence and assessment graph.
4. **`manifest.json`** — simplified derived application/compatibility index.
5. **`profiles/acoustic-metadata-profile.json`** — machine-readable snapshot generated from the executable metadata profile.

Derived representations are regenerated from the in-memory model to avoid contradictory hand-maintained values.

## External assets

For a resource whose bytes were not retrieved, the package records its URI, access metadata and version where known. It does not invent a byte size or checksum. Metadata remain portable even if an external resource later becomes unavailable.

## Scope limitation

The package model supports research-data description and stewardship. It is not a certified repository, DOI service, long-term preservation guarantee, acoustic simulation engine or automatic scientific-validity assessor.
