# Metadata Completeness Assessment

Metadata completeness is a primary evaluation mechanism for the acoustic metadata profile. It is intentionally separate from FAIR support, lifecycle status and scientific validity.

## Field statuses

- `PRESENT` — applicable value is present and passes the prototype field-level check.
- `MISSING` — applicable value is absent.
- `INVALID` — present value violates a prototype validation rule or controlled vocabulary.
- `NOT_APPLICABLE` — the conditional requirement does not apply to the declared record/access context.
- `NOT_VERIFIED` — a value or external condition is recorded but not independently verified.
- `MANUAL_REVIEW` — an actual expert/manual decision is required.

## Overall outcomes

- `COMPLETE_FOR_PROTOTYPE` — all active prototype-required and conditionally-required fields are satisfied. Recommended coverage is reported separately.
- `PARTIALLY_COMPLETE` — required metadata are missing/invalid but the failure is not marked interpretation- or reuse-critical.
- `INSUFFICIENT_FOR_INTERPRETATION` — one or more active interpretation-critical fields are missing/invalid.
- `INSUFFICIENT_FOR_REUSE` — one or more active reuse-critical fields are missing/invalid.
- `VALIDATION_INCOMPLETE` — active required fields need verification or manual review.

## Reported counts

The report may show counts such as metadata fields completed, required fields satisfied, active conditional requirements, recommended fields present, invalid values, unverified values and manual-review fields. These are descriptive counts only.

They are never labelled a FAIR compliance score, acoustic-quality score or scientific-validity score.

## Conditional examples

- direct/processed measurements require measurement method and instrument context;
- processed/derived results require processing/derivation context;
- simulation/prediction results require generation software/provenance context;
- manufacturer values require manufacturer provenance;
- metadata-only external resources require an external URI/access context, while local byte size/checksum/path become not applicable;
- restricted access activates authentication metadata;
- embargoed access activates embargo information.

## Independence

A record can be metadata-complete and relationship-stale. A relationship can be acceptable while licence metadata are incomplete. Completeness does not establish whether the supplied acoustic values are scientifically valid for another design case.

The generated report is stored as `reports/metadata-completeness-assessment.json` and links to the package ID and metadata-profile version.
