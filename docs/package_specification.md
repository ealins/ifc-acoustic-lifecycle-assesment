# Acoustic Component Package Specification

## Scope

This specification describes the prototype exchange layout for an `AcousticComponentResearchObject`. The domain object is primary; the ZIP archive is one exchange serialization.

## Recommended archive layout

```text
acoustic-component-package/
├── ro-crate-metadata.json
├── metadata.ttl
├── manifest.json
├── profiles/
│   └── acoustic-metadata-profile.json
├── geometry/
│   └── source-model.ifc
├── measurements/
│   ├── primary-acoustic-record.*
│   └── related-acoustic-records.*
├── evidence/
│   └── relationship-evidence.json
├── reports/
│   ├── metadata-completeness-assessment.json
│   ├── fair-support-assessment.json
│   ├── relationship-lifecycle-assessment.json
│   └── package-validation.json
├── checksums/
│   └── sha256sums.txt
└── README.txt
```

Legacy report paths remain temporarily available for backward compatibility.

## Serialization authority

1. The in-memory Python domain model is authoritative during application execution.
2. `ro-crate-metadata.json` is the principal portable research-object representation.
3. `metadata.ttl` contains domain RDF, provenance, qualified relationship/evidence and assessment entities.
4. `manifest.json` is a simplified derived application/compatibility asset index.
5. `profiles/acoustic-metadata-profile.json` is generated from the executable profile registry in `fair_platform/metadata_profile.py`.

Derived files are regenerated from the in-memory model. They must not be independently edited as competing authorities.

## Local assets

For a local embedded asset the manifest/RO model records, where applicable:

- asset ID;
- role;
- safe relative path;
- original filename;
- media type;
- byte size;
- SHA-256 checksum;
- source/dataset version.

The complete IFC file remains authoritative for geometry. Metadata identify/summarize the selected component without duplicating complete geometry.

## External assets

A metadata-only external acoustic resource records:

- asset/dataset ID;
- role;
- source URI;
- media type when known;
- access rights;
- reachability/access status;
- last access-check timestamp when a check occurred;
- source version when known.

If source bytes were not retrieved, the package must not fabricate a byte size or checksum. Metadata can remain available even if the data become unavailable.

## Required package relationships

The portable metadata must resolve:

- root research object → IFC source;
- root research object → selected IFC component;
- root research object → acoustic dataset(s);
- selected component ↔ acoustic dataset through an explicit qualified relationship;
- relationship → evidence items;
- package → metadata-completeness report;
- package → FAIR-support report;
- package → relationship-lifecycle report;
- package → profile version;
- provenance entities/activities where supplied.

## Integrity rules

Validation checks include safe relative paths, asset existence, no path traversal, checksums for retrieved local assets, no fabricated external checksums/sizes, JSON-LD parsing, Turtle parsing, metadata-profile snapshot version, relationship references, evidence-source references, source-version consistency and report-to-package identity.

`checksums/sha256sums.txt` excludes self-referential checksum/manifest cycles. Checksums are independently recalculable from the archive bytes.

## Assessment separation

The package stores these outcomes independently:

- metadata completeness;
- selected FAIR support;
- relationship lifecycle status;
- acoustic scientific suitability (`NOT_ASSESSED` by default).

No combined FAIR/acoustic-quality score is produced.

## Limitations

This package format is a thesis prototype profile layered on generic research-object/RO-Crate concepts. It is not a certified repository package standard, long-term preservation guarantee, universal acoustic metadata standard or scientific-validity certificate.
