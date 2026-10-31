"""Dashboard page: how the v0.6 sidecar architecture works.

Shows the three decoupled layers (measurement data, sidecar, IFC model), the
checks the engine runs on a record, the class-level node graph, and what the
Blender add-on takes from the same record.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from vibro_ifc import engine as sv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "ldv"

# one colour per steward group; own terms stand out
STEWARD_COLOURS = {
    "W3C": "#5BA8E5", "W3C / OGC": "#4FC3C9", "W3C LBD CG": "#8FA8E8", "OGC": "#7BD389",
    "ISO 21597": "#E5B85B", "buildingSMART": "#E58F5B", "DCMI": "#B58FE5", "SPDX": "#9AA8B8",
    "QUDT": "#C9D46A", "schema.org": "#8FD0B0", "FOAF": "#8FA0B8", "this thesis": "#F0645A", "unknown": "#7A8798",
}


@st.cache_data(show_spinner=False)
def _load(path: str, mtime: float):
    graph = sv.load_record(path)
    return {
        "summary": sv.summary(graph),
        "validation": sv.validate_record(graph),
        "gaps": sv.gap_report(graph),
        "vocabularies": sv.vocabulary_table(graph),
        "graph_core": sv.class_graph(graph, include_quality=False),
        "graph_full": sv.class_graph(graph, include_quality=True),
    }


@st.cache_data(show_spinner=False)
def _checks(path: str, mtime: float, data_dir: str):
    return sv.data_checks(sv.load_record(path), data_dir or None)


def _active_source():
    """(records, default data folder, label): repository records, or the last build when chosen."""
    build = st.session_state.get("build")
    if build and st.session_state.get("use_build"):
        return sv.list_records(build["records_dir"]), str(build["data_dir"]), "your last build"
    return sv.list_records(), str(DEFAULT_DATA_DIR) if DEFAULT_DATA_DIR.is_dir() else "", "repository records"


def _node_graph_figure(data: dict, show_labels: bool):
    import networkx as nx
    import plotly.graph_objects as go

    g = nx.Graph()
    for node in data["nodes"]:
        g.add_node(node["id"], **node)
    for link in data["links"]:
        if g.has_edge(link["source"], link["target"]):
            g[link["source"]][link["target"]]["labels"].append(link["label"])
        else:
            g.add_edge(link["source"], link["target"], labels=[link["label"]])
    pos = nx.spring_layout(g, seed=7, k=1.1, iterations=200)

    ex, ey, mx, my, mt = [], [], [], [], []
    for a, b, attrs in g.edges(data=True):
        ex += [pos[a][0], pos[b][0], None]
        ey += [pos[a][1], pos[b][1], None]
        mx.append((pos[a][0] + pos[b][0]) / 2)
        my.append((pos[a][1] + pos[b][1]) / 2)
        mt.append(", ".join(sorted(set(attrs["labels"]))))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(width=1, color="rgba(150,170,195,.35)"), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=mx, y=my, mode="markers", marker=dict(size=7, color="rgba(0,0,0,0)"), text=mt, hoverinfo="text", showlegend=False))
    for steward in sorted({n["steward"] for n in data["nodes"]}):
        members = [n for n in data["nodes"] if n["steward"] == steward]
        fig.add_trace(go.Scatter(
            x=[pos[n["id"]][0] for n in members], y=[pos[n["id"]][1] for n in members],
            mode="markers+text" if show_labels else "markers",
            text=[n["label"] for n in members], textposition="top center", textfont=dict(size=10, color="#C9D6E6"),
            marker=dict(size=[12 + 6 * min(n["count"], 8) ** 0.5 * 2 for n in members],
                        color=STEWARD_COLOURS.get(steward, "#7A8798"),
                        line=dict(width=2 if steward == "this thesis" else 0.5, color="#FFFFFF")),
            hovertext=[f"{n['label']}<br>{n['count']} instance(s)<br>{steward}" for n in members], hoverinfo="text", name=steward,
        ))
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False), legend=dict(orientation="h", y=-0.05), font=dict(color="#C9D6E6"))
    return fig


def _layers(info: dict, checks: list[dict], validation: dict) -> None:
    status = {c["role"]: c["status"] for c in checks}
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.caption("LAYER 1 · MEASUREMENT DATA")
        st.markdown(f"**{info['measurement_file'] or '-'}**")
        st.write("Polytec text file, one per scan point. Kept unchanged.")
        st.metric("Checksum", status.get("Measurement file", "-"))
    with c2.container(border=True):
        st.caption("LAYER 2 · SIDECAR (JSON-LD)")
        st.markdown(f"**{info['record']}**")
        st.write(f"Profile v{info['profile']}, {info['triples']} statements, built from published vocabularies.")
        st.metric("SHACL", "conforms" if validation["conforms"] else f"{validation['violations']} violation(s), {validation['warnings']} warning(s)")
    with c3.container(border=True):
        st.caption("LAYER 3 · IFC MODEL (UNCHANGED)")
        st.markdown(f"**{info['ifc_file'] or '-'}**")
        st.write(f"Element: {info['ifc_label'] or '-'}")
        st.code(info["global_id"] or "-", language="text")
        st.metric("Checksum", status.get("IFC model", "-"))
    st.caption("The sidecar points to the data file and to the IFC element by checksum and GlobalId. The data file and the IFC model know nothing about each other.")


def render_sidecar_v06() -> None:
    st.title("Sidecar architecture (profile v0.6)")
    st.caption("Three decoupled layers. This page is the engine: it reads a record, checks it, and shows what it contains. Blender is the visualisation.")

    records, default_data, label = _active_source()
    if not records:
        st.error("No records found. Use 'Build from new data' to create some.")
        return
    st.caption(f"Showing: {label}.")
    left, right = st.columns([1, 2])
    chosen = left.selectbox("Record", records, format_func=lambda p: p.stem)
    data_dir = right.text_input("Folder with the TXT files and the IFC (optional, for checksum checks)", value=default_data, key=f"sidecar_data_{label}")

    mtime = chosen.stat().st_mtime
    data = _load(str(chosen), mtime)
    checks = _checks(str(chosen), mtime, data_dir)
    info, validation, gaps = data["summary"], data["validation"], data["gaps"]

    tabs = st.tabs(["Architecture", "Node graph", "Checks and gaps", "Blender"])

    with tabs[0]:
        _layers(info, checks, validation)
        st.subheader("What the record says about the link")
        a, b, c = st.columns(3)
        a.metric("Association level", info["association_level"] or "-")
        b.metric("Registration", info["registration"] or "-")
        c.metric("Position hypothesis", "declared by model" if "not confirmed" in info["hypothesis_status"] else (info["hypothesis_status"] or "-"))
        st.write(f"Source of the hypothesis: {info['hypothesis_source'] or '-'}. Status: **{info['hypothesis_status'] or '-'}**.")
        if checks and all(c_["status"] == "file not found" for c_ in checks):
            st.info("The data files were not found in the folder above, so the checksums were not compared. Set the folder to run the comparison.")
        elif checks:
            st.dataframe(pd.DataFrame(checks), use_container_width=True, hide_index=True)

    with tabs[1]:
        include_quality = st.toggle("Show quality measurements (dqv)", value=False)
        show_labels = st.toggle("Show class labels", value=True)
        st.plotly_chart(_node_graph_figure(data["graph_full" if include_quality else "graph_core"], show_labels), use_container_width=True)
        st.caption("One node per class, sized by number of instances. Colour is the vocabulary steward; thesis-specific terms have a white outline. Hover an edge midpoint for the property.")
        st.subheader("Vocabularies in this record")
        st.dataframe(pd.DataFrame(data["vocabularies"]), use_container_width=True, hide_index=True)

    with tabs[2]:
        st.subheader("SHACL result")
        st.write("Violation = mandatory field missing. Warning = recommended field or a known gap.")
        if validation["results"]:
            st.dataframe(pd.DataFrame(validation["results"]), use_container_width=True, hide_index=True)
        else:
            st.success("No findings.")
        st.subheader("Fields the record declares itself")
        g1, g2 = st.columns(2)
        g1.markdown("**Absent** (not in the lab form or files)")
        g1.write(", ".join(gaps["absent"]) or "-")
        g2.markdown("**Unresolved** (sources disagree or need confirmation)")
        g2.write(", ".join(gaps["unresolved"]) or "-")
        st.caption(f"{gaps['units_pending']} unit(s) have no resolved QUDT IRI yet.")

    with tabs[3]:
        st.subheader("What Blender uses from this record")
        st.dataframe(pd.DataFrame([
            {"Part": "Points, wall, transform, spectra", "Source in the add-on (first version)": "Separate view configuration and spectra cache"},
            {"Part": "Tree panel", "Source in the add-on (first version)": "This sidecar, read for display"},
            {"Part": "Status flags", "Source in the add-on (first version)": "This sidecar compared with the real files (checksums, header coordinates, IFC element)"},
        ]), use_container_width=True, hide_index=True)
        st.write("Next step: generate the view configuration from the sidecar so a change in the record changes the view.")
        st.download_button("Download this record (JSON-LD)", Path(chosen).read_bytes(), file_name=Path(chosen).name, mime="application/ld+json")


# ----------------------------------------------------------------- all records
@st.cache_data(show_spinner=False)
def _all_records(data_dir: str, stamp: float, records_dir: str):
    rows = []
    for path in sv.list_records(records_dir):
        graph = sv.load_record(path)
        info, report = sv.summary(graph), sv.validate_record(graph)
        checks = sv.data_checks(graph, data_dir or None)
        rows.append({
            "Record": path.stem,
            "Measurement file": info["measurement_file"],
            "Violations": report["violations"],
            "Warnings": report["warnings"],
            "Association": info["association_level"],
            "Registration": info["registration"],
            "Checksums": ", ".join(sorted({c["status"] for c in checks})) or "-",
        })
    return rows


def _records_stamp(records) -> float:
    return max((p.stat().st_mtime for p in records), default=0.0)


def render_overview() -> None:
    st.title("Vibrometry measurements linked to an IFC model")
    st.caption("A metadata profile (JSON-LD sidecar and SHACL shapes) that links SLDV measurement files and lab context to an IFC element. The IFC stays untouched.")
    records, default_data, label = _active_source()
    if not records:
        st.info("No records yet. Use 'Build from new data' in the sidebar.")
        return
    rows = _all_records(default_data, _records_stamp(records), str(records[0].parent))
    st.caption(f"Showing: {label}.")
    a, b, c, d = st.columns(4)
    a.metric("Records (scan points)", len(rows))
    b.metric("Mandatory fields missing", sum(r["Violations"] for r in rows))
    c.metric("Recommended fields missing", sum(r["Warnings"] for r in rows))
    d.metric("Registration established", sum(r["Registration"] != "not established" for r in rows))

    st.subheader("Three decoupled layers")
    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.caption("LAYER 1")
        st.markdown("**Measurement data**")
        st.write("Polytec text files, one per scan point. Kept unchanged. Identified by file name and SHA-256.")
    with c2.container(border=True):
        st.caption("LAYER 2")
        st.markdown("**Sidecar**")
        st.write("JSON-LD record per point, built from published vocabularies. Describes the data, the lab context and the link to the IFC. Checked by SHACL.")
    with c3.container(border=True):
        st.caption("LAYER 3")
        st.markdown("**IFC model**")
        st.write("The building model, not modified. The element is referenced by GlobalId and file checksum.")
    st.write("**Blender** is the visualisation. In its first version it reads the sidecar for display and checks, and draws from a separate view configuration. **This dashboard** is the engine that reads, validates and explains the records.")
    st.info("Scope: the link is at component level. The position of the scan points on the wall is a hypothesis from the IFC model and is not confirmed by the lab. The profile does not claim 3D registration or any change to the IFC schema.")


def render_records() -> None:
    st.title("All records")
    records, default_data, label = _active_source()
    if not records:
        st.info("No records yet. Use 'Build from new data' in the sidebar.")
        return
    st.caption(f"Showing: {label}.")
    data_dir = st.text_input("Folder with the TXT files and the IFC (optional)", value=default_data, key=f"records_data_{label}")
    rows = _all_records(data_dir, _records_stamp(records), str(records[0].parent))
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption("Violation = mandatory field missing. Warning = recommended field or a known gap. Records are in profile/v0.6/records.")


def render_method() -> None:
    st.title("Method and scope")
    st.markdown(
        "- **Question:** which metadata let a vibrometry measurement be found, understood and reused together with the building model it was taken on.\n"
        "- **Approach:** an application profile made mostly of existing vocabularies, checked with SHACL, with only a few terms of its own.\n"
        "- **Link to the IFC:** by GlobalId, file checksum and an element fingerprint. No property set is required in the IFC.\n"
        "- **Data format:** the TXT export (CSV also accepted). HDF5 is a later option.\n"
        "- **Evaluation:** selected FAIR indicators, change scenarios, and competency queries."
    )
    graph = sv.load_record(sv.list_records()[0])
    st.subheader("Vocabularies used in a record")
    st.dataframe(pd.DataFrame(sv.vocabulary_table(graph)), use_container_width=True, hide_index=True)
    st.subheader("Not claimed")
    st.markdown(
        "- FAIR certification, or scientific validity of the measured values.\n"
        "- Registration of the scan points on the wall.\n"
        "- A change to the IFC schema, or dense vibration values stored in IFC."
    )


# ------------------------------------------------------------ build from new data
def render_build() -> None:
    from vibro_ifc import build_service as bs

    st.title("Build from new data")
    st.caption("Upload an IFC and the Polytec TXT files of a new measurement. The builder writes one v0.6 record per file, a spectra cache and a Blender view configuration. Your files are not modified.")
    ifc_file = st.file_uploader("IFC model (a single wall works best)", type=["ifc"])
    txt_files = st.file_uploader("Polytec TXT files (one per scan point)", type=["txt"], accept_multiple_files=True)
    template = st.file_uploader("Lab facts (JSON-LD template, optional)", type=["jsonld", "json"])
    if template is None:
        st.warning("No template uploaded: the built-in template holds the lab facts of the CLT10-4-3 test (method, instrument, excitation as reported). For a different test, upload your own template, or those facts will be wrong.")
    with st.expander("Options"):
        c1, c2, c3 = st.columns(3)
        freq = c1.number_input("Default frequency (Hz)", min_value=1.0, value=1000.0)
        channel = c2.selectbox("Default channel", ["Z", "X", "Y", "NORM"])
        face = c3.text_input("Reference face name", value="RF_A")

    if st.button("Build records", type="primary", disabled=not (ifc_file and txt_files)):
        with st.spinner("Reading the IFC geometry and the measurement files..."):
            try:
                result = bs.build_from_uploads(
                    ifc_file.name, ifc_file.getvalue(), {f.name: f.getvalue() for f in txt_files},
                    template.getvalue() if template else None,
                    default_freq_hz=freq, default_channel=channel, face_name=face,
                )
            except bs.BuildError as exc:
                st.error(str(exc))
                return
        st.session_state["build"] = result
        st.session_state["use_build"] = True
        st.session_state["build_zip"] = bs.package_zip(result)

    result = st.session_state.get("build")
    if not result:
        return
    st.success(f"{len(result['records'])} record(s) built. The Sidecar v0.6 and All records pages now show this build.")
    rows = _all_records(str(result["data_dir"]), _records_stamp(result["records"]), str(result["records_dir"]))
    a, b, c = st.columns(3)
    a.metric("Records", len(rows))
    b.metric("Files excluded", len(result["excluded"]))
    c.metric("Mandatory fields missing", sum(r["Violations"] for r in rows))
    if result["excluded"]:
        st.warning("These files were not used:")
        st.dataframe(pd.DataFrame([{"File": k, "Reason": v} for k, v in result["excluded"].items()]), use_container_width=True, hide_index=True)
    frame = result.get("frame", {})
    st.write(f"Position hypothesis: {frame.get('source', '-')}. Status: **{frame.get('status', '-')}**.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.download_button("Download the build (records, spectra cache, Blender view config, manifest)", st.session_state.get("build_zip", b""), file_name="vibro_ifc_build.zip", mime="application/zip")
    st.caption("To use the build in Blender, place the zip contents next to your TXT files and the IFC, as in the original package.")
