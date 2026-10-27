"""Persistent, research-grade batch workspace for the SLDV/IFC thesis.

Keeps uploader payloads in non-widget session keys, so Streamlit page navigation
does not discard the current batch. Source TXT/CSV bytes are never rewritten.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.ui.batch_measurement_intake import (
    _lab_context, _parse_metadata, _read_signal_preview, _record_for_file,
)
from dashboard.ui.platform_app import inspect_ifc_bytes
from fair_platform.sldv_payload import inspect_sldv_payload
from fair_platform.vibrometry_sidecar import (
    PROFILE_ID, PROFILE_VERSION, build_sidecar, jsonld_is_parseable,
    sha256_uri, validate_shacl, validate_sidecar,
)


class CachedUpload:
    """Minimal Streamlit-upload compatible object backed by session-state bytes."""
    def __init__(self, name: str, payload: bytes):
        self.name, self._payload = name, payload

    def getvalue(self) -> bytes:
        return self._payload


def _remember_upload(upload, storage_key: str) -> None:
    if upload is not None:
        st.session_state[storage_key] = {"name": upload.name, "bytes": upload.getvalue()}


def _cached_upload(widget_value, storage_key: str):
    _remember_upload(widget_value, storage_key)
    saved = st.session_state.get(storage_key)
    if widget_value is not None:
        return widget_value
    if saved:
        return CachedUpload(saved["name"], saved["bytes"])
    return None


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, indent=2, ensure_ascii=False, default=str).encode("utf-8")


def _make_bundle(report: dict[str, Any]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest/index.json", _json_bytes(report["index"]))
        archive.writestr("reports/validation-report.json", _json_bytes(report["validation_report"]))
        archive.writestr("reports/metadata-extraction.json", _json_bytes(report["metadata_report"]))
        archive.writestr("metadata/lab-source.json", _json_bytes(report["metadata"]))
        archive.writestr("geometry/" + report["ifc_name"], report["ifc_bytes"])
        if report.get("viewer_json") is not None:
            archive.writestr("viewer/blender-viewer.json", report["viewer_json"])
        for record in report["records"]:
            stem = Path(record["filename"]).stem
            safe_id = "".join(c if c.isalnum() or c in "-_." else "_" for c in record["record_id"])
            archive.writestr("measurements/" + record["filename"], record["payload"])
            archive.writestr(f"metadata/{safe_id}.jsonld", _json_bytes(record["sidecar"]))
            archive.writestr(f"reports/{safe_id}-validation.json", _json_bytes(record["validation"]))
        readme = (
            "VIBRO-IFC research data package\n"
            "Original measurement TXT/CSV bytes are retained unchanged.\n"
            "JSON-LD sidecars link payload identity, lab context and IFC component context.\n"
            "Hashes establish byte identity, not scientific correctness or spatial registration.\n"
            "No HDF5 derivative is generated.\n"
        )
        archive.writestr("README.txt", readme)
    return out.getvalue()


def _build_report(measurements, metadata_upload, ifc_file, component, viewer_upload):
    metadata, metadata_report = _parse_metadata(metadata_upload)
    metadata_report["sha256"] = sha256_uri(metadata_upload.getvalue())
    ifc_bytes = ifc_file.getvalue()
    component = dict(component)
    component.update({"source_file": ifc_file.name, "source_sha256": sha256_uri(ifc_bytes)})
    records, table, validation_report = [], [], []
    seen = set()
    for i, upload in enumerate(measurements, 1):
        name, payload = Path(upload.name).name, upload.getvalue()
        if name.casefold() in seen:
            table.append({"File": name, "Status": "FAIL", "Findings": "Duplicate basename"})
            continue
        seen.add(name.casefold())
        per_file = _record_for_file(metadata, name)
        lab, provenance = _lab_context(metadata, per_file)
        record_id = str(per_file.get("recordIdentifier") or per_file.get("measurementIdentifier") or f"SLDV-{i:03d}")
        sidecar = build_sidecar(name, payload, lab, component, record_id=record_id)
        # Extend, rather than replace, the current profile's sidecar with explicit
        # provenance and source context that the profile builder does not yet emit.
        sidecar["sourceProvenance"] = {
            "measurement": {"fileName": name, "sha256": sha256_uri(payload), "byteSize": len(payload), "preservation": "original bytes"},
            "laboratoryMetadata": {"fileName": metadata_upload.name, "sha256": metadata_report["sha256"], "format": metadata_report.get("format")},
            "fieldProvenance": provenance,
        }
        sidecar["applicationProfile"] = {
            "id": PROFILE_ID, "version": PROFILE_VERSION,
            "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "coordinateRegistration": "not asserted by this workflow",
        }
        cross = validate_sidecar(sidecar, payload, ifc_bytes, {
            "resolved": bool(component.get("global_id")),
            "global_id": component.get("global_id"), "ifc_class": component.get("ifc_class"),
        })
        shacl = validate_shacl(sidecar)
        try:
            parseable = jsonld_is_parseable(sidecar)
        except Exception:
            parseable = False
        preview, plot, plot_note = _read_signal_preview(name, payload)
        diagnostics = inspect_sldv_payload(name, payload)
        missing = [k for k, v in lab.items() if v == "unknown"]
        findings = list(cross)
        if not shacl.get("conforms"):
            findings.append({"code": "SHACL_NONCONFORMANCE", "message": shacl.get("report_text", "")})
        if not parseable:
            findings.append({"code": "JSONLD_PARSE_FAILURE", "message": "JSON-LD parsing failed."})
        if missing:
            findings.append({"code": "MISSING_LAB_CONTEXT", "message": ", ".join(missing)})
        status = "FAIL" if cross or not parseable else ("REVIEW" if not shacl.get("conforms") or missing else "PASS")
        validation = {
            "status": status, "findings": findings, "jsonld_parseable": parseable,
            "shacl": shacl, "cross_layer": {"conforms": not cross, "issues": cross},
            "sourceHashes": {"measurement": sha256_uri(payload), "ifc": sha256_uri(ifc_bytes)},
            "scientificValidity": "not assessed by hashes or structural validation",
        }
        record = {
            "record_id": record_id, "filename": name, "payload": payload,
            "payload_sha256": sha256_uri(payload), "lab_context": lab,
            "field_provenance": provenance, "sidecar": sidecar,
            "payload_analysis": diagnostics, "signal_preview": preview,
            "signal_plot": plot, "signal_note": plot_note, "validation": validation,
        }
        records.append(record)
        row = {"Record": record_id, "File": name, "Bytes": len(payload),
               "SHA-256": sha256_uri(payload), "JSON-LD": "PASS" if parseable else "FAIL",
               "SHACL": "PASS" if shacl.get("conforms") else "FAIL",
               "Cross-layer": "PASS" if not cross else "FAIL",
               "Missing lab fields": len(missing), "Status": status}
        table.append(row)
        validation_report.append({"recordIdentifier": record_id, "sourceFile": name, **validation})
    index = {
        "@context": {"dct": "http://purl.org/dc/terms/", "vibro": "https://w3id.org/vibro-ifc/vocab/"},
        "indexVersion": "1.1", "profile": PROFILE_ID, "profileVersion": PROFILE_VERSION,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "generatedFor": {"ifcFileName": ifc_file.name, "ifcSha256": sha256_uri(ifc_bytes),
                         "ifcSchema": component.get("ifc_schema"), "ifcGlobalId": component.get("global_id"),
                         "ifcEntityType": component.get("ifc_class")},
        "metadataSource": {"fileName": metadata_upload.name, "sha256": metadata_report["sha256"]},
        "records": [{"recordIdentifier": r["record_id"], "sourceFile": r["filename"],
                     "sourceSha256": r["payload_sha256"], "sidecarPath": f"metadata/{r['record_id']}.jsonld",
                     "ifcGlobalId": component.get("global_id"), "validationStatus": r["validation"]["status"]}
                    for r in records],
    }
    return {"records": records, "results": table, "index": index, "metadata": metadata,
            "metadata_report": metadata_report, "validation_report": validation_report,
            "ifc_name": ifc_file.name, "ifc_bytes": ifc_bytes,
            "component": component, "viewer_json": viewer_upload.getvalue() if viewer_upload else None}



def _inspect_project_package(payload: bytes) -> dict[str, Any]:
    """Read the user's existing LDV/IFC package without extracting files to disk."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        entries = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            # Ignore unsafe paths and cap individual reads to avoid ZIP path traversal
            # and unexpectedly huge payloads in a dashboard session.
            path = Path(info.filename)
            if path.is_absolute() or ".." in path.parts or info.file_size > 100_000_000:
                continue
            entries[info.filename] = archive.read(info)
    root = "ldv_project_final/"
    normalized = {name[len(root):] if name.startswith(root) else name: data for name, data in entries.items()}
    def count(prefix: str, suffixes: tuple[str, ...] | None = None) -> int:
        return sum(name.startswith(prefix) and (suffixes is None or name.lower().endswith(suffixes)) for name in normalized)
    return {
        "files": normalized,
        "measurements": count("data/", (".txt", ".csv")),
        "sidecars": count("metadata/points/", (".jsonld",)),
        "history": count("history/", (".jsonld",)),
        "views": count("view/", (".json",)),
        "ifc_files": count("data/", (".ifc",)),
    }


