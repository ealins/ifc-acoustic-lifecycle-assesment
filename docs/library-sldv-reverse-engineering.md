# Library SLDV workflow reverse-engineering notes

## What was recovered

The Library's `build_scan_record.py` generates point-specific JSON-LD from original SLDV TXT headers and a four-tier JSON-LD template. It derives file name, byte size, SHA-256, point index, and source x/y/z coordinates from the payload; laboratory context and IFC bindings are copied from the template. The original workflow also records a scan index and deliberately keeps the scan-to-IFC frame registration as an unconfirmed hypothesis.

The dashboard integration ports the reusable, data-derived checks into `fair_platform/sldv_payload.py` rather than copying the old script's assumptions about one specimen. It does not require exactly 6,381 rows, a 20–6,400 Hz axis, or a fixed number of scan points.

## Dashboard behavior

When a TXT or CSV measurement is uploaded in **Build Component Package**, the dashboard:
- reports byte size, line count, numeric row/column structure, and whether numeric rows are rectangular;
- detects the legacy `Point Index: [x, y, z]` header when present;
- reports a possible numeric axis only as a candidate, not as a confirmed frequency axis;
- preserves the original measurement bytes;
- adds `reports/sldv-payload-analysis.json` to the generated package;
- separately validates the three-input JSON-LD sidecar with SHACL and cross-layer checks against the actual measurement and IFC bytes.

## Deliberate boundaries

- The four-tier JSON-LD from the Library is a legacy implementation reference, not automatically treated as the authoritative current profile.
- The current thesis package still has exactly three authoritative inputs: measurement TXT/CSV, lab context, and IFC context.
- No HDF5 conversion, numerical-data rewrite, or assumed coordinate transformation is introduced.
- Point coordinates extracted from a TXT header remain source-frame coordinates. They are not evidence of registration to the IFC coordinate frame.
- Missing lab facts must be supplied in the dashboard or represented explicitly as unknown; the code must not invent them.

## Evaluation

`tests/test_sldv_payload.py` covers a small legacy-style TXT file with point coordinates, a CSV with a different axis/range, and rejection of unsupported extensions. These are deliberately synthetic unit fixtures; they are not a substitute for testing with the user's new lab data through the dashboard.
