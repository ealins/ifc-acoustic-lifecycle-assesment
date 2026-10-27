# Thesis validation walkthrough: code, evidence, and interpretation

This document is the implementation-level companion to the thesis evaluation protocol. It explains what each stage does, what it proves, what it does not prove, and which evidence must be retained.

## 1. Research claim and boundary

The demonstrator tests whether a measurement record can be linked reproducibly to an IFC component through a versioned, machine-checkable application profile. It has exactly three authoritative inputs:

1. The original SLDV TXT/CSV bytes.
2. Laboratory context recorded from the experiment (including explicit unknowns).
3. The IFC file bytes and selected component identity.

The JSON-LD sidecar, hashes, RDF graph, validation reports, package manifest, and diagnostic summaries are derived artifacts. They must not be described as additional authoritative measurement sources. No HDF5 or alternate numerical container is created.

A conforming package does not prove that the experiment was correctly performed, that the measured component physically corresponds to the selected IFC component, or that the scan coordinate frame is registered to the IFC frame. Those require separate experimental evidence.

## 2. Execution path

### Stage A — Input gate and source preservation

**Implementation:** `dashboard/ui/research_builder.py` and `fair_platform/sldv_payload.py`.

The dashboard accepts the measurement payload as uploaded bytes. The file suffix is checked against `.txt` and `.csv`. The inspector decodes a separate in-memory text view for diagnostics (UTF-8 first, then CP1252, then Latin-1), while the original bytes remain unchanged for packaging and hashing.

The inspector detects a legacy `Point Index: ... [x = ... y = ... z = ...]` header where present, counts rows that are fully numeric, reports rectangularity and reports a candidate first-column axis only when enough numeric rows exist. It does not assume every first column is frequency, infer units, or infer IFC registration. Delimiter and decimal conventions are heuristic and must be recorded as parser diagnostics, not treated as ground truth.

**Evidence:** original byte size and SHA-256; `reports/sldv-payload-analysis.json`; post-export checksum comparison.

**Pass condition:** exact source bytes are preserved and unsupported extensions are rejected before profile construction.

**Failure modes:** unsupported extension, empty/unparseable numeric section, irregular numeric rows, or ambiguous delimiter. Some are warnings rather than fatal errors because header conventions vary by acquisition software.

### Stage B — Laboratory-context mapping

**Implementation:** `dashboard/ui/research_builder.py`, mapping dashboard metadata to the profile fields consumed by `build_sidecar()`.

The profile records method, instrument, operator, measurement date, calibration status, scan setup, measured quantity, unit, processing description, and limitations. Missing facts must not be fabricated. They should be represented as the profile's explicit `unknown` token and explained in `limitations`.

The mapping is a consequential transformation: the thesis must state which source metadata field populates each profile field. A syntactically valid string is not proof that the scientific value is correct. In particular, date input must be normalized to the profile's declared format (ISO `YYYY-MM-DD` or `unknown`) or the validation report must explain why it is invalid. Do not silently infer the measurement date from filesystem timestamps.

**Evidence:** input metadata form values, the resulting sidecar, and SHACL report.

### Stage C — IFC context and component resolution

**Implementation:** IFC inspection functions in the dashboard and `validate_sidecar()` in `fair_platform/vibrometry_sidecar.py`.

The package records the IFC filename, SHA-256 of the exact IFC bytes, schema, selected GlobalId, and entity class. The selected GlobalId and class must come from parsing the uploaded IFC, not from a user-typed guess. Cross-layer validation compares the declared values with the resolution result.

**Evidence:** IFC checksum, parser/schema information, selected GlobalId, resolved entity type, and issue codes.

**Pass condition:** the identifier resolves in the supplied model and the resolved class agrees with the sidecar.

**Important limitation:** a matching GlobalId and hash establish which model/component record was referenced. They do not prove physical alignment between measurement coordinates and IFC geometry. Any scan-to-IFC transformation remains unconfirmed unless independently measured and evaluated.

### Stage D — Sidecar construction and integrity metadata

**Implementation:** `build_sidecar()` in `fair_platform/vibrometry_sidecar.py`.

The builder creates a JSON-LD record with a profile identifier/version, stable record identifier, creation timestamp, a measurement-payload node, laboratory-context node, and IFC-link node. It computes `sha256:<64 lowercase hex characters>` over the exact measurement bytes and records the IFC hash supplied by the IFC inspection stage.

The sidecar is a description and link record, not a copy of the numeric measurement data. Hashes are byte-identity checks: any changed byte should change the digest. They do not certify the meaning or quality of the data.

**Evidence:** sidecar JSON-LD, source file hashes, byte size and profile version.

### Stage E — JSON-LD to RDF

**Implementation:** `jsonld_is_parseable()`, `query_profile_record()`, and `validate_shacl()`.

JSON-LD is parsed into an RDF graph using RDFLib. This checks whether the document can be interpreted as graph data under its context. The competency query then attempts to retrieve the record, profile, payload hash, IFC filename/hash, GlobalId and entity type from that graph.

**Pass condition:** parsing succeeds and the expected link fields can be retrieved.

**Interpretation:** a successful query demonstrates machine-queryable links, not external resolvability of every vocabulary URI and not physical correctness.

