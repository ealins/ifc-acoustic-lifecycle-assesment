# Evaluation protocol: SLDV application profile

Use a fixed baseline package and record profile/software versions, input checksums, expected and observed outcomes, and emitted issue codes for every run. Keep the original TXT/CSV payload unchanged.

| ID | Perturbation / condition | Expected result | Primary evidence |
|---|---|---|---|
| E01 | Complete baseline; hashes match; GlobalId resolves to expected class | Pass | JSON-LD parse, SHACL conforms, no cross-layer issues |
| E02 | Change one measurement-payload byte after sidecar generation | Fail | MEASUREMENT_HASH_MISMATCH |
| E03 | Change one IFC byte after sidecar generation | Fail | IFC_HASH_MISMATCH |
| E04 | GlobalId absent from supplied IFC | Fail | IFC_GLOBALID_UNRESOLVED |
| E05 | Sidecar GlobalId differs from resolved entity | Fail | IFC_GLOBALID_MISMATCH |
| E06 | Sidecar entity class differs from resolved IFC class | Fail | IFC_CLASS_MISMATCH |
| E07 | Remove required lab field calibrationStatus | Fail | SHACL violation for lab context |
| E08 | Invalid checksum lexical form | Fail | SHACL pattern violation |
| E09 | Measurement filename uses .h5 or .json | Reject before validation | File-gate error; no derivative created |
| E10 | Date explicitly unknown and limitation documented | Pass structural validation | Uncertainty retained, not inferred |
| E11 | Change IFC filename but retain matching bytes and identity | Pass integrity; optionally flag manifest naming discrepancy | Separates display label from byte identity |
| E12 | Malformed JSON-LD or empty RDF graph | Fail | JSON-LD/RDF parsing gate |

## Measures to report

- SHACL conformance rate: conforming records / records evaluated.
- Defect detection rate: detected injected defects / injected defects.
- False-positive count on E01 and E10.
- Cross-layer defect detection grouped by issue code.
- Execution time for JSON-LD parsing, SHACL, hashing, and GlobalId resolution, measured separately.
- Payload preservation: SHA-256 before packaging equals SHA-256 after export.
- Repeatability: identical inputs and software/profile versions produce equivalent findings. Ignore non-semantic timestamp differences when comparing generated sidecars.

For the single-specimen demonstrator, report counts and limitations rather than statistical generalisation. Negative tests should assert the expected issue code or SHACL result, not merely that an error occurred.
