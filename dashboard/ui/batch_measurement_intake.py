"""Batch intake for source-preserving SLDV measurement records."""
from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import streamlit as st

from dashboard.ui.platform_app import inspect_ifc_bytes
from fair_platform.sldv_payload import inspect_sldv_payload
from fair_platform.vibrometry_sidecar import (
    PROFILE_VERSION,
    build_sidecar,
    sha256_uri,
    validate_shacl,
    validate_sidecar,
)


def _parse_metadata(upload):
    if upload is None:
        return {}, "No external metadata file supplied."
    name = upload.name.lower()
    raw = upload.getvalue()
    if name.endswith((".json", ".jsonld")):
        obj = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(obj, dict):
            raise ValueError("External JSON metadata must be a JSON object.")
        return obj, "Parsed JSON/JSON-LD metadata."
    if name.endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        return {"records": rows}, f"Parsed {len(rows)} metadata CSV rows."
    if name.endswith(".docx"):
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError("DOCX parsing requires python-docx in the deployed environment.") from exc
        document = Document(io.BytesIO(raw))
        extracted = {}
        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if ":" in text:
                key, value = text.split(":", 1)
                if key.strip() and value.strip():
                    extracted[key.strip()] = value.strip()
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                if len(cells) >= 2 and cells[0] and cells[1]:
                    extracted[cells[0].rstrip(":")] = cells[1]
        return {"sourceDocument": upload.name, "extractedFields": extracted}, f"Extracted {len(extracted)} labelled fields from DOCX; review mappings before relying on them."
    raise ValueError("Supported external metadata formats: JSON, JSON-LD, CSV or DOCX.")


def _record_for_file(metadata, filename):
    records = metadata.get("records", []) if isinstance(metadata, dict) else []
    for row in records:
        if not isinstance(row, dict):
            continue
        candidate = row.get("fileName") or row.get("measurement_file") or row.get("filename") or row.get("sourceFile")
        if candidate and str(candidate).strip() == filename:
            return row
    return {}


def _lab_context(shared, record):
    aliases = {
        "method": ("method", "measurement_method", "Measurement method"),
        "instrument": ("instrument", "instrument_model", "Instrument"),
        "operator": ("operator", "Operator"),
        "measurementDate": ("measurementDate", "measurement_date", "Measurement date"),
        "calibrationStatus": ("calibrationStatus", "calibration_status", "Calibration status"),
        "scanSetup": ("scanSetup", "scan_setup", "Scan setup"),
        "measuredQuantity": ("measuredQuantity", "measured_quantity", "Measured quantity"),
        "unit": ("unit", "Unit", "units"),
        "processingDescription": ("processingDescription", "processing_description", "Processing"),
        "limitations": ("limitations", "Limitations"),
    }
    result = {}
    for target, keys in aliases.items():
        value = next((record.get(k) for k in keys if record.get(k) not in (None, "")), None)
        if value is None:
            value = next((shared.get(k) for k in keys if shared.get(k) not in (None, "")), None)
        if value is not None:
            result[target] = str(value).strip()
    result.setdefault("method", "unknown")
    result.setdefault("instrument", "unknown")
    result.setdefault("operator", "unknown")
    result.setdefault("measurementDate", "unknown")
    result.setdefault("calibrationStatus", "unknown")
    result.setdefault("scanSetup", "unknown")
    result.setdefault("measuredQuantity", "unknown")
    result.setdefault("unit", "unknown")
    result.setdefault("processingDescription", "unknown")
    result.setdefault("limitations", "External metadata was incomplete; unknown values require confirmation.")
    unknown = [key for key in ("instrument", "operator", "calibrationStatus", "scanSetup", "processingDescription") if result[key].lower() == "unknown"]
    if unknown and "unknown" not in result["limitations"].lower():
        result["limitations"] += "; Unknown fields: " + ", ".join(unknown) + "."
    return result


