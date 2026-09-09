# Evaluation Methodology

The prototype is evaluated through multiple independent mechanisms rather than a single FAIR score.

## A. Metadata derivation traceability

Every executable metadata-field definition records a source category and acquisition mode. Sources include IFC, source/VaBDat-style acoustic data, FAIR/design requirements, provenance requirements, access/rights requirements, package requirements, relationship requirements, domain literature inputs represented in the thesis, and explicit prototype design decisions.

The UI distinguishes automatically extracted values from user/source-entered values and never silently fills missing factual metadata.

## B. Metadata completeness

Evaluation cases cover complete, incomplete, conditionally incomplete, invalid, not-applicable and not-verified fields. Required and active conditional requirements determine the prototype completeness result; recommended coverage is reported separately.

## C. Selected FAIR-support indicators

Criterion-level Findable, Accessible, Interoperable and Reusable checks are applied with explicit evidence/status/recommendations. The result is a bounded FAIR-support assessment, not certification.

## D. Package integrity

Tests validate JSON-LD, Turtle, profile snapshot, manifest/index consistency, report-to-package identity, safe relative paths, packaged assets and SHA-256 checksums. External assets that were not retrieved receive no invented checksum.

## E. Relationship traceability

Tests confirm that the package identifies the selected IFC GlobalId, acoustic dataset ID, relationship type, rationale, evidence, source versions and relationship history.

## F. Controlled lifecycle scenarios

Automated regression scenarios cover:

1. complete prototype record;
2. missing licence;
3. missing direct-measurement method/instrument context;
4. catalog record without direct measurement evidence;
5. relevant IFC component change;
6. missing/unreachable acoustic resource;
7. multiple candidate records;
8. invalid relationship evidence/status.

These scenarios verify that metadata completeness, FAIR support and lifecycle state remain independent.

## G. Library usability

The prototype library is tested for listing/search, GlobalId lookup, component/record/origin filters, metadata-completeness filters, FAIR-support filters, relationship/lifecycle filters, inspection of provenance/relationships/RDF/JSON-LD and ZIP download.

## H. Expert-review preparation

`docs/acoustic_metadata_expert_review_form.md` provides a structured review form for a future building-acoustics/domain expert. The repository does not claim expert validation unless a real completed review is supplied.

## Verification gates

CI performs syntax compilation, imports, the complete pytest suite, a metadata-profile/package export smoke test, JSON-LD/Turtle/checksum verification and headless Streamlit health startup. Test results are reported exactly rather than inferred.
