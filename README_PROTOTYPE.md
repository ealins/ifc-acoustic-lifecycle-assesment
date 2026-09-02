# GeoBIM Semantic Lifecycle Engine - Research Prototype

**Status**: ✅ Complete and tested

## Overview

Clean research prototype for **IFC-external performance-record association lifecycle governance**.  
**Focus**: Semantic assessment + change detection (acoustic domain).  
**No RDF visualization, no dashboard** — just core engine + minimal Streamlit demo.

---

## Architecture

### Core Modules (lifecycle_engine/)

1. **assessment.py** (189 lines)
   - 3-tier semantic assessment: Technical Resolution → Structural Compatibility → Semantic Status
   - Classes: `IFCEvidence`, `RecordEvidence`, `AssessmentResult`
   - Confidence scoring: 0.95 (acceptable) → 0.70 (ambiguous) → 0.20 (invalid)
   - Thickness tolerance: 2cm default

2. **change_detector.py** (153 lines)
   - 7 change categories: IFC_EVIDENCE_CHANGE, RECORD_CONTENT_CHANGE, etc.
   - Classes: `ChangeEvent`, `ChangeReport`
   - Automatic review flags for significant changes

3. **ifc_extractor.py** (100 lines)
   - Parses your real IFC file: HFT_Bau4_2025.04.22 (514 walls)
   - Functions: `extract_walls_from_ifc()`, `sample_walls_from_ifc()`

### Demo App (demo_app.py - 208 lines)

**3-page Streamlit interface**:
- Page 1: IFC Analysis (load + extract walls from real file)
- Page 2: Semantic Assessment (run 3-tier assessment, view results)
- Page 3: Change Detection (detect changes between snapshots, export JSON)

---

## Tested & Working

✅ IFC extraction: Extracts 514 walls, sampling works  
✅ Assessment: Family + thickness matching, confidence scoring  
✅ Change detection: Multi-change scenarios, review flagging  
✅ All modules compile, no errors  

---

## Run Demo

```bash
cd e:\thesis\thesis_experiment_vscode\thesis_experiment_vscode
streamlit run demo_app.py
```

---

## Files Created

```
lifecycle_engine/
  __init__.py              # Module exports
  assessment.py            # 3-tier semantic assessment
  change_detector.py       # Change detection engine
  ifc_extractor.py         # IFC parser (uses ifcopenshell)

demo_app.py                # Streamlit app (3 pages)
```

**~650 lines total core code** — focused, clean, research-ready.
