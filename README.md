# VIBRO-IFC: SLDV measurements linked to an IFC model

A FAIR-oriented metadata application profile (JSON-LD sidecar and SHACL shapes) that links scanning laser Doppler vibrometry (SLDV) measurement files and laboratory context to an IFC model. The IFC is not modified. This repository holds the profile, the engine that reads and checks records, and a dashboard that shows how the architecture works.

## Architecture

| Layer | What | Notes |
|---|---|---|
| 1. Measurement data | Polytec TXT export, one file per scan point | Kept unchanged. Identified by file name and SHA-256. |
| 2. Sidecar | JSON-LD record per scan point | Built from published vocabularies (SOSA/SSN, PROV-O, DCAT, CSVW, DQV, QUDT, BOT, ISO 21597 Linkset and others). Checked by SHACL. |
| 3. IFC model | Building model | Unchanged. The element is referenced by GlobalId and file checksum. |

Blender is the visualisation. In its first version the add-on reads the sidecar for display and checks and draws from a separate view configuration. This dashboard is the engine: it reads, validates and explains the records.

## Contents

- `profile/v0.6/shapes_v0.6.ttl`: SHACL shapes. Violation = mandatory field, Warning = recommended field or known gap.
- `profile/v0.6/records/`: one record per scan point (20 records).
- `vibro_ifc/engine.py`: validation, checksum checks, declared gaps, class graph.
- `vibro_ifc/pages.py`, `vibro_ifc/app.py`: the Streamlit dashboard.
- `tests/test_sidecar_v06.py`: engine tests.

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
.\.venv\Scripts\python.exe -m pytest -q
```

To compare checksums, put the TXT files and the IFC in `data/ldv` or enter another folder in the dashboard.

## Scope

- The link is at component level. The position of the scan points on the wall is a hypothesis from the IFC model and is not confirmed by the laboratory.
- Not claimed: FAIR certification, scientific validity of the measured values, 3D registration, a change to the IFC schema.
- Known gaps in the records are listed by the records themselves (persistent identifier, licence, exact date, excitation type and others).
