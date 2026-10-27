# FAIR-oriented SLDV application profile

**Profile identifier:** https://w3id.org/vibro-ifc/profile/0.1  
**Version:** 0.1.0 (experimental thesis profile)  
**Machine validation:** shapes/vibrometry-profile.shacl.ttl

## Purpose and boundary

The profile describes the association between exactly three authoritative inputs:

1. **Measurement payload:** the original SLDV TXT or CSV export. Its bytes remain the source of record; the workflow does not transform it into HDF5 or another numerical container.
2. **Laboratory context:** method, instrument, operator, date, calibration, scan setup, quantity, unit, processing, and limitations.
3. **IFC context:** IFC file identity and checksum, schema, selected GlobalId, and resolved entity type.

The JSON-LD sidecar links these inputs. Hashes establish byte identity, SHACL checks metadata structure, and cross-layer checks compare the declared IFC reference with the entity resolved from the supplied IFC file. A valid sidecar is not proof that the measurement itself is scientifically correct.

## Field contract

| Layer | Field | Requirement | Notes |
|---|---|---|---|
| Record | recordIdentifier | Required | Stable identifier within the package; avoid deriving identity solely from a mutable filename. |
| Record | profileVersion | Required | Exact profile version used to create the record. |
| Payload | fileName | Required | Original .txt or .csv filename. |
| Payload | mediaType | Required | text/plain or text/csv. |
| Payload | byteSize | Required | Positive integer for the exact uploaded bytes. |
| Payload | sha256 | Required | sha256: plus 64 lowercase hexadecimal characters. |
| Laboratory | method | Required | The method actually documented. |
| Laboratory | instrument | Required | Manufacturer/model or explicit unknown; include instrument identifier where available. |
| Laboratory | operator | Required | Person or responsible role as recorded in source context; apply access controls. |
| Laboratory | measurementDate | Required | ISO YYYY-MM-DD or explicit unknown. Do not infer from a file timestamp. |
| Laboratory | calibrationStatus | Required | State and evidence/date where known; otherwise unknown plus a limitation. |
| Laboratory | scanSetup | Required | Scan mode, excitation/shaker setup, point layout, and relevant acquisition settings. |
| Laboratory | measuredQuantity | Required | Quantity represented by the file; do not infer from filename alone. |
| Laboratory | unit | Required | Unit for the declared quantity, or dimensionless where appropriate. |
| Laboratory | processingDescription | Required | Processing, filters, averaging, windowing, transformations, or none documented. |
| Laboratory | limitations | Required | Known gaps and interpretation limits. |
| IFC | ifcFileName | Required | Name of the exact IFC input file. |
| IFC | ifcSha256 | Required | Hash of the exact IFC bytes supplied for resolution. |
| IFC | ifcSchema | Required | Schema declared by the file/parser, e.g. IFC4. |
| IFC | ifcGlobalId | Required | Selected component GlobalId. |
| IFC | ifcEntityType | Required | Resolved entity type, e.g. IfcWall; not a guessed type. |

A required field means the record must carry a value or explicit uncertainty token. Unknown facts must not be invented. If unknown is used, explain the consequence in limitations.

## Validation layers

1. **File gate:** accept only .txt and .csv measurement payloads; preserve exact bytes.
2. **Integrity gate:** recompute SHA-256 for measurement and IFC bytes.
3. **JSON-LD gate:** parse the sidecar to RDF.
4. **SHACL gate:** enforce required structure, checksum lexical forms, and profile conformance.
5. **SHACL-SPARQL gate:** enforce cross-field rules: filename/media-type agreement and an explicit limitations statement whenever laboratory values are recorded as `unknown`.
6. **SPARQL competency query:** return the record, original payload hash, IFC file hash, GlobalId and entity type from the JSON-LD graph. The query is provided in `queries/vibrometry-profile-competency.sparql` and its result is included in the structural validation report.
7. **IFC cross-layer gate:** resolve the GlobalId against the supplied IFC model and compare GlobalId and entity type.
8. **Package gate:** include sidecar, original inputs, manifest, and machine-readable report. The manifest identifies each packaged file and its hash.

SHACL cannot prove that a GlobalId exists in a particular IFC file or that a checksum matches file bytes. Those are procedural checks and must be reported separately.

## Constraint design and references

The executable shape uses SHACL Core for cardinality, closed shapes, lexical patterns and nested-node requirements; it uses SHACL-SPARQL only where a constraint compares multiple fields. The SPARQL competency query is an inspection aid, not a replacement for conformance or byte-level validation. These choices are based on:

- W3C, *Shapes Constraint Language (SHACL)* Recommendation: conformance and machine-readable validation reports, including SHACL-SPARQL constraints.
- W3C, *SPARQL 1.1 Query Language* Recommendation: portable RDF graph-pattern queries and `FILTER NOT EXISTS` checks.
- Wilkinson et al. (2016), *The FAIR Guiding Principles for scientific data management and stewardship*, Scientific Data 3, 160018, doi:10.1038/sdata.2016.18: qualified links, provenance and rich metadata support reuse, but do not themselves certify scientific validity.

## Versioning policy

- A patch version corrects wording or non-breaking implementation defects without changing required fields or meanings.
- A minor version may add optional properties or non-breaking shapes.
- A major version is required for renamed/removed required fields, changed semantics, or new mandatory constraints.
- Each record stores the profile version used. Revalidation under a later profile reports both profile and validator versions.
- Never silently rewrite an old sidecar to the newest profile. Preserve the original and create an explicitly versioned migration result.

## Scope limits

The demonstrator evaluates one IFC specimen and selected component links. It does not claim interoperability across all SLDV vendors, exhaustive unit ontology coverage, automatic interpretation of every TXT/CSV layout, or proof of physical correspondence based only on a matching GlobalId.
