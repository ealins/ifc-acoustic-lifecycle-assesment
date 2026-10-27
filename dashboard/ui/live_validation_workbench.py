"""Interactive, source-linked validation workbench for the thesis demonstrator.

This page reads the current Python/SHACL files at runtime and executes the
same sidecar validators used by the package builder. Defect scenarios are
controlled synthetic fixtures, not claims about the user's laboratory data.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import streamlit as st

from fair_platform.vibrometry_sidecar import (
    PROFILE_ID,
    PROFILE_VERSION,
    build_sidecar,
    jsonld_is_parseable,
    query_profile_record,
    sha256_uri,
    validate_shacl,
    validate_sidecar,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_FILES = {
    "Sidecar construction and cross-layer checks": "fair_platform/vibrometry_sidecar.py",
    "TXT/CSV source inspector": "fair_platform/sldv_payload.py",
    "SHACL application profile": "shapes/vibrometry-profile.shacl.ttl",
    "Validation test suite": "tests/test_vibrometry_shacl.py",
    "Evaluation protocol": "docs/vibrometry-evaluation-cases.md",
}


def _fixture():
    measurement = b"point,velocity\n1,0.03\n"
    ifc = b"synthetic IFC fixture bytes - not a real IFC model"
    lab = {
        "method": "3D scanning laser Doppler vibrometry",
        "instrument": "unknown",
        "operator": "unknown",
        "measurementDate": "unknown",
        "calibrationStatus": "unknown",
        "scanSetup": "declared fixture scan setup",
        "measuredQuantity": "velocity",
        "unit": "m/s",
        "processingDescription": "unknown",
        "limitations": "Synthetic validation fixture; instrument, operator and calibration are unknown.",
    }
    ifc_context = {
        "global_id": "0HAsj4B9D2bBEUfukRtNYE",
        "ifc_schema": "IFC4",
        "source_sha256": sha256_uri(ifc),
        "ifc_class": "IfcWall",
        "source_file": "fixture.ifc",
    }
    return measurement, ifc, lab, ifc_context


def render_live_validation_workbench() -> None:
    st.markdown("## Live validation workbench")
    st.caption(
        "Source-linked and executable. Changing a control reruns the checks on this page. "
        "Synthetic scenarios exercise validator behavior; they do not replace validation of the real lab TXT/CSV and IFC specimen."
    )
    measurement, ifc, lab, ifc_context = _fixture()
    source_col, test_col = st.columns([1, 1])
    with source_col:
        st.markdown("### Code and rule explorer")
        source_label = st.selectbox("Inspect implementation", list(SOURCE_FILES), key="live_source_file")
        source_path = ROOT / SOURCE_FILES[source_label]
        if source_path.exists():
            source_bytes = source_path.read_bytes()
            st.caption(f"`{SOURCE_FILES[source_label]}` · SHA-256 `{hashlib.sha256(source_bytes).hexdigest()}` · {len(source_bytes)} bytes")
            source_text = source_bytes.decode("utf-8", errors="replace")
            st.code(source_text[:18000], language="turtle" if source_path.suffix == ".ttl" else ("python" if source_path.suffix == ".py" else "text"))
            if len(source_text) > 18000:
                st.caption("Excerpt limited to the first 18,000 characters. The source hash covers the complete file.")
        else:
            st.warning("Selected source file is not present in this runtime.")
    with test_col:
        st.markdown("### Controlled defect lab")
        scenario = st.selectbox(
            "Scenario",
            [
                "Baseline — unchanged record",
                "Measurement byte changed",
                "IFC byte changed",
                "GlobalId cannot resolve",
                "GlobalId differs from resolved component",
                "Entity class differs",
                "Remove calibration status",
                "Corrupt measurement checksum",
                "Filename/media type conflict",
            ],
            key="live_validation_scenario",
        )
        sidecar = build_sidecar("scan.csv", measurement, lab, ifc_context, record_id="interactive-fixture")
        measured_for_check, ifc_for_check = measurement, ifc
        resolved = {"resolved": True, "global_id": ifc_context["global_id"], "ifc_class": "IfcWall"}
        if scenario == "Measurement byte changed":
            measured_for_check = measurement + b" "
        elif scenario == "IFC byte changed":
            ifc_for_check = ifc + b" "
        elif scenario == "GlobalId cannot resolve":
            resolved = {"resolved": False, "global_id": None, "ifc_class": None}
        elif scenario == "GlobalId differs from resolved component":
            resolved = {"resolved": True, "global_id": "1HAsj4B9D2bBEUfukRtNYE", "ifc_class": "IfcWall"}
        elif scenario == "Entity class differs":
            resolved = {"resolved": True, "global_id": ifc_context["global_id"], "ifc_class": "IfcSlab"}
        elif scenario == "Remove calibration status":
            del sidecar["labContext"]["calibrationStatus"]
        elif scenario == "Corrupt measurement checksum":
            sidecar["measurementPayload"]["sha256"] = "sha256:not-a-digest"
        elif scenario == "Filename/media type conflict":
            sidecar["measurementPayload"]["mediaType"] = "text/plain"

        st.markdown("**Executed validators**")
        cross_issues = validate_sidecar(sidecar, measured_for_check, ifc_for_check, resolved)
        try:
            shacl = validate_shacl(sidecar)
            shacl_ok = bool(shacl["conforms"])
            shacl_text = shacl["report_text"]
            shacl_error = None
        except Exception as exc:
            shacl_ok, shacl_text, shacl_error = False, "", f"{type(exc).__name__}: {exc}"
        try:
            jsonld_ok = jsonld_is_parseable(sidecar)
            query_rows = query_profile_record(sidecar)
            query_ok = bool(query_rows)
            query_error = None
        except Exception as exc:
            jsonld_ok, query_ok, query_rows = False, False, []
            query_error = f"{type(exc).__name__}: {exc}"

        cross_ok = not cross_issues
        overall = cross_ok and shacl_ok and jsonld_ok and query_ok
        metrics = st.columns(3)
        metrics[0].metric("Cross-layer integrity", "PASS" if cross_ok else "FAIL")
        metrics[1].metric("SHACL profile", "PASS" if shacl_ok else "FAIL")
        metrics[2].metric("JSON-LD + SPARQL", "PASS" if jsonld_ok and query_ok else "FAIL")
        if overall:
            st.success("Current synthetic scenario passes all executed layers.")
        else:
            st.error("Current synthetic scenario has validation findings. A failed scenario is expected for injected defects.")
        st.caption(f"Profile {PROFILE_VERSION} · {PROFILE_ID} · shape file read from current repository at validation time")
        st.markdown("**Cross-layer findings**")
        st.json({"valid": cross_ok, "issues": cross_issues})
        st.markdown("**SHACL report**")
        if shacl_error:
            st.error(shacl_error)
        else:
            st.write(shacl_text)
        with st.expander("SPARQL competency-query result"):
            st.json({"query_succeeded": query_ok, "rows": query_rows, "error": query_error})
        with st.expander("Exact record used for this run"):
            st.json(sidecar)
        st.caption("The fixture IFC bytes are intentionally synthetic. IFC GlobalId resolution here is a controlled validator input, not a parsed building model.")
    st.markdown("### Traceability matrix")
    st.dataframe(
        [
            {"Layer": "Source bytes", "Implementation": "fair_platform/vibrometry_sidecar.py::sha256_uri", "Evidence": "byte count + SHA-256", "Boundary": "Does not establish scientific correctness"},
            {"Layer": "IFC identity", "Implementation": "validate_sidecar", "Evidence": "GlobalId + entity class comparison", "Boundary": "Fixture resolution is simulated; real run needs parsed IFC bytes"},
            {"Layer": "JSON-LD", "Implementation": "jsonld_is_parseable", "Evidence": "RDF graph parses", "Boundary": "Vocabulary URIs not necessarily dereferenced"},
            {"Layer": "Profile constraints", "Implementation": "validate_shacl + shapes/vibrometry-profile.shacl.ttl", "Evidence": "SHACL conformance and report text", "Boundary": "Only encoded constraints are tested"},
            {"Layer": "Machine query", "Implementation": "query_profile_record", "Evidence": "Record → payload → IFC link row", "Boundary": "Queryability does not prove physical registration"},
        ],
        use_container_width=True,
        hide_index=True,
    )
