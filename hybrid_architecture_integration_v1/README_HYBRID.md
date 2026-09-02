# Hybrid IFC–RDF acoustic association integration

This package keeps the v7 lifecycle logic unchanged and adds the final architecture integration.

## Architecture

1. **IFC-native technical carrier**: `IfcRelAssociatesDocument -> IfcDocumentReference.Location` contains the stable acoustic-record URI.
2. **HFT semantic anchor**: `HFT_AcousticLink` contains only `MappingSeriesURI`, `AssociationType`, and `SemanticProfile`.
3. **RDF acoustic registry**: owns acoustic values, tested assembly and provenance.
4. **RDF MappingSeries / MappingAssertion graph**: owns mutable semantic status, rationale, evidence hashes, review state and revision history.

The HFT property set intentionally does **not** duplicate `AcousticRecordURI`, `MappingStatus`, or `MappingBasis`. The stable MappingSeries URI is used rather than a particular assertion revision, so creating r2/r3/... does not require an IFC edit.

## Files

- `build_hybrid_ifc.py` — generates the hybrid IFC from an IFC containing the target wall; reuses or creates the native document association and creates the lightweight HFT semantic anchor.
- `verify_hybrid_ifc.py` — checks the IFC-side architecture.
- `run_hybrid_lifecycle_evaluation.py` — reads the acoustic URI from the native IFC reference, verifies the HFT MappingSeries anchor, then calls the unchanged v7 `run_lifecycle_evaluation.py`.
- `run_lifecycle_evaluation.py` — unchanged v7 lifecycle evaluator.
- `association_lifecycle.py` — unchanged v7 lifecycle model/history implementation.
- `vabdat_one_record_registry.ttl` — baseline acoustic RDF registry for the pilot record.

## Recommended first run

From the extracted package directory, using the supplied hybrid IFC one directory above:

```powershell
python .\verify_hybrid_ifc.py `
  --ifc ..\HFT_Bau1_hybrid_native_semantic.ifc `
  --global-id '2qL6OSUnz6ZAzEOn1HxeD2'
```

Expected checks:

- `exactly_one_native_document_reference = true`
- `native_location_present = true`
- `hft_anchor_present = true`
- `mapping_series_uri_present = true`
- `no_duplicate_acoustic_record_uri_in_hft = true`
- `no_mutable_mapping_status_in_hft = true`
- `overall_pass = true`

Then create a **fresh** hybrid integration graph:

```powershell
python .\run_hybrid_lifecycle_evaluation.py `
  --ifc ..\HFT_Bau1_hybrid_native_semantic.ifc `
  --registry .\vabdat_one_record_registry.ttl `
  --association-graph .\association_lifecycle_hybrid_test.ttl `
  --global-id '2qL6OSUnz6ZAzEOn1HxeD2' `
  --record-version 'prototype-v1' `
  --wall-thickness 0.285 `
  --require-hft-anchor
```

Expected first-run interpretation:

- `record_uri_source = IfcDocumentReference.Location`
- `record_uri_manual_argument_used = false`
- native record URI = `https://example.org/hft-acoustic/record/vabdat-310`
- HFT MappingSeriesURI matches the wall↔record pair
- hybrid architecture check = `PASS`
- semantic status = `AMBIGUOUS` for the real Bau 1 wall/reference record case
- technical resolution = `true` as long as the record exists in the supplied registry
- a new r1 assertion is created in the fresh hybrid graph

Run the same command again. Expected result:

- `meaningful_change = false`
- `action = no_change_no_revision`

This confirms that the final integrated carrier architecture still preserves the v7 idempotency behavior.

## Build the hybrid IFC yourself

If you prefer to generate the hybrid file locally instead of using the supplied example:

```powershell
python .\build_hybrid_ifc.py `
  --ifc-in ..\ifc_rdf_steps_8_9\HFT_Bau1_baseline_native_reference.ifc `
  --ifc-out ..\HFT_Bau1_hybrid_native_semantic.ifc `
  --global-id '2qL6OSUnz6ZAzEOn1HxeD2' `
  --record-uri 'https://example.org/hft-acoustic/record/vabdat-310' `
  --record-id 'vabdat-310'
```

The builder also works when no native document association exists; in that case it creates one using the IFC schema entities.

## Research interpretation

This integration does not introduce a new semantic-assessment rule. It closes the architecture gap between Test 2 and v7:

- Test 2 supported IFC-native referencing as the technical carrier.
- Test 3 showed that technical resolution is insufficient for semantic validity.
- v1–v7 developed the MappingAssertion lifecycle layer.
- this wrapper integrates the two: the evaluator now discovers the record through the IFC-native carrier and verifies the HFT semantic anchor instead of requiring a manually entered record URI.
