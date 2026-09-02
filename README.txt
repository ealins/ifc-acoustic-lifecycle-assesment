VS Code thesis experiment package

Place these files in a local data/ folder:
- HFT_Bau1_2026.02.18.ifc
- HFT_Bau1_baseline_embedded.ifc
- HFT_Bau1_baseline_native_reference.ifc
- HFT_Bau1_baseline_proposed_ifc_rdf.ifc
- native_external_record_v1.json
- acoustic_registry_v1.ttl

Then run:
  python -m venv .venv
  .venv\\Scripts\\Activate.ps1   (Windows PowerShell)
  pip install -r requirements.txt
  python run_experiment.py

Outputs are written to results/.

The controlled updates (45.0 dB, source revision, broken URIs, +0.10 m shift) are experiment manipulations only, not source data claims.
