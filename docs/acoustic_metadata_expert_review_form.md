# Acoustic Metadata Profile — Expert Review Form

This form is preparation for future acoustic-domain review. Its presence does **not** mean that expert validation has occurred.

## Reviewer information

- Reviewer name:
- Organization:
- Relevant expertise:
- Review date:
- Profile version reviewed:
- Package/example case reviewed:

## 1. Package and component identification

- Are the package and acoustic dataset identifiers sufficient for the intended research use case?
- Is IFC GlobalId/component context sufficient to identify the represented component without duplicating complete geometry?
- Missing or ambiguous fields:
- Recommended changes:

## 2. Dataset-origin classification

For each origin (`RAW_MEASUREMENT`, `PROCESSED_MEASUREMENT`, `DERIVED_RESULT`, `SIMULATION_RESULT`, `MANUFACTURER_VALUE`, `REFERENCE_VALUE`, `CATALOG_RECORD`, `PREDICTED_VALUE`):

- Is the category understandable?
- Are categories sufficiently distinct?
- Are any categories missing or overlapping?
- Recommended changes:

## 3. Measurement/generation context

- Are method/instrument/calibration/conditions fields appropriate for direct measurements?
- Are processing/derivation fields sufficient for processed or derived records?
- Are simulation-result provenance fields sufficient for documenting imported results without implementing simulation?
- Which fields should be required, conditional, recommended or optional?

## 4. Quality and reuse context

- Are uncertainty, quality notes, limitations, intended/unsupported uses and validation-status fields sufficient for reuse decisions?
- Which fields require domain-specific vocabularies?
- Which fields cannot be evaluated automatically?

## 5. Component-dataset relationship

- Are the controlled relationship types semantically distinguishable?
- Is `MEASURED_ON` sufficiently restricted to evidence of actual measurement?
- Is the evidence-item model understandable and auditable?
- Are the lifecycle states/actions useful to a domain researcher?

## 6. FAIR-support and completeness separation

- Is the distinction between metadata completeness and selected FAIR support clear?
- Are any FAIR-support criteria overclaiming accessibility, interoperability or reuse?
- Does the application clearly avoid equating metadata completeness with scientific validity?

## 7. Overall assessment

- Critical changes required before prototype evaluation:
- Recommended changes:
- Optional improvements:
- Fields suitable for automated extraction:
- Fields that should always require human/source confirmation:
- Additional comments:

## Review outcome

- [ ] Reviewed with no critical metadata-profile changes requested
- [ ] Reviewed with changes requested
- [ ] Review incomplete

Reviewer signature/record reference (if applicable):