def _render_project_package(package: dict[str, Any]) -> None:
    """Browse the supplied final project archive and its real evidence."""
    files = package["files"]
    st.success("Existing LDV/IFC project package loaded. These are the artifacts from your ZIP; source files are not regenerated.")
    metrics = st.columns(5)
    metrics[0].metric("Measurement files", package["measurements"])
    metrics[1].metric("Point sidecars", package["sidecars"])
    metrics[2].metric("Template history", package["history"])
    metrics[3].metric("Blender configs", package["views"])
    metrics[4].metric("IFC models", package["ifc_files"])

    tabs = st.tabs(["Package overview", "Measurements", "Template & provenance", "Blender / IFC", "Validation", "All files"])
    with tabs[0]:
        readme = next((data for name, data in files.items() if name.lower().endswith("readme.md")), None)
        if readme:
            st.markdown(readme.decode("utf-8", errors="replace"))
        st.write("Package file counts", {
            "all files": len(files), "measurements": package["measurements"],
            "point JSON-LD": package["sidecars"], "template history": package["history"],
            "view configurations": package["views"],
        })
        index = files.get("metadata/scan_index.jsonld")
        if index:
            st.subheader("Scan index")
            try:
                st.json(json.loads(index.decode("utf-8-sig")), expanded=2)
            except Exception as exc:
                st.warning(f"Index could not be parsed as JSON: {exc}")
        if "reports/scan_vs_ifc_hypotheses.png" in files:
            st.image(files["reports/scan_vs_ifc_hypotheses.png"], caption="Scan-to-IFC hypotheses — inspect as hypotheses, not verified registration.")
    with tabs[1]:
        measurement_names = sorted(n for n in files if n.startswith("data/") and n.lower().endswith((".txt", ".csv")))
        if measurement_names:
            selected = st.selectbox("Choose original measurement", measurement_names, key="project_zip_measurement")
            raw = files[selected]
            st.write({"file": selected, "bytes": len(raw), "sha256": sha256_uri(raw)})
            st.download_button("Download original measurement unchanged", raw, Path(selected).name, "text/plain" if selected.lower().endswith(".txt") else "text/csv", key="project_zip_measurement_download")
            preview, plot, note = _read_signal_preview(Path(selected).name, raw)
            if preview is not None:
                st.dataframe(preview, use_container_width=True, hide_index=True)
            if plot is not None and not plot.empty:
                st.line_chart(plot, x="sample_index", y="value", color="signal")
            st.caption(note or "Preview only; downloaded bytes remain unchanged.")
        else:
            st.warning("No TXT/CSV measurements found under data/.")
    with tabs[2]:
        template_names = [n for n in files if n == "metadata/template_sidecar.jsonld" or n.startswith("history/") and n.endswith(".jsonld")]
        other_prov = [n for n in files if "template_provenance" in n.lower()]
        choices = sorted(template_names + other_prov)
        if choices:
            selected = st.selectbox("Template / provenance artifact", choices, key="project_zip_template")
            raw = files[selected]
            if selected.lower().endswith((".json", ".jsonld")):
                try:
                    st.json(json.loads(raw.decode("utf-8-sig")), expanded=3)
                except Exception:
                    st.code(raw.decode("utf-8", errors="replace"))
            elif selected.lower().endswith(".csv"):
                try:
                    st.dataframe(pd.read_csv(io.BytesIO(raw)), use_container_width=True, hide_index=True)
                except Exception:
                    st.code(raw.decode("utf-8", errors="replace"))
            else:
                st.markdown(raw.decode("utf-8", errors="replace"))
            st.download_button("Download selected artifact unchanged", raw, Path(selected).name, key="project_zip_template_download")
        else:
            st.warning("No template or provenance artifacts were found.")
        lab_forms = [n for n in files if n.startswith("sources/") and n.lower().endswith(".docx")]
        if lab_forms:
            st.caption("Lab/source documents included: " + ", ".join(Path(n).name for n in lab_forms))
            for name in lab_forms:
                st.download_button(f"Download {Path(name).name}", files[name], Path(name).name, key="project_zip_source_" + str(lab_forms.index(name)))
    with tabs[3]:
        configs = sorted(n for n in files if n.startswith("view/") and n.lower().endswith(".json"))
        if configs:
            selected = st.selectbox("Blender view configuration", configs, key="project_zip_view")
            raw = files[selected]
            try:
                st.json(json.loads(raw.decode("utf-8-sig")), expanded=3)
            except Exception as exc:
                st.warning(f"Configuration could not be parsed as JSON: {exc}")
                st.code(raw.decode("utf-8", errors="replace"))
            st.download_button("Download view configuration unchanged", raw, Path(selected).name, "application/json", key="project_zip_view_download")
        if "metadata/view_hypothesis.json" in files:
            st.subheader("Coordinate / registration hypothesis")
            try:
                st.json(json.loads(files["metadata/view_hypothesis.json"].decode("utf-8-sig")))
            except Exception:
                st.code(files["metadata/view_hypothesis.json"].decode("utf-8", errors="replace"))
        if "view/scan_on_wall.png" in files:
            st.image(files["view/scan_on_wall.png"], caption="Package preview; does not independently prove spatial registration.")
        if "view/layer_stack.png" in files:
            st.image(files["view/layer_stack.png"], caption="IFC layer-stack preview.")
        ifc_names = sorted(n for n in files if n.lower().endswith(".ifc"))
        for name in ifc_names:
            st.download_button(f"Download IFC: {Path(name).name}", files[name], Path(name).name, "application/octet-stream", key="project_zip_ifc_" + str(ifc_names.index(name)))
        st.warning("The package describes scan-to-IFC axes as a hypothesis. Treat the mapping as unverified until independently registered.")
    with tabs[4]:
        report_names = sorted(n for n in files if n.startswith("reports/") or n.endswith(".ttl") or n.startswith("metadata/shapes"))
        for name in report_names:
            with st.expander(name, expanded=name.endswith("validation_summary.txt")):
                raw = files[name]
                if name.lower().endswith(".csv"):
                    try:
                        st.dataframe(pd.read_csv(io.BytesIO(raw)), use_container_width=True, hide_index=True)
                    except Exception:
                        st.code(raw.decode("utf-8", errors="replace"))
                elif name.lower().endswith((".json", ".jsonld")):
                    try:
                        st.json(json.loads(raw.decode("utf-8-sig")), expanded=2)
                    except Exception:
                        st.code(raw.decode("utf-8", errors="replace"))
                elif name.lower().endswith(".png"):
                    st.image(raw)
                else:
                    st.code(raw.decode("utf-8", errors="replace"))
                st.download_button("Download artifact", raw, Path(name).name, key="project_zip_report_" + str(report_names.index(name)))
    with tabs[5]:
        inventory = pd.DataFrame([{"Path": n, "Bytes": len(v), "SHA-256": sha256_uri(v)} for n, v in sorted(files.items())])
        st.dataframe(inventory, use_container_width=True, hide_index=True)
        selected = st.selectbox("Download any package file", sorted(files), key="project_zip_any_file")
        st.download_button("Download selected file unchanged", files[selected], Path(selected).name, key="project_zip_any_download")

