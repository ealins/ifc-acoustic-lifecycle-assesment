# FAIR-Support Assessment

FAIR is used in two ways: as a design framework for the metadata/package architecture and as an evaluation lens through selected criterion-level indicators. The prototype does **not** provide FAIR certification or universal FAIR-compliance claims.

## Criterion result model

Each criterion records an ID, FAIR dimension, label, requirement/priority, status, evidence, evidence source, missing information, recommendation, assessment method, machine-checkable flag and manual-review flag.

Statuses are `PASS`, `PARTIAL`, `FAIL`, `NOT_APPLICABLE`, `NOT_VERIFIED`, and `MANUAL_REVIEW`.

## Findable

Selected checks cover package identity, distinction between local/prototype identifiers and registered/resolvable identifiers, descriptive metadata, acoustic dataset identifier, IFC GlobalId, asset indexing, package version and local catalog identity/discovery.

## Accessible

Selected checks cover retrieval of packaged assets, explicit external URIs, URI syntax, separately recorded reachability status, access rights, metadata retention and documented access method. A URI string is never treated as proof that a remote resource is reachable.

## Interoperable

Selected checks cover declared IFC schema, acoustic format/media type, parseable RO-Crate-style JSON-LD, parseable RDF/Turtle, explicit qualified relationships, units when relevant, declared vocabularies/profile, and optional IDS/bSDD references. RDF existence alone is not sufficient to pass the whole dimension.

## Reusable

Selected checks cover creator/responsible agent, provenance, dataset-origin classification, method/instrument when conditionally relevant, source/package versions, licence/reuse conditions, quality/limitations, relationship rationale/evidence, intended reuse and citation information.

Reusability support does not prove scientific acoustic validity for a new component or design case.

## Overall labels

Current non-certifying readiness labels include `READY_FOR_PROTOTYPE_REUSE`, `PARTIALLY_READY`, `INSUFFICIENT_METADATA`, and `ASSESSMENT_INCOMPLETE`.

The generated report is stored as `reports/fair-support-assessment.json`. Legacy report paths are retained only for backward compatibility.
