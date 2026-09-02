FINAL THESIS TESTS — TEST 2 AND TEST 3
=====================================

Purpose
-------
This package continues the comparative thesis design after the completed pilot.

TEST 2 — Controlled architecture comparison
Primary arms:
  A. Embedded IFC
  B. Native IFC external reference -> JSON
  D. Custom IFC link -> RDF
Sensitivity arm:
  C. Native IFC external reference -> the SAME RDF registry used by D

This isolates:
  A vs B: effect of externalisation
  B vs C: effect of RDF while keeping IFC-native carrier constant
  C vs D: effect of the custom IFC-side carrier while keeping RDF constant

Scenarios:
  1. Initial five-question retrieval
  2. Acoustic-value update
  3. Provenance/source update
  4. External resource unavailable, with IFC-side identifiers UNCHANGED
  5. IFC-side overhead
  6. Native-reference-to-same-RDF sensitivity arm

The old geometry-shift scenario is intentionally excluded from the final experiment.

TEST 3 — Mapping and semantic robustness
Cases:
  - controlled acceptable match
  - actual Bau 1 metal-stud ambiguous match
  - actual concrete wall intentionally linked to incompatible record
  - actual unmatched wall
  - controlled multiple-candidate case
  - external resource unavailable/broken
  - controlled semantically stale association

Important: Test 3 evaluates reference correspondence. It does NOT predict acoustic
performance and does not claim that the VaBDat Rw value is an in-situ Bau 1 value.

Where to copy the files
-----------------------
Copy these three Python files beside your existing project run_experiment.py, e.g.:

E:\thesis\thesis_experiment_vscode\thesis_experiment_vscode\
    run_experiment.py
    run_test2_final_architecture.py
    run_test3_semantic_robustness.py
    data\

Required data\ files
--------------------
HFT_Bau1_2026.02.18.ifc
HFT_Bau1_baseline_embedded.ifc
HFT_Bau1_baseline_native_reference.ifc
HFT_Bau1_baseline_proposed_ifc_rdf.ifc
native_external_record_v1.json
acoustic_registry_v1.ttl

Run Test 2 first
----------------
Activate the existing virtual environment, then:

python .\run_test2_final_architecture.py

Results go to:
  final_test2_results\

Key files:
  test2_initial_retrieval.json
  test2_ifc_overhead.csv
  test2_provenance_structure.csv
  test2_scenario_results.csv
  test2_summary.txt
  HFT_Bau1_sensitivity_native_to_same_rdf.ifc

Only after reviewing Test 2, run Test 3
---------------------------------------
python .\run_test3_semantic_robustness.py

Results go to:
  final_test3_results\

Key files:
  test3_semantic_robustness_results.csv
  test3_semantic_robustness_details.json

Methodological notes
--------------------
1. 5/5 retrieval means the five queries are answerable. It does NOT mean that the
   source contains complete method/provenance/context information.
2. The corrected external-resource test never changes the IFC URI/reference. The
   external resource alone is made unavailable.
3. Native->same-RDF is a sensitivity arm, not a fourth primary baseline.
4. RDF/PROV-O structure and custom IFC linking are evaluated separately.
5. File-size overhead is secondary; entity/property counts are more structural.
6. The current pilot IFCs may still use legacy names Pset_AcousticEmbedded and
   Pset_AcousticLink. The final thesis should document HFT_AcousticEmbedded and
   HFT_AcousticLink as the intended user-defined names because the Pset_ prefix is
   reserved for standardized property sets. The scripts retain legacy compatibility
   so your already-generated pilot IFCs remain usable.