def render_persistent_thesis_workspace() -> None:
    st.markdown("# VIBRO•IFC · Research data workbench")
    st.caption("Persistent batch intake · real source inspection · FAIR-oriented JSON-LD · IFC context · Blender/Bonsai hand-off")
    st.info("Uploaded inputs are retained in this Streamlit session when you navigate between workspace sections. Use **Start new batch** only when you intend to replace the current workspace.")
    if st.button("Start new batch / clear retained uploads", type="secondary", key="clear_persistent_batch"):
        for key in ("vibro_saved_measurements", "vibro_saved_metadata", "vibro_saved_ifc", "vibro_saved_viewer", "vibro_batch_report", "vibro_batch_key", "vibro_project_package"):
            st.session_state.pop(key, None)
        st.rerun()

    project_zip_widget = st.file_uploader("Load your existing LDV/IFC project package (.zip)", type=["zip"], key="persistent_project_zip_widget")
    if project_zip_widget is not None:
        try:
            project_package = _inspect_project_package(project_zip_widget.getvalue())
            st.session_state["vibro_project_package"] = {"name": project_zip_widget.name, "bytes": project_zip_widget.getvalue()}
            _render_project_package(project_package)
            st.divider()
            st.subheader("Or build a new batch from individual uploads")
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            st.error(f"Could not read this project ZIP: {exc}")
    elif st.session_state.get("vibro_project_package"):
        saved_package = st.session_state["vibro_project_package"]
        try:
            _render_project_package(_inspect_project_package(saved_package["bytes"]))
            st.divider()
            st.subheader("Or build a new batch from individual uploads")
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            st.error(f"Could not read retained project ZIP: {exc}")

    c1, c2 = st.columns([1.2, 1])
    with c1:
        measure_widgets = st.file_uploader("Original SLDV TXT/CSV files", type=["txt", "csv"], accept_multiple_files=True, key="persistent_measure_widgets")
        metadata_widget = st.file_uploader("Lab context (DOCX / JSON / JSON-LD / CSV)", type=["docx", "json", "jsonld", "csv"], key="persistent_metadata_widget")
    with c2:
        ifc_widget = st.file_uploader("IFC model", type=["ifc"], key="persistent_ifc_widget")
        viewer_widget = st.file_uploader("Optional Blender/Bonsai viewer JSON (scene / heatmap / point mapping)", type=["json", "jsonld"], key="persistent_viewer_widget")

    if measure_widgets:
        st.session_state["vibro_saved_measurements"] = [{"name": f.name, "bytes": f.getvalue()} for f in measure_widgets]
    _remember_upload(metadata_widget, "vibro_saved_metadata")
    _remember_upload(ifc_widget, "vibro_saved_ifc")
    _remember_upload(viewer_widget, "vibro_saved_viewer")
    saved_measurements = st.session_state.get("vibro_saved_measurements", [])
    saved_meta = st.session_state.get("vibro_saved_metadata")
    saved_ifc = st.session_state.get("vibro_saved_ifc")
    saved_viewer = st.session_state.get("vibro_saved_viewer")
    measurements = [CachedUpload(x["name"], x["bytes"]) for x in saved_measurements]
    metadata = CachedUpload(saved_meta["name"], saved_meta["bytes"]) if saved_meta else None
    ifc = CachedUpload(saved_ifc["name"], saved_ifc["bytes"]) if saved_ifc else None
    viewer = CachedUpload(saved_viewer["name"], saved_viewer["bytes"]) if saved_viewer else None

    if not measurements or not metadata or not ifc:
        st.warning("Add measurement TXT/CSV, laboratory metadata and an IFC model. These will remain in the workspace while you navigate.")
        return
    try:
        components = inspect_ifc_bytes(ifc.getvalue())
    except Exception as exc:
        st.error(f"IFC inspection failed: {type(exc).__name__}: {exc}")
        return
    if not components:
        st.error("No selectable IFC components were found in the model.")
        return
    labels = [f"{x.get('name') or '(unnamed)'} · {x.get('ifc_class')} · {x.get('global_id')}" for x in components]
    previous_guid = st.session_state.get("vibro_selected_global_id")
    default = next((i for i, x in enumerate(components) if x.get("global_id") == previous_guid), 0)
    idx = st.selectbox("IFC target component", range(len(components)), index=default, format_func=lambda i: labels[i], key="persistent_ifc_component")
    component = components[idx]
    st.session_state["vibro_selected_global_id"] = component.get("global_id")
    material = {"measurements": [(x.name, sha256_uri(x.getvalue())) for x in measurements],
                "metadata": sha256_uri(metadata.getvalue()), "ifc": sha256_uri(ifc.getvalue()),
                "component": component.get("global_id"), "viewer": sha256_uri(viewer.getvalue()) if viewer else None,
                "profile": PROFILE_VERSION}
    batch_key = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()
    if st.session_state.get("vibro_batch_key") != batch_key:
        with st.spinner("Inspecting sources, generating sidecars and validating links…"):
            try:
                st.session_state["vibro_batch_report"] = _build_report(measurements, metadata, ifc, component, viewer)
                st.session_state["vibro_batch_key"] = batch_key
            except Exception as exc:
                st.exception(exc)
                return
    report = st.session_state.get("vibro_batch_report")
    if not report:
        return
    rows = report["results"]
    passes = sum(x["Status"] == "PASS" for x in rows)
    reviews = sum(x["Status"] == "REVIEW" for x in rows)
    failures = sum(x["Status"] == "FAIL" for x in rows)
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Measurements", len(report["records"]))
    k2.metric("Pass", passes)
    k3.metric("Review", reviews)
    k4.metric("Fail", failures)
    tabs = st.tabs(["Overview", "Source data", "Metadata & provenance", "JSON-LD", "IFC / Blender", "Validation & downloads"])
    with tabs[0]:
        st.subheader("Batch status")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.subheader("Layered data architecture")
        arch = st.columns(3)
        arch[0].metric("Original payloads", len(report["records"]))
        arch[0].caption("TXT/CSV bytes remain unchanged.")
        arch[1].metric("JSON-LD sidecars", len(report["records"]))
        arch[1].caption("Each record has its own identifier and payload hash.")
        arch[2].metric("IFC target", component.get("ifc_class", "Unknown"))
        arch[2].caption(str(component.get("global_id", "GlobalId unavailable")))
        st.code("Original TXT/CSV → JSON-LD sidecar + field provenance → IFC file hash + GlobalId", language="text")
    with tabs[1]:
        choice = st.selectbox("Inspect source file", range(len(report["records"])), format_func=lambda i: report["records"][i]["filename"], key="persistent_source_choice")
        record = report["records"][choice]
        st.write({"filename": record["filename"], "bytes": len(record["payload"]), "sha256": record["payload_sha256"]})
        st.write(record["payload_analysis"])
        if record["signal_preview"] is not None:
            st.dataframe(record["signal_preview"], use_container_width=True, hide_index=True)
        if record["signal_plot"] is not None and not record["signal_plot"].empty:
            st.line_chart(record["signal_plot"], x="sample_index", y="value", color="signal")
        st.caption(record["signal_note"])
        st.download_button("Download original source bytes", record["payload"], file_name=record["filename"], mime="text/plain" if record["filename"].lower().endswith(".txt") else "text/csv", key="download_source_bytes")
    with tabs[2]:
        record = report["records"][st.selectbox("Record for provenance view", range(len(report["records"])), format_func=lambda i: report["records"][i]["record_id"], key="persistent_provenance_choice")]
        prov_rows = [{"Field": k, "Value": record["lab_context"].get(k), "Status": v.get("status"), "Source": v.get("source"), "Source field": v.get("source_field"), "Method": v.get("method")} for k, v in record["field_provenance"].items()]
        st.dataframe(pd.DataFrame(prov_rows), use_container_width=True, hide_index=True)
        st.json(record["payload_analysis"])
    with tabs[3]:
        record = report["records"][st.selectbox("Sidecar record", range(len(report["records"])), format_func=lambda i: report["records"][i]["record_id"], key="persistent_sidecar_choice")]
        st.json(record["sidecar"], expanded=3)
        st.download_button("Download JSON-LD sidecar", _json_bytes(record["sidecar"]), f"{record['record_id']}.jsonld", "application/ld+json", key="download_sidecar")
    with tabs[4]:
        st.write({"IFC file": ifc.name, "SHA-256": sha256_uri(ifc.getvalue()), "schema": component.get("ifc_schema"), "GlobalId": component.get("global_id"), "entity": component.get("ifc_class"), "name": component.get("name")})
        if viewer:
            st.success(f"Viewer JSON loaded: {viewer.name} · {len(viewer.getvalue()):,} bytes")
            try:
                viewer_obj = json.loads(viewer.getvalue().decode("utf-8-sig"))
                st.json(viewer_obj, expanded=2)
                st.download_button("Download viewer JSON unchanged", viewer.getvalue(), viewer.name, "application/json", key="download_viewer_json")
            except Exception as exc:
                st.error(f"Viewer JSON is not parseable: {exc}")
                st.download_button("Download viewer file unchanged", viewer.getvalue(), viewer.name, "application/json", key="download_viewer_raw")
        else:
            st.warning("No viewer JSON has been supplied in this batch. This workspace can inspect and package an existing Blender/Bonsai JSON export; it does not fabricate a heatmap or claim point-to-IFC registration.")
        st.info("The viewer hand-off preserves the JSON as supplied. Coordinate-frame and vertex/point mapping must be independently evidenced before treating a heatmap as spatially registered to IFC.")
    with tabs[5]:
        st.dataframe(pd.DataFrame([{"Record": x["recordIdentifier"], "File": x["sourceFile"], "Status": x["status"], "Findings": json.dumps(x["findings"], ensure_ascii=False)} for x in report["validation_report"]]), use_container_width=True, hide_index=True)
        st.download_button("Download index / manifest JSON", _json_bytes(report["index"]), "index.json", "application/json", key="download_index")
        st.download_button("Download validation report", _json_bytes(report["validation_report"]), "validation-report.json", "application/json", key="download_validation")
        st.download_button("Download metadata extraction report", _json_bytes(report["metadata_report"]), "metadata-extraction.json", "application/json", key="download_metadata_report")
        st.download_button("Download complete thesis data package (.zip)", _make_bundle(report), "vibro-ifc-thesis-package.zip", "application/zip", type="primary", key="download_complete_package")
        st.caption("The ZIP contains unchanged TXT/CSV payloads, JSON-LD sidecars, index, validation reports, source IFC and optional viewer JSON. Hash/SHACL checks are not scientific validation.")
