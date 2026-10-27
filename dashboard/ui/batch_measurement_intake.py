"""Batch-first, in-dashboard SLDV / JSON-LD / IFC demonstrator.

Original measurement bytes remain authoritative. This module creates per-record
JSON-LD sidecars and a package index for live inspection; it does not create
HDF5 files or rewrite measurement payloads.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.ui.platform_app import inspect_ifc_bytes
from fair_platform.sldv_payload import inspect_sldv_payload
from fair_platform.vibrometry_sidecar import (
    PROFILE_ID,
    PROFILE_VERSION,
    build_sidecar,
    sha256_uri,
    validate_shacl,
    validate_sidecar,
    jsonld_is_parseable,
)


FIELD_ALIASES = {
    "method": ("method", "measurement_method", "measurement method", "method of measurement"),
    "instrument": ("instrument", "instrument_model", "instrument model", "device", "equipment"),
    "operator": ("operator", "measured_by", "measured by", "experimenter"),
    "measurementDate": ("measurementDate", "measurement_date", "measurement date", "date"),
    "calibrationStatus": ("calibrationStatus", "calibration_status", "calibration status", "calibration"),
    "scanSetup": ("scanSetup", "scan_setup", "scan setup", "measurement setup", "scan configuration"),
    "measuredQuantity": ("measuredQuantity", "measured_quantity", "measured quantity", "quantity"),
    "unit": ("unit", "units", "measurement unit"),
    "processingDescription": ("processingDescription", "processing_description", "processing description", "processing", "data processing"),
    "limitations": ("limitations", "limitation", "notes", "remarks"),
}


def _norm_key(value: Any) -> str:
    return "".join(ch.lower() for ch in str(value).strip() if ch.isalnum())


def _parse_metadata(upload):
    """Parse lab metadata and preserve a traceable description of extraction."""
    if upload is None:
        return {}, {"status": "not supplied", "source": None, "fields_extracted": 0}
    name = upload.name.lower()
    raw = upload.getvalue()
    if name.endswith((".json", ".jsonld")):
        obj = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(obj, dict):
            raise ValueError("External JSON metadata must be a JSON object.")
        return obj, {
            "status": "parsed",
            "source": upload.name,
            "format": "JSON/JSON-LD",
            "fields_extracted": len(obj.get("labContext", {})) + len(obj.get("extractedFields", {})),
        }
    if name.endswith(".csv"):
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
        return {"records": rows}, {
            "status": "parsed",
            "source": upload.name,
            "format": "CSV",
            "fields_extracted": len(rows[0]) if rows else 0,
            "records_extracted": len(rows),
        }
    if name.endswith(".docx"):
        try:
            from docx import Document
        except ImportError as exc:
            raise ValueError("DOCX parsing requires python-docx. Add it to requirements.txt and redeploy.") from exc
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
        return {"sourceDocument": upload.name, "extractedFields": extracted}, {
            "status": "parsed",
            "source": upload.name,
            "format": "DOCX paragraphs and tables",
            "fields_extracted": len(extracted),
            "extracted_field_names": list(extracted),
        }
    raise ValueError("Supported laboratory metadata formats: JSON, JSON-LD, CSV or DOCX.")


def _record_for_file(metadata: dict[str, Any], filename: str) -> dict[str, Any]:
    records = metadata.get("records", []) if isinstance(metadata, dict) else []
    target = filename.casefold()
    for row in records:
        if not isinstance(row, dict):
            continue
        candidate = row.get("fileName") or row.get("measurement_file") or row.get("filename") or row.get("sourceFile")
        if candidate and Path(str(candidate)).name.casefold() == target:
            return row
    return {}


def _lookup(source: dict[str, Any], aliases: tuple[str, ...]):
    indexed = {_norm_key(key): value for key, value in source.items()}
    for alias in aliases:
        value = indexed.get(_norm_key(alias))
        if value not in (None, ""):
            return value, next((str(k) for k in source if _norm_key(k) == _norm_key(alias)), alias)
    return None, None


def _lab_context(metadata: dict[str, Any], per_file: dict[str, Any]):
    """Map source fields to profile fields; per-file values outrank shared values.

    Return both normalized values and field-level provenance. Missing source
    facts stay unknown; no UI defaults overwrite source metadata.
    """
    shared_sources = []
    for key in ("labContext", "extractedFields"):
        value = metadata.get(key, {})
        if isinstance(value, dict) and value:
            shared_sources.append((value, metadata.get("sourceDocument") or key))
    if not shared_sources and not metadata.get("records"):
        shared_sources.append((metadata, metadata.get("sourceDocument") or "metadata root"))
    values, provenance = {}, {}
    for target, aliases in FIELD_ALIASES.items():
        value, source_field = _lookup(per_file, aliases)
        if value not in (None, ""):
            values[target] = str(value).strip()
            provenance[target] = {"status": "extracted", "source": "matching per-file metadata record", "source_field": source_field, "method": "alias mapping"}
            continue
        found = False
        for source, source_name in shared_sources:
            value, source_field = _lookup(source, aliases)
            if value not in (None, ""):
                values[target] = str(value).strip()
                provenance[target] = {"status": "extracted", "source": source_name, "source_field": source_field, "method": "alias mapping"}
                found = True
                break
        if not found:
            values[target] = "unknown"
            provenance[target] = {"status": "unknown", "source": None, "source_field": None, "method": "No matching source field found"}
    if values["limitations"] == "unknown":
        unknown = [key for key in ("instrument", "operator", "calibrationStatus", "scanSetup", "processingDescription") if values[key] == "unknown"]
        values["limitations"] = "Unknown source fields require review: " + ", ".join(unknown) if unknown else "No limitations documented in supplied metadata."
        provenance["limitations"] = {"status": "derived", "source": "field completeness check", "source_field": None, "method": "Generated from missing-field inventory"}
    return values, provenance


def _read_signal_preview(filename: str, payload: bytes):
    """Best-effort numeric preview from the source text; does not rewrite it."""
    try:
        text = payload.decode("utf-8-sig", errors="replace")
        delimiter = ";" if text.count(";") > text.count(",") else ","
        frame = pd.read_csv(io.StringIO(text), sep=delimiter, comment="#", engine="python")
        if frame.shape[1] < 2:
            frame = pd.read_csv(io.StringIO(text), sep=None, comment="#", engine="python")
        numeric = frame.apply(pd.to_numeric, errors="coerce")
        numeric = numeric.dropna(axis=1, how="all")
        if numeric.empty:
            return frame.head(20), None, "No numeric columns could be identified."
        numeric = numeric.dropna(axis=0, how="all")
        numeric = numeric.head(5000)
        xcol = numeric.columns[0]
        ycols = list(numeric.columns[1:5])
        if not ycols:
            ycols = list(numeric.columns[:1])
        plot = numeric.reset_index(names="sample_index").melt(
            id_vars="sample_index", value_vars=ycols, var_name="signal", value_name="value"
        )
        return frame.head(20), plot, f"{len(frame):,} parsed rows; {len(numeric.columns)} numeric columns. Plot capped at 5,000 samples."
    except Exception as exc:
        return None, None, f"Preview could not be parsed: {type(exc).__name__}: {exc}"


def _render_architecture(report: dict[str, Any], selected_record: dict[str, Any] | None):
    st.markdown("### Three decoupled layers")
    a, b, c = st.columns(3)
    with a:
        st.markdown("#### 01 · Measurement")
        st.caption("Original TXT/CSV bytes")
        st.metric("Uploaded files", report.get("measurement_count", 0))
        st.code("SHA-256 + byte size\nSource payload stays unchanged", language="text")
    with b:
        st.markdown("#### 02 · Semantic")
        st.caption("Index JSON + JSON-LD 1.1 sidecars")
        st.metric("Sidecars generated", len(report.get("records", [])))
        st.code("Record URI → payload hash\nRecord URI → IFC link record", language="text")
    with c:
        st.markdown("#### 03 · IFC context")
        st.caption("Model + component identity")
        st.metric("IFC schema", report.get("ifc_schema") or "Not resolved")
        st.code("IFC hash + schema\nGlobalId + entity class", language="text")
    st.markdown("#### Link path for the selected record")
    if selected_record:
        sidecar = selected_record.get("sidecar", {})
        payload = sidecar.get("measurementPayload", {})
        link = sidecar.get("ifcLinkRecord", {})
        st.code(
            f'{selected_record.get("filename")}  [{payload.get("sha256", "no hash")}]\n'
            f'  └─ index entry: {selected_record.get("record_id")}\n'
            f'      └─ JSON-LD @id: {sidecar.get("@id", "missing")}\n'
            f'          └─ IFC: {link.get("ifcFileName", "unknown")} / {link.get("ifcGlobalId", "unknown")}',
            language="text",
        )
    st.info("Decoupling means each layer has its own identity and source of record. The semantic sidecar links them; measurement arrays are not embedded in IFC. Hashes verify byte identity, not scientific validity or spatial registration.")


def render_batch_measurement_intake() -> None:
    st.markdown("# Batch SLDV research-data workspace")
    st.write("Upload the measurement set, one laboratory-context file and one IFC model. The app automatically extracts metadata, creates an index and JSON-LD 1.1 sidecars, then exposes the resulting architecture and validation evidence here in the dashboard.")
    left, right = st.columns([1.1, 1])
    with left:
        measurements = st.file_uploader(
            "1 · Original SLDV measurement files (TXT/CSV)",
            type=["txt", "csv"], accept_multiple_files=True, key="batch_sldv_measurements",
            help="Select the complete batch. Original file bytes are retained unchanged.",
        )
        metadata_upload = st.file_uploader(
            "2 · Laboratory-context metadata (DOCX/JSON/JSON-LD/CSV)",
            type=["json", "jsonld", "csv", "docx"], key="batch_lab_metadata",
            help="Shared lab fields may be in labContext or labelled DOCX fields. Per-file rows can identify a measurement by filename.",
        )
    with right:
        ifc_file = st.file_uploader("3 · IFC model", type=["ifc"], key="batch_ifc")
        components = []
        if ifc_file:
            try:
                components = inspect_ifc_bytes(ifc_file.getvalue())
            except Exception as exc:
                st.error(f"IFC inspection failed: {type(exc).__name__}: {exc}")
        selected_component = None
        if components:
            labels = [f'{item.get("name") or "(unnamed)"} · {item.get("ifc_class")} · {item.get("global_id")}' for item in components]
            idx = st.selectbox("Target IFC component for this measurement batch", range(len(components)), format_func=lambda i: labels[i], key="batch_ifc_component")
            selected_component = dict(components[idx])
        elif ifc_file:
            st.error("No selectable IFC component was found in the supplied model.")

    if not measurements or not metadata_upload or not ifc_file or not selected_component:
        st.info("Upload all three inputs to populate the live technical workspace. No manual metadata overrides are required.")
        return

    try:
        metadata, metadata_report = _parse_metadata(metadata_upload)
    except Exception as exc:
        st.error(f"Laboratory metadata extraction failed: {type(exc).__name__}: {exc}")
        return

    ifc_bytes = ifc_file.getvalue()
    selected_component["source_file"] = ifc_file.name
    selected_component["source_sha256"] = sha256_uri(ifc_bytes)
    metadata_sha = sha256_uri(metadata_upload.getvalue())
    ifc_schema = selected_component.get("ifc_schema")
    cache_material = {
        "files": [(Path(item.name).name, sha256_uri(item.getvalue())) for item in measurements],
        "metadata_sha256": metadata_sha,
        "ifc_sha256": sha256_uri(ifc_bytes),
        "component": selected_component.get("global_id"),
        "profile": PROFILE_VERSION,
    }
    cache_key = hashlib.sha256(json.dumps(cache_material, sort_keys=True).encode()).hexdigest()
    if st.session_state.get("batch_sldv_cache_key") != cache_key:
        records, results, source_reports = [], [], []
        seen = set()
        for position, uploaded in enumerate(measurements, start=1):
            filename = Path(uploaded.name).name
            payload = uploaded.getvalue()
            if filename.casefold() in seen:
                results.append({"File": filename, "Status": "FAIL", "Findings": [{"code": "DUPLICATE_FILENAME", "message": "Duplicate filename would make package paths ambiguous."}]})
                continue
            seen.add(filename.casefold())
            per_file = _record_for_file(metadata, filename)
            lab, field_provenance = _lab_context(metadata, per_file)
            record_id = str(per_file.get("recordIdentifier") or per_file.get("measurementIdentifier") or f"SLDV-{position:03d}")
            record = {
                "record_id": record_id,
                "filename": filename,
                "payload": payload,
                "payload_sha256": sha256_uri(payload),
                "lab_context": lab,
                "field_provenance": field_provenance,
                "metadata_record": per_file,
                "sidecar": {},
                "payload_analysis": {},
                "signal_preview": None,
                "signal_plot": None,
                "signal_note": "",
                "validation": {},
            }
            try:
                sidecar = build_sidecar(filename, payload, lab, selected_component, record_id=record_id)
                cross = validate_sidecar(
                    sidecar, payload, ifc_bytes,
                    {"resolved": bool(selected_component.get("global_id")), "global_id": selected_component.get("global_id"), "ifc_class": selected_component.get("ifc_class")},
                )
                shacl = validate_shacl(sidecar)
                try:
                    jsonld_parseable = jsonld_is_parseable(sidecar)
                except Exception:
                    jsonld_parseable = False
                payload_analysis = inspect_sldv_payload(filename, payload)
                preview, plot, plot_note = _read_signal_preview(filename, payload)
                record.update({"sidecar": sidecar, "payload_analysis": payload_analysis, "signal_preview": preview, "signal_plot": plot, "signal_note": plot_note})
                validation = {
                    "overall": not cross and bool(shacl.get("conforms")) and jsonld_parseable,
                    "cross_layer": {"conforms": not cross, "issues": cross},
                    "shacl": shacl,
                    "jsonld_parseable": jsonld_parseable,
                    "hashes": {
                        "measurement_expected": sidecar["measurementPayload"]["sha256"],
                        "measurement_actual": sha256_uri(payload),
                        "ifc_expected": sidecar["ifcLinkRecord"]["ifcSha256"],
                        "ifc_actual": sha256_uri(ifc_bytes),
                    },
                }
                record["validation"] = validation
                findings = list(cross)
                if not shacl.get("conforms"):
                    findings.append({"code": "SHACL_NONCONFORMANCE", "message": shacl.get("report_text", "Sidecar failed SHACL profile validation.")})
                if not jsonld_parseable:
                    findings.append({"code": "JSONLD_PARSE_FAILURE", "message": "The generated sidecar could not be parsed as JSON-LD."})
                unknown = [key for key, value in lab.items() if value == "unknown"]
                if unknown:
                    findings.append({"code": "MISSING_LAB_CONTEXT", "message": "Fields not found in supplied metadata: " + ", ".join(unknown)})
                results.append({
                    "File": filename, "Record ID": record_id, "Bytes": len(payload),
                    "SHA-256": record["payload_sha256"], "JSON-LD": "PASS",
                    "Cross-layer": "PASS" if not cross else "FAIL",
                    "SHACL": "PASS" if shacl.get("conforms") else "FAIL",
                    "Missing metadata fields": len(unknown), "Status": "PASS" if validation["overall"] and not unknown else "REVIEW",
                    "Findings": findings,
                })
            except Exception as exc:
                record["validation"] = {"overall": False, "error": f"{type(exc).__name__}: {exc}"}
                results.append({"File": filename, "Record ID": record_id, "Bytes": len(payload), "SHA-256": record["payload_sha256"], "Status": "FAIL", "Findings": [{"code": "PROCESSING_EXCEPTION", "message": f"{type(exc).__name__}: {exc}"}]})
            records.append(record)

        index = {
            "@context": {"dct": "http://purl.org/dc/terms/", "vibro": "https://w3id.org/vibro-ifc/vocab/"},
            "indexVersion": "1.0",
            "profile": PROFILE_ID,
            "profileVersion": PROFILE_VERSION,
            "generatedFor": {"ifcFileName": ifc_file.name, "ifcSha256": sha256_uri(ifc_bytes), "ifcSchema": ifc_schema, "ifcGlobalId": selected_component.get("global_id"), "ifcEntityType": selected_component.get("ifc_class")},
            "metadataSource": {"fileName": metadata_upload.name, "sha256": metadata_sha, "format": metadata_report.get("format")},
            "measurementCount": len(records),
            "records": [{
                "recordIdentifier": record["record_id"],
                "sourceFile": record["filename"],
                "sourceSha256": record["payload_sha256"],
                "sidecarPath": f'metadata/{record["record_id"]}.jsonld',
                "sidecarId": record.get("sidecar", {}).get("@id"),
                "ifcGlobalId": selected_component.get("global_id"),
                "validationStatus": record.get("validation", {}).get("overall", False),
            } for record in records],
        }
        report = {
            "cache_key": cache_key, "measurement_count": len(records), "records": records,
            "results": results, "index": index, "metadata_report": metadata_report,
            "metadata": metadata, "metadata_sha256": metadata_sha,
            "ifc_file_name": ifc_file.name, "ifc_sha256": sha256_uri(ifc_bytes),
            "ifc_schema": ifc_schema, "ifc_component": selected_component,
            "ifc_bytes": ifc_bytes,
        }
        st.session_state["batch_sldv_cache_key"] = cache_key
        st.session_state["batch_sldv_report"] = report

    report = st.session_state.get("batch_sldv_report")
    if not report or report.get("cache_key") != cache_key:
        st.warning("Processing has not produced a report for the current upload set.")
        return

    records = report["records"]
    results = report["results"]
    passing = sum(row.get("Status") == "PASS" for row in results)
    review = sum(row.get("Status") == "REVIEW" for row in results)
    failed = sum(row.get("Status") == "FAIL" for row in results)
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Measurements processed", len(records))
    m2.metric("Pass", passing)
    m3.metric("Review needed", review)
    m4.metric("Failed", failed)

    st.markdown("## Technical showcase")
    record_options = list(range(len(records)))
    selected_idx = st.selectbox(
        "Inspect measurement record",
        record_options,
        format_func=lambda i: f'{records[i]["record_id"]} · {records[i]["filename"]}',
        key="batch_sldv_record_select",
    )
    selected_record = records[selected_idx] if records else None
    tabs = st.tabs(["Architecture", "Record & provenance", "JSON-LD 1.1", "Index JSON", "Signal data", "Validation"])
    with tabs[0]:
        _render_architecture(report, selected_record)
        st.markdown("#### Layer boundaries and dependencies")
        st.dataframe([
            {"Layer": "Measurement", "Authoritative artifact": "Original TXT/CSV", "Identity": "SHA-256 + filename", "Depends on IFC schema?": "No"},
            {"Layer": "Semantic", "Authoritative artifact": "JSON-LD 1.1 sidecar + index", "Identity": "Record @id + profile version", "Depends on IFC schema?": "Only through explicit link fields"},
            {"Layer": "IFC context", "Authoritative artifact": report["ifc_file_name"], "Identity": "IFC hash + schema + GlobalId", "Depends on measurement layout?": "No"},
        ], use_container_width=True, hide_index=True)
        st.caption("Changing a source file invalidates its digest. Changing the IFC model invalidates the model digest. The sidecar records both identities without embedding the measurement arrays in IFC.")
    with tabs[1]:
        st.markdown("### Extracted laboratory fields")
        rows = []
        for field, value in selected_record["lab_context"].items():
            evidence = selected_record["field_provenance"].get(field, {})
            rows.append({"Profile field": field, "Value": value, "Extraction status": evidence.get("status"), "Source": evidence.get("source"), "Source field": evidence.get("source_field"), "Mapping method": evidence.get("method")})
        st.dataframe(rows, use_container_width=True, hide_index=True)
        st.markdown("### Source and IFC identities")
        st.json({
            "measurement": {"fileName": selected_record["filename"], "bytes": len(selected_record["payload"]), "sha256": selected_record["payload_sha256"]},
            "labMetadata": {"fileName": report["metadata_report"].get("source"), "sha256": report["metadata_sha256"], "format": report["metadata_report"].get("format")},
            "ifc": {"fileName": report["ifc_file_name"], "sha256": report["ifc_sha256"], "schema": report["ifc_schema"], "componentGlobalId": report["ifc_component"].get("global_id"), "entityType": report["ifc_component"].get("ifc_class")},
        })
        with st.expander("Raw metadata file structure"):
            st.json(report["metadata"])
        with st.expander("Payload analysis report"):
            st.json(selected_record.get("payload_analysis", {}))
    with tabs[2]:
        st.markdown("### Generated JSON-LD sidecar")
        sidecar = selected_record.get("sidecar", {})
        st.caption(f'Profile {sidecar.get("profileVersion", PROFILE_VERSION)} · {sidecar.get("@id", "No record identifier")}')
        st.json(sidecar, expanded=2)
        with st.expander("Raw JSON-LD document"):
            st.code(json.dumps(sidecar, indent=2, ensure_ascii=False), language="json")
        st.markdown("#### Semantic relationship summary")
        st.dataframe([
            {"Relationship": "Record → source payload", "Target": sidecar.get("measurementPayload", {}).get("@id"), "Evidence": sidecar.get("measurementPayload", {}).get("sha256")},
            {"Relationship": "Record → IFC link record", "Target": sidecar.get("ifcLinkRecord", {}).get("@id"), "Evidence": sidecar.get("ifcLinkRecord", {}).get("ifcGlobalId")},
            {"Relationship": "Profile conformance target", "Target": sidecar.get("dct:conformsTo"), "Evidence": sidecar.get("profileVersion")},
        ], use_container_width=True, hide_index=True)
    with tabs[3]:
        st.markdown("### Generated batch index")
        st.caption("The index is generated from the processed records and points to each sidecar and IFC context. It is separate from the sidecars themselves.")
        st.json(report["index"], expanded=2)
        st.code(json.dumps(report["index"], indent=2, ensure_ascii=False), language="json")
    with tabs[4]:
        st.markdown("### Original measurement inspection")
        st.caption("Numeric preview is derived in memory for visualization only. The uploaded source bytes are preserved unchanged.")
        preview = selected_record.get("signal_preview")
        plot = selected_record.get("signal_plot")
        st.info(selected_record.get("signal_note") or "No signal preview available.")
        if preview is not None:
            st.dataframe(preview, use_container_width=True, hide_index=True)
        if plot is not None and not plot.empty:
            st.markdown("#### Numeric signal preview")
            st.line_chart(plot, x="sample_index", y="value", color="signal")
        st.markdown("#### Source payload (first 80 lines)")
        st.code(selected_record["payload"].decode("utf-8-sig", errors="replace")[:12000], language="text")
    with tabs[5]:
        st.markdown("### Validation by layer")
        st.dataframe(results, use_container_width=True, hide_index=True)
        st.markdown("#### Selected record findings")
        validation = selected_record.get("validation", {})
        st.metric("Cross-layer checks", "PASS" if validation.get("cross_layer", {}).get("conforms") else "FAIL")
        st.metric("SHACL profile", "PASS" if validation.get("shacl", {}).get("conforms") else "FAIL")
        st.markdown("**Hash comparison**")
        st.json(validation.get("hashes", {}))
        st.markdown("**Cross-layer findings**")
        st.json(validation.get("cross_layer", {}).get("issues", []))
        shacl = validation.get("shacl", {})
        st.markdown("**SHACL report text**")
        st.code(shacl.get("report_text", "SHACL was not executed."), language="text")
        with st.expander("SHACL result graph (Turtle)"):
            st.code(shacl.get("results_graph", ""), language="turtle")
        st.markdown("#### Metadata completeness")
        completeness = [{"Field": key, "Status": value.get("status"), "Evidence": value.get("source_field") or value.get("method")} for key, value in selected_record["field_provenance"].items()]
        st.dataframe(completeness, use_container_width=True, hide_index=True)
