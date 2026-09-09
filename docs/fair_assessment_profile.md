# Prototype FAIR-Support Assessment Profile

## Scope

This profile applies a bounded set of transparent checks to the Acoustic Component Research-Object Profile. It is an **evidence-based FAIR-support assessment**, not a certification of FAIR compliance and not an assessment of acoustic scientific validity.

Overall labels are:

- `READY_FOR_PROTOTYPE_REUSE`
- `PARTIALLY_READY`
- `INSUFFICIENT_METADATA`
- `ASSESSMENT_INCOMPLETE`

Criterion statuses are:

- `PASS`
- `PARTIAL`
- `FAIL`
- `NOT_APPLICABLE`
- `NOT_VERIFIED`
- `MANUAL_REVIEW`

Each result stores criterion ID, FAIR dimension, requirement, priority, status, evidence, evidence source, missing information, recommendation, assessment method, machine-checkability, and whether manual review is required.

## Findable

Selected indicators check that:

1. the package has an explicit identifier;
2. identifier type is distinguished (local/prototype URI, URN, repository URI, DOI where genuinely supplied);
3. package metadata identify the research object;
4. acoustic datasets have explicit identifiers;
5. the selected IFC component has a GlobalId where applicable;
6. packaged assets are indexed;
7. the object has a local catalog identity;
8. version is explicit; and
9. descriptive metadata support discovery.

A local package ID or prototype URI is never described as a DOI.

## Accessible

Selected indicators check that:

1. packaged primary assets can be retrieved from the archive;
2. external references use valid URI syntax;
3. external reachability is explicitly `verified`, `failed`, or `not tested`;
4. access rights/conditions are documented;
5. portable metadata remain in the package; and
6. the access method is explicit.

A URI string alone is not evidence that an external resource is reachable.

## Interoperable

Selected indicators check that:

1. IFC format/schema evidence is declared when extractable;
2. acoustic media type and inspected structure are declared;
3. `ro-crate-metadata.json` is valid structural JSON-LD;
4. domain Turtle parses;
5. component and acoustic dataset are linked through a qualified relationship entity;
6. units are documented where relevant;
7. the prototype profile/vocabularies are declared; and
8. IDS/bSDD references, when supplied, remain optional references requiring actual validation rather than fabricated semantics.

RDF or JSON-LD presence alone does not imply interoperability.

## Reusable

Selected indicators check that:

1. creator/responsible agent is documented;
2. provenance is documented;
3. acoustic-data origin is classified;
4. method is documented when applicable;
5. instrument context is documented for physical measurements when applicable;
6. package/source versions are distinguished;
7. licence/reuse terms are documented;
8. quality, uncertainty, or limitations are available;
9. relationship rationale is explicit;
10. structured relationship evidence exists;
11. intended reuse is stated;
12. citation information can be supplied; and
13. domain-scientific metadata completeness is exposed as a manual-review concern rather than treated as scientific validity.

## Priority behavior

`prototype required` criteria can block reuse readiness. `conditionally required` criteria apply only when their precondition is present (for example external URI reachability or instrument context for physical measurements). `recommended` criteria can reduce readiness without making the object structurally invalid. `optional` criteria remain visible but do not prevent the package from receiving a prototype reuse-ready label.

## Limitations

- No external FAIR certification is performed.
- URI reachability is not inferred from URI syntax.
- The profile does not prove that an acoustic value is correct or suitable for a design decision.
- Metadata completeness is distinct from acoustic scientific validity.
- Criteria reflect the selected IFC/acoustic research-object use case and are not universal FAIR metrics.