### Stage F — SHACL profile validation

**Implementation:** `shapes/vibrometry-profile.shacl.ttl`, executed by `validate_shacl()` using pySHACL.

SHACL Core constraints check required properties, cardinalities, data types, permitted values and lexical patterns. Nested node shapes check the measurement payload, lab context and IFC-link record. SHACL-SPARQL constraints check cross-field rules such as filename/media-type agreement and require limitations to explain explicit unknown laboratory values.

The output includes a conformance Boolean and a machine-readable RDF validation report with violation messages. A SHACL pass means the sidecar satisfies the encoded rules for the profile version used. It does not prove the rules are complete or the scientific facts true.

**Evidence:** profile ID/version, shapes file/version, `conforms`, report text, and result graph.

### Stage G — Cross-layer validation

**Implementation:** `validate_sidecar()` in `fair_platform/vibrometry_sidecar.py`.

These checks compare metadata against the actual bytes and IFC resolution evidence. They detect measurement hash/size mismatch, IFC hash mismatch, unresolved GlobalId, mismatched GlobalId, and mismatched entity class. These checks are separate from SHACL because SHACL cannot, by itself, prove that an external file's bytes match a declared hash or that an identifier exists in the uploaded IFC file.

**Evidence:** each issue code and message, plus the actual inputs used for the check.

### Stage H — Combined result and package export

The dashboard combines the SHACL result and cross-layer issues into a validation report and includes the sidecar and payload diagnostics in the package. The top-level `valid` flag should be read as the conjunction of the checks it actually executes—not as overall scientific validation.

Before claiming end-to-end integrity, the final exported archive must be reopened and the hashes recomputed from the packaged measurement and IFC assets. The package should retain the original source assets, sidecar, manifest, validation report, parser diagnostics, and enough software/profile version information to reproduce the result.

## 3. Evaluation matrix and expected evidence

Use `docs/vibrometry-evaluation-cases.md` as the baseline protocol. For each test, record case ID, profile version, code commit, input hashes, injected defect, expected result, observed result, issue code, runtime, and pass/fail.

- E01: unchanged valid baseline — parse succeeds, SHACL conforms, no cross-layer issues.
- E02: mutate one measurement byte — measurement hash mismatch.
- E03: mutate one IFC byte — IFC hash mismatch.
- E04: use a GlobalId absent from the IFC — unresolved reference.
- E05: change the sidecar GlobalId — GlobalId mismatch.
- E06: change the sidecar entity class — entity-class mismatch.
- E07: remove calibration status — SHACL violation.
- E08: malformed SHA-256 lexical form — SHACL violation.
- E09: use an unsupported extension — reject at input gate; do not create a converted payload.
- E10: explicit unknown date with documented limitation — structurally valid uncertainty representation.
- E11: change a display filename without changing bytes — hashes still match; report filename/manifest policy separately if relevant.
- E12: malformed JSON-LD — parsing gate fails.

Negative tests should assert the expected issue code or SHACL constraint message, not merely that some failure happened.

## 4. Thesis metrics

Report measured values from the executed test results, not estimates:

- SHACL conformance rate = conforming records / records evaluated.
- Defect detection rate = injected defects detected / defects injected.
- False positives on valid baseline and valid explicit-unknown cases.
- Detection counts grouped by issue code and validation layer.
- Separate execution times for payload inspection, hashing, JSON-LD parsing, SHACL, IFC resolution, and package verification.
- Payload preservation rate: exports whose packaged source hash equals the pre-package source hash / exports tested.
- Repeatability: equivalent findings for repeated runs using identical input bytes and software/profile versions. Compare semantic fields separately from generated timestamps.

With one specimen, report case counts and bounded conclusions. Do not generalize a small controlled test set into universal support for all vendors or all IFC models.

## 5. Known implementation caveats to close before final thesis claims

1. **Real-input evaluation:** CI fixtures are synthetic; run the protocol against the actual laboratory TXT/CSV and IFC specimen.
2. **Legacy template reconciliation:** the Library's four-tier JSON-LD template has not yet been byte-for-byte compared with the new profile. Document field mappings and deliberate omissions before claiming complete reverse-engineering.
3. **Date normalization:** the UI mapping must ensure that raw dates conform to `YYYY-MM-DD` or become explicit `unknown` with a limitation. Otherwise a real package can fail SHACL for formatting alone.
4. **Resolution provenance:** preserve explicit evidence that the selected GlobalId was resolved from the current IFC bytes at validation time. Do not substitute a Boolean that merely reflects the presence of a previously extracted GlobalId.
5. **Export round-trip:** recompute measurement and IFC hashes from the exported package, not just from in-memory upload objects.
6. **Documentation consistency:** legacy pages may still describe HDF5/VTK support for the broader platform. Distinguish those general platform capabilities from this thesis-specific profile and do not imply those formats are accepted by the thesis package builder.

## 6. Reporting language

Prefer: “The record conforms to profile 0.1.0 under shapes file X, and the measurement/IFC byte-integrity and component-reference checks returned no issues for this input pair.”

Avoid: “The data are FAIR,” “the scan is registered to the wall,” or “the system is scientifically validated” unless independent evidence supports those broader claims.