def render_batch_measurement_intake() -> None:
    st.markdown("## Batch SLDV measurement intake")
    st.write("Upload the original TXT/CSV measurement files together, add the external laboratory metadata, and bind each record to the selected IFC component. One JSON-LD sidecar and one validation report are generated per measurement. Original payload bytes are included unchanged.")
    st.info("This batch intake creates a metadata/validation bundle; it does not yet run the full FAIR package builder separately for every file. No HDF5 or rewritten measurement payload is created.")

    left, right = st.columns(2)
    with left:
        measurements = st.file_uploader(
            "Local acoustic measurement files (multiple)",
            type=["txt", "csv"],
            accept_multiple_files=True,
            key="batch_sldv_measurements",
            help="Select all approximately 20 original SLDV TXT/CSV files. File bytes are preserved.",
        )
        metadata_upload = st.file_uploader(
            "External laboratory metadata",
            type=["json", "jsonld", "csv", "docx"],
            key="batch_lab_metadata",
            help="JSON/JSON-LD can contain shared labContext and/or a records array. CSV rows should identify a measurement using fileName or measurement_file. DOCX is extracted as labelled fields for review.",
        )
        record_prefix = st.text_input("Record ID prefix", value="SLDV")
    with right:
        ifc_file = st.file_uploader("IFC specimen model", type=["ifc"], key="batch_ifc")
        components = inspect_ifc_bytes(ifc_file.getvalue()) if ifc_file else []
        selected_component = None
        if components:
            labels = [
                f"{item.get('name')} · {item.get('ifc_class')} · {item.get('global_id')}"
                for item in components
            ]
            idx = st.selectbox("IFC component for this batch", range(len(components)), format_func=lambda i: labels[i], key="batch_ifc_component")
            selected_component = components[idx]
            st.success(f"Resolved component: {selected_component.get('global_id')} ({selected_component.get('ifc_class')})")
        elif ifc_file:
            st.error("No component could be resolved from this IFC file.")

    metadata = {}
    metadata_note = "No external metadata file supplied."
    if metadata_upload:
        try:
            metadata, metadata_note = _parse_metadata(metadata_upload)
            st.caption(metadata_note)
            with st.expander("Review parsed external metadata", expanded=True):
                st.json(metadata)
        except Exception as exc:
            st.error(f"Could not parse external metadata: {type(exc).__name__}: {exc}")
            metadata = {}

    st.markdown("### Shared laboratory metadata / mapping overrides")
    st.caption("Values entered here apply to every file unless a matching per-file metadata record overrides them. Use explicit unknowns instead of inventing facts.")
    m1, m2, m3 = st.columns(3)
    with m1:
        method = st.text_input("Method", value="3D scanning laser Doppler vibrometry", key="batch_method")
        instrument = st.text_input("Instrument / model", key="batch_instrument")
        operator = st.text_input("Operator", key="batch_operator")
        measurement_date = st.text_input("Measurement date (ISO date or unknown)", value="unknown", key="batch_date")
    with m2:
        calibration = st.text_input("Calibration status/reference", value="unknown", key="batch_calibration")
        scan_setup = st.text_input("Scan setup", key="batch_setup")
        quantity = st.text_input("Measured quantity", value="velocity", key="batch_quantity")
        unit = st.text_input("Unit", value="m/s", key="batch_unit")
    with m3:
        processing = st.text_input("Processing description", key="batch_processing")
        limitations = st.text_area("Limitations", value="Instrument and calibration details must be confirmed from laboratory records.", key="batch_limitations")
        record_id_map = st.text_input("Per-file record IDs (optional)", placeholder="Comma-separated, in upload order", key="batch_record_ids")

    shared = {
        "method": method, "instrument": instrument, "operator": operator,
        "measurementDate": measurement_date, "calibrationStatus": calibration,
        "scanSetup": scan_setup, "measuredQuantity": quantity, "unit": unit,
        "processingDescription": processing, "limitations": limitations,
    }
    id_list = [item.strip() for item in record_id_map.split(",") if item.strip()]
    can_process = bool(measurements and ifc_file and selected_component)
    st.metric("Measurement files selected", len(measurements or []))
    if not can_process:
        st.caption("Select at least one TXT/CSV file and a valid IFC component to generate the batch bundle.")
        return

    if st.button("Validate batch and build sidecar bundle", type="primary", use_container_width=True):
        ifc_bytes = ifc_file.getvalue()
        geometry = dict(selected_component)
        geometry["source_file"] = ifc_file.name
        geometry["source_sha256"] = geometry.get("source_sha256") or sha256_uri(ifc_bytes)
        rows, bundle = [], io.BytesIO()
        seen = set()
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("geometry/" + Path(ifc_file.name).name, ifc_bytes)
            for index, uploaded in enumerate(measurements, start=1):
                filename = Path(uploaded.name).name
                if filename in seen:
                    rows.append({"File": filename, "Status": "FAIL", "Issues": "Duplicate filename in upload; package paths would collide."})
                    continue
                seen.add(filename)
                payload = uploaded.getvalue()
                per_file = _record_for_file(metadata, filename)
                lab = _lab_context({**metadata.get("labContext", {}), **shared}, per_file)
                identifier = (id_list[index - 1] if len(id_list) >= index else per_file.get("recordIdentifier") or per_file.get("measurementIdentifier") or f"{record_prefix}-{index:03d}")
                try:
                    sidecar = build_sidecar(filename, payload, lab, geometry, record_id=str(identifier))
                    cross = validate_sidecar(
                        sidecar, payload, ifc_bytes,
                        {"resolved": bool(geometry.get("global_id")), "global_id": geometry.get("global_id"), "ifc_class": geometry.get("ifc_class")},
                    )
                    shacl = validate_shacl(sidecar)
                    payload_report = inspect_sldv_payload(filename, payload)
                    valid = not cross and bool(shacl.get("conforms"))
                    archive.writestr(f"measurements/{filename}", payload)
                    archive.writestr(f"metadata/{identifier}.jsonld", json.dumps(sidecar, indent=2))
                    archive.writestr(f"reports/{identifier}-payload-analysis.json", json.dumps(payload_report, indent=2))
                    archive.writestr(f"reports/{identifier}-validation.json", json.dumps({
                        "valid": valid, "cross_layer": {"valid": not cross, "issues": cross}, "shacl": shacl,
                    }, indent=2))
                    rows.append({
                        "File": filename, "Record ID": identifier, "Bytes": len(payload),
                        "SHA-256": sha256_uri(payload), "JSON-LD": "PASS",
                        "Cross-layer": "PASS" if not cross else "FAIL",
                        "SHACL": "PASS" if shacl.get("conforms") else "FAIL",
                        "Status": "PASS" if valid else "REVIEW",
                        "Issues": "; ".join([item["code"] for item in cross] + ([] if shacl.get("conforms") else ["SHACL_NONCONFORMANCE"])),
                    })
                except Exception as exc:
                    rows.append({"File": filename, "Record ID": identifier, "Status": "FAIL", "Issues": f"{type(exc).__name__}: {exc}"})
        report = {"profile_version": PROFILE_VERSION, "measurement_count": len(measurements), "results": rows}
        with zipfile.ZipFile(bundle, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("reports/batch-summary.json", json.dumps(report, indent=2))
        st.session_state["batch_sldv_last_report"] = report
        st.session_state["batch_sldv_last_bundle"] = bundle.getvalue()

    report = st.session_state.get("batch_sldv_last_report")
    if report:
        st.markdown("### Per-file validation results")
        st.dataframe(report["results"], use_container_width=True, hide_index=True)
        total = report.get("measurement_count", 0)
        passed = sum(row.get("Status") == "PASS" for row in report["results"])
        st.metric("Passing records", f"{passed}/{total}")
        st.download_button(
            "Download batch sidecar + validation ZIP",
            st.session_state["batch_sldv_last_bundle"],
            file_name="sldv-batch-sidecars-and-validation.zip",
            mime="application/zip",
            use_container_width=True,
        )
