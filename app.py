from __future__ import annotations

import streamlit as st
import pandas as pd
from pathlib import Path

from engine import BASE_URL, LINK_VALIDATION_QUERY, LIFECYCLE_QUERY, build_rdf_turtle, evaluate_lifecycle, extract_ifc_walls
from models import MappingAssertion
from visuals import plot_lifecycle_graph, status_color

st.set_page_config(page_title="MappingSeries Lifecycle Validator", page_icon="MS", layout="wide")

DEFAULT_IFC = {
    "GlobalId": "2qL6OSUnz6ZAzEOn1HxeD2",
    "element_type": "IfcWall",
    "wall_name": "Bau2_CLT_140",
    "construction_family": "cross_laminated_timber",
    "thickness_m": 0.176,
    "materials": "GF18 / CLT140 / GF18",
    "native_record_uri": f"{BASE_URL}/record/vabdat-310",
    "pset_record_uri": f"{BASE_URL}/record/vabdat-310",
    "pset_mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-310",
    "mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-310",
    "association_type": "AcousticPerformanceReference",
    "semantic_profile": "HFT-Acoustic-Link-v1",
}
DEFAULT_RDF = {
    "record_uri": f"{BASE_URL}/record/vabdat-310",
    "record_id": "vabdat-310",
    "construction_family": "cross_laminated_timber",
    "thickness_m": 0.176,
    "Rw": 48.0,
    "unit": "dB",
    "assembly": "B_bGF18_bCLT140_bGF18",
    "source_organisation": "ift Rosenheim",
    "report_reference": "M_310",
    "provenance_note": "original prototype source reference",
    "record_available": True,
    "spectrum_adaptation_C": -2.0,
    "spectrum_adaptation_Ctr": -6.0,
    "measurement_method": "ISO 10140-2 laboratory measurement",
    "frequency_data": '[{"frequency_hz": 100, "R_db": 31.2}, {"frequency_hz": 125, "R_db": 34.8}, {"frequency_hz": 160, "R_db": 37.1}]',
    "layer_data": '[{"material_id": "GF18", "thickness_m": 0.018}, {"material_id": "CLT140", "thickness_m": 0.140}, {"material_id": "GF18", "thickness_m": 0.018}]',
}
VABDAT_URL = "https://www.vabdat.de/Bauteil/"
IFC_WALL_OPTIONS = {
    "Bau 1 | metal frame | 0.100 m": {"wall_name": "Bau1_MFC_100", "construction_family": "metal_frame", "thickness_m": 0.100, "materials": "GP12 / M75 / iMW60", "mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-346"},
    "Bau 2 | CLT | 0.176 m": {"wall_name": "Bau2_CLT_140", "construction_family": "cross_laminated_timber", "thickness_m": 0.176, "materials": "GF18 / CLT140 / GF18", "mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-310"},
    "Bau 3 | CLT | 0.190 m": {"wall_name": "Bau3_CLT_080", "construction_family": "cross_laminated_timber", "thickness_m": 0.190, "materials": "CLT80 / aC10 / M75 / iMW60 / GP12 / GP12", "mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-345"},
    "Bau 4 | timber frame | 0.169 m": {"wall_name": "Bau4_TFC_169", "construction_family": "timber_frame", "thickness_m": 0.169, "materials": "OSB12 / M120 / iMW120 / OSB12 / GP12", "mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-328"},
    "Bau 5 | reinforced concrete | 0.100 m": {"wall_name": "Bau5_RCO_100", "construction_family": "reinforced_concrete", "thickness_m": 0.100, "materials": "RCO100", "mapping_series_uri": f"{BASE_URL}/mapping-series/2qL6OSUnz6ZAzEOn1HxeD2-vabdat-303"},
}
RDF_RECORD_OPTIONS = {
    "VaBDat 346 | B_bGP12_frM75 | MFC": {"record_id": "vabdat-346", "construction_family": "metal_frame", "thickness_m": 0.100, "Rw": 44.1, "assembly": "B_bGP12_frM75||iMW60_bGP12", "report_reference": "M_25"},
    "VaBDat 310 | B_bGF18_bCLT140_bGF18 | CLT": {"record_id": "vabdat-310", "construction_family": "cross_laminated_timber", "thickness_m": 0.176, "Rw": 48.0, "assembly": "B_bGF18_bCLT140_bGF18", "report_reference": "M_310"},
    "VaBDat 345 | B_bCLT80_aC10_frM75 | CLT": {"record_id": "vabdat-345", "construction_family": "cross_laminated_timber", "thickness_m": 0.190, "Rw": 51.0, "assembly": "B_bCLT80_aC10_frM75||iMW60_bGP12_bGP12", "report_reference": "M_345"},
    "VaBDat 328 | B_bGP12_bOSB12_frT120 | TFC": {"record_id": "vabdat-328", "construction_family": "timber_frame", "thickness_m": 0.169, "Rw": 46.5, "assembly": "B_bGP12_bOSB12_frT120||iMW120_bOSB12_bGP12", "report_reference": "M_328"},
    "VaBDat 303 | B_bRCO100 | RCO": {"record_id": "vabdat-303", "construction_family": "reinforced_concrete", "thickness_m": 0.100, "Rw": 52.0, "assembly": "B_bRCO100", "report_reference": "M_303"},
}
VALIDATION_PROFILES = {
    "Strict thesis validation": {"thickness_tolerance_m": 0.010, "use_semantic_staleness": True, "require_mapping_series": True},
    "Balanced default": {"thickness_tolerance_m": 0.020, "use_semantic_staleness": True, "require_mapping_series": True},
    "Exploratory validation": {"thickness_tolerance_m": 0.050, "use_semantic_staleness": False, "require_mapping_series": False},
}


def initialize_state() -> None:
    for key, value in DEFAULT_IFC.items():
        st.session_state.setdefault(f"ifc_{key}", value)
    for key, value in DEFAULT_RDF.items():
        st.session_state.setdefault(f"rdf_{key}", value)
    st.session_state.setdefault("lifecycle_histories", {})
    st.session_state.setdefault("assertions", [])
    st.session_state.setdefault("previous_state", None)
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("last_events", [])
    st.session_state.setdefault("thickness_tolerance_m", 0.02)
    st.session_state.setdefault("use_semantic_staleness", True)
    st.session_state.setdefault("require_mapping_series", True)
    st.session_state.setdefault("validation_profile", "Balanced default")
    st.session_state.setdefault("semantic_override_status", "")
    st.session_state.setdefault("semantic_override_note", "")
    st.session_state.setdefault("selected_ifc_wall", "Bau 2 | CLT | 0.176 m")
    st.session_state.setdefault("selected_rdf_record", "VaBDat 310 | B_bGF18_bCLT140_bGF18 | CLT")
    st.session_state.setdefault("real_ifc_walls", [])
    st.session_state.setdefault("real_ifc_path", "data/HFT_Bau4_2025.04.22 (1).ifc")
    st.session_state.setdefault("selected_real_wall", "")


def apply_wall_option() -> None:
    option = IFC_WALL_OPTIONS[st.session_state["selected_ifc_wall"]]
    for field, value in option.items():
        st.session_state[f"ifc_{field}"] = value
    st.session_state["ifc_pset_record_uri"] = st.session_state["ifc_native_record_uri"]
    st.session_state["ifc_pset_mapping_series_uri"] = st.session_state["ifc_mapping_series_uri"]
    activate_wall_history()


def apply_rdf_option() -> None:
    option = RDF_RECORD_OPTIONS[st.session_state["selected_rdf_record"]]
    for field, value in option.items():
        st.session_state[f"rdf_{field}"] = value
    st.session_state["rdf_record_uri"] = f"{BASE_URL}/record/{option['record_id']}"
    st.session_state["ifc_native_record_uri"] = st.session_state["rdf_record_uri"]
    st.session_state["ifc_pset_record_uri"] = st.session_state["rdf_record_uri"]
    st.session_state["ifc_mapping_series_uri"] = f"{BASE_URL}/mapping-series/{st.session_state['ifc_GlobalId']}-{option['record_id']}"
    st.session_state["ifc_pset_mapping_series_uri"] = st.session_state["ifc_mapping_series_uri"]


def apply_validation_profile() -> None:
    profile = VALIDATION_PROFILES[st.session_state["validation_profile"]]
    st.session_state["thickness_tolerance_m"] = profile["thickness_tolerance_m"]
    st.session_state["use_semantic_staleness"] = profile["use_semantic_staleness"]
    st.session_state["require_mapping_series"] = profile["require_mapping_series"]


def load_real_ifc() -> None:
    path = Path(st.session_state["real_ifc_path"])
    if not path.exists():
        st.session_state["real_ifc_error"] = f"IFC file not found: {path}"
        return
    try:
        walls = extract_ifc_walls(str(path))
        st.session_state["real_ifc_walls"] = walls
        st.session_state["selected_real_wall"] = walls[0]["GlobalId"] if walls else ""
        st.session_state.pop("real_ifc_error", None)
    except Exception as error:
        st.session_state["real_ifc_error"] = f"Could not read IFC: {error}"


def apply_real_wall() -> None:
    wall = next((wall for wall in st.session_state["real_ifc_walls"] if wall["GlobalId"] == st.session_state["selected_real_wall"]), None)
    if not wall:
        return
    for field, value in wall.items():
        st.session_state[f"ifc_{field}"] = value


def set_scenario(name: str) -> None:
    if name == "compatible":
        st.session_state["ifc_thickness_m"] = 0.100
        st.session_state["rdf_thickness_m"] = 0.100
        st.session_state["rdf_record_available"] = True
        st.session_state["ifc_construction_family"] = "metal_frame"
        st.session_state["rdf_construction_family"] = "metal_frame"
    elif name == "ambiguous":
        st.session_state["ifc_thickness_m"] = 0.285
        st.session_state["rdf_thickness_m"] = 0.100
        st.session_state["rdf_record_available"] = True
    elif name == "invalid":
        st.session_state["ifc_construction_family"] = "concrete"
        st.session_state["rdf_construction_family"] = "metal_frame"
        st.session_state["rdf_record_available"] = True
    elif name == "break":
        st.session_state["rdf_record_available"] = False
    elif name == "restore":
        st.session_state["rdf_record_available"] = True
    elif name == "rdf_content":
        st.session_state["rdf_Rw"] = 48.0
        st.session_state["rdf_provenance_note"] = "updated laboratory result"
    elif name == "provenance":
        st.session_state["rdf_provenance_note"] = "reissued source report, provenance changed"
        st.session_state["rdf_report_reference"] = "M_25-reissued"
    elif name == "ifc_thickness":
        st.session_state["ifc_thickness_m"] = 0.285
    elif name == "reset":
        for key, value in DEFAULT_IFC.items():
            st.session_state[f"ifc_{key}"] = value
        for key, value in DEFAULT_RDF.items():
            st.session_state[f"rdf_{key}"] = value
        st.session_state["lifecycle_histories"][active_wall_key()] = {"assertions": [], "previous_state": None}
        st.session_state["assertions"] = []
        st.session_state["previous_state"] = None
        st.session_state["last_result"] = None
        st.session_state["last_events"] = []


def current_evidence() -> tuple[dict, dict]:
    ifc = {key: st.session_state[f"ifc_{key}"] for key in DEFAULT_IFC}
    rdf = {key: st.session_state[f"rdf_{key}"] for key in DEFAULT_RDF}
    return ifc, rdf


def active_wall_key() -> str:
    return st.session_state["selected_ifc_wall"]


def activate_wall_history() -> None:
    history = st.session_state["lifecycle_histories"].setdefault(
        active_wall_key(), {"assertions": [], "previous_state": None}
    )
    st.session_state["assertions"] = history["assertions"]
    st.session_state["previous_state"] = history["previous_state"]
    st.session_state["last_result"] = history.get("last_result")
    st.session_state["last_events"] = history.get("last_events", [])


def badge(label: str, status: str, detail: str = "") -> None:
    color = status_color(status)
    st.markdown(f"<div class='status-card'><div class='status-label'>{label}</div><div class='status-value' style='color:{color}'>{status}</div><div class='status-detail'>{detail}</div></div>", unsafe_allow_html=True)


def render_flow(result: dict | None, assertions: list[MappingAssertion]) -> None:
    latest = assertions[-1] if assertions else None
    if result:
        statuses = {
            "IFC Evidence": ("available", "PASS"),
            "Native Link": (result["technical"]["state"], result["technical"]["state"]),
            "MappingSeries": (result["mapping"]["status"], result["mapping"]["status"]),
            "IDS": (result["ids"]["status"], result["ids"]["status"]),
            "bSDD": (result["bsdd"]["status"], result["bsdd"]["status"]),
            "RDF Evidence": ("available" if st.session_state["rdf_record_available"] else "last known", "PASS" if st.session_state["rdf_record_available"] else "BROKEN"),
            "Technical State": (result["technical"]["state"], result["technical"]["state"]),
            "Semantic Status": (result["semantic"]["semantic_status"], result["semantic"]["semantic_status"]),
            "Lifecycle": (f"r{latest.revision_number}" if latest else "not run", "PASS" if latest else "MISSING"),
            "Review": ("required" if result["semantic"]["requires_review"] else "clear", "PARTIAL" if result["semantic"]["requires_review"] else "PASS"),
        }
    else:
        statuses = {key: ("not yet run", "MISSING") for key in ["IFC Evidence", "Native Link", "MappingSeries", "IDS", "bSDD", "RDF Evidence", "Technical State", "Semantic Status", "Lifecycle", "Review"]}
    st.markdown("### Architecture flow")
    st.markdown("<div class='flow-strip'>" + "".join(f"<div class='flow-node'><b>{label}</b><span style='color:{status_color(status)}'>{detail}</span></div><div class='flow-arrow'>-&gt;</div>" for label, (detail, status) in statuses.items())[:-len("<div class='flow-arrow'>-&gt;</div>")] + "</div>", unsafe_allow_html=True)


def render_editors() -> None:
    st.markdown("### Evidence workspace")
    left, right = st.columns(2)
    with left:
        st.markdown("#### IFC-side evidence")
        st.selectbox("IFC wall option", list(IFC_WALL_OPTIONS), key="selected_ifc_wall", on_change=apply_wall_option)
        st.caption(f"Preset component metadata from [VaBDat Bauteile]({VABDAT_URL}); all fields below remain editable.")
        for key in ["GlobalId", "element_type", "wall_name", "construction_family", "materials", "native_record_uri", "pset_record_uri", "pset_mapping_series_uri", "mapping_series_uri", "association_type", "semantic_profile"]:
            st.text_input(key, key=f"ifc_{key}")
        st.number_input("thickness_m", min_value=0.0, step=0.001, format="%.3f", key="ifc_thickness_m")
    with right:
        st.markdown("#### RDF registry / acoustic evidence")
        st.selectbox("Acoustic record option", list(RDF_RECORD_OPTIONS), key="selected_rdf_record", on_change=apply_rdf_option)
        st.caption(f"Choose a sample record, then change acoustic values and registry variables below. Source: [VaBDat Bauteile]({VABDAT_URL})")
        for key in ["record_uri", "record_id", "construction_family", "unit", "assembly", "source_organisation", "report_reference", "provenance_note"]:
            st.text_input(key, key=f"rdf_{key}")
        st.number_input("thickness_m", min_value=0.0, step=0.001, format="%.3f", key="rdf_thickness_m")
        st.number_input("Rw", step=0.1, format="%.1f", key="rdf_Rw")
        st.number_input("spectrum_adaptation_C", step=0.1, format="%.1f", key="rdf_spectrum_adaptation_C")
        st.number_input("spectrum_adaptation_Ctr", step=0.1, format="%.1f", key="rdf_spectrum_adaptation_Ctr")
        st.text_input("measurement_method", key="rdf_measurement_method")
        st.text_area("frequency_data (JSON)", key="rdf_frequency_data", height=120)
        st.text_area("layer_data (JSON)", key="rdf_layer_data", height=120)
        st.checkbox("record_available", key="rdf_record_available")


def render_validation(result: dict | None) -> None:
    if not result:
        st.info("Run the lifecycle assessment to evaluate the current evidence.")
        return
    st.markdown("### Link, IDS and terminology validation")
    checks = [("Link decision", result.get("link_status", result["technical"]["state"])), ("Native link", result["technical"]["state"]), ("Pset link", result.get("pset", {}).get("state", "MISSING")), ("MappingSeries check", result["mapping"]["status"]), ("RDF data decision", result.get("data", {}).get("status", "PASS")), ("Simulation readiness", result.get("simulation", {}).get("status", "PARTIAL")), ("IDS readiness", result["ids"]["status"]), ("bSDD alignment", result["bsdd"]["status"])]
    for check_start in range(0, len(checks), 4):
        cols = st.columns(4)
        for column, (label, status) in zip(cols, checks[check_start:check_start + 4]):
            with column:
                badge(label, status)
    st.caption(f"Expected MappingSeries URI: {result['mapping']['expected']}")
    st.caption("Overall ACCEPTABLE requires Link decision = RESOLVED and RDF data decision = PASS. A changed record may create a new revision while remaining acceptable only when its new evidence passes every data rule.")
    with st.expander("Simulation readiness details", expanded=False):
        simulation_rows = result.get("simulation", {}).get("rows", [])
        if simulation_rows:
            st.dataframe(pd.DataFrame(simulation_rows).astype(str), hide_index=True, use_container_width=True)
        st.caption("Rw is a summary rating. Simulation readiness additionally requires spectrum adaptation terms, a documented method, frequency-band R(f) observations, and layer/build-up data.")
    with st.expander("IDS evidence readiness details", expanded=False):
        ids_rows = result["ids"].get("rows")
        if ids_rows is None:
            current_ifc, _ = current_evidence()
            required_fields = ["GlobalId", "element_type", "construction_family", "thickness_m", "materials", "native_record_uri"]
            optional_fields = ["mapping_series_uri", "association_type", "semantic_profile"]
            ids_rows = [
                {"field": field, "requirement": requirement, "value": current_ifc.get(field, ""), "status": "PASS" if current_ifc.get(field) not in (None, "") else "MISSING"}
                for requirement, fields in (("required", required_fields), ("optional", optional_fields))
                for field in fields
            ]
        st.dataframe(pd.DataFrame(ids_rows).astype(str), hide_index=True, use_container_width=True)
        st.caption("Required fields must be present; optional fields expose semantic-routing readiness. IDS checks IFC evidence readiness, not semantic validity.")
    with st.expander("bSDD terminology alignment details", expanded=False):
        st.dataframe(pd.DataFrame(result["bsdd"]["rows"]).astype(str), hide_index=True, use_container_width=True)
        st.caption("Local concept mapping normalises terminology before semantic assessment.")
    with st.expander("RDF record-data validation details", expanded=False):
        data_rows = result.get("data", {}).get("rows", [])
        if data_rows:
            st.dataframe(pd.DataFrame(data_rows).astype(str), hide_index=True, use_container_width=True)
        st.caption("The RDF data decision checks record identity, family, thickness, Rw, unit, assembly, source, report, provenance, and availability.")
    with st.expander("Overall discrepancy audit", expanded=bool(result.get("discrepancies"))):
        discrepancies = result.get("discrepancies", [])
        if discrepancies:
            st.error(f"{len(discrepancies)} discrepancy or review condition(s) detected")
            st.dataframe(pd.DataFrame(discrepancies).astype(str), hide_index=True, use_container_width=True)
        else:
            st.success("No discrepancies detected. Link, record data, IDS, bSDD, and semantic checks are consistent.")
    st.caption("Overall ACCEPTABLE requires Link decision = RESOLVED and RDF data decision = PASS.")
    if result:
        st.markdown("**Native IFC link vs Pset link**")
        st.write("Native link = the IFC document/reference location used for technical retrieval. Pset link = an IFC property carrying semantic context for enrichment; it must agree with the native link and RDF target but does not replace it.")
        st.dataframe(pd.DataFrame([{
            "link channel": "Native IfcDocumentReference.Location",
            "value": result["technical"].get("ifc_uri", ""),
            "role": "technical retrieval",
            "status": result["technical"]["state"],
        }, {
            "link channel": "Pset record URI",
            "value": result.get("pset", {}).get("pset_uri", ""),
            "role": "semantic enrichment context",
            "status": result.get("pset", {}).get("state", "MISSING"),
        }]).astype(str), hide_index=True, use_container_width=True)



def render_lifecycle_summary(assertions: list[MappingAssertion]) -> None:
    st.markdown("**Current MappingAssertion lifecycle**")
    if not assertions:
        st.info("No MappingAssertion has been created yet. Run the lifecycle assessment to create revision r1.")
        return
    latest = assertions[-1]
    link_status = getattr(latest, "link_status", latest.technical_link_state)
    data_status = getattr(latest, "data_status", "PASS")
    change_categories = [event.category for event in latest.change_events] or ["INITIAL_ASSESSMENT"]
    summary = pd.DataFrame([{
        "current revision": f"r{latest.revision_number}",
        "MappingSeries": latest.mapping_series_uri,
        "Link": link_status,
        "Data": data_status,
        "IDS": latest.ids_status,
        "bSDD": latest.bsdd_status,
        "Semantic": latest.semantic_status,
        "Review": "REQUIRED" if latest.requires_review else "CLEAR",
    }])
    st.dataframe(summary, hide_index=True, use_container_width=True)
    st.caption(f"Latest revision changes: {', '.join(change_categories)}. Earlier revisions remain immutable in the lifecycle timeline below.")


def render_assessment(result: dict | None) -> None:
    if not result:
        return
    st.markdown("### Technical vs semantic assessment")
    status = result["semantic"]["semantic_status"]
    rows = pd.DataFrame([
        ["RESOLVED", "ACCEPTABLE", "reachable and justified"],
        ["RESOLVED", "AMBIGUOUS", "reachable but evidence is insufficient or non-equivalent"],
        ["RESOLVED", "INVALID", "reachable but contradictory association"],
        ["BROKEN", "BROKEN", "external record unavailable"],
        ["RESOLVED", "SEMANTICALLY_STALE", "reachable but prior justification no longer holds"],
    ], columns=["technical state", "semantic status", "interpretation"])
    rows["current"] = ((rows["technical state"] == result["technical"]["state"]) & (rows["semantic status"] == status)).map({True: "CURRENT", False: ""})
    st.dataframe(rows, hide_index=True, use_container_width=True)
    color = status_color(status)
    st.markdown(f"<div class='rationale' style='border-left-color:{color}'><b>{status}</b><br>{result['semantic']['rationale']}</div>", unsafe_allow_html=True)
    st.caption("This validates whether available IFC evidence currently justifies the external RDF record association. It does not validate real acoustic performance.")


def render_timeline(assertions: list[MappingAssertion]) -> None:
    st.markdown("### MappingAssertion lifecycle")
    st.caption(f"Active wall history: {active_wall_key()}")
    if not assertions:
        st.info("No MappingAssertion exists yet.")
        return
    st.caption(f"MappingSeries: {assertions[-1].mapping_series_uri}")
    for assertion in assertions:
        changes = [event.category for event in assertion.change_events] or ["INITIAL_ASSESSMENT"]
        link_status = getattr(assertion, "link_status", assertion.technical_link_state)
        data_status = getattr(assertion, "data_status", "PASS")
        st.markdown(f"<div class='revision'><div class='revision-head'><b>MappingAssertion r{assertion.revision_number}</b><span>{assertion.timestamp}</span></div><div><b style='color:{status_color(assertion.semantic_status)}'>{assertion.semantic_status}</b> | Link {link_status} | Data {data_status} | IDS {assertion.ids_status} | bSDD {assertion.bsdd_status} | {'REVIEW' if assertion.requires_review else 'CLEAR'}</div><div class='status-detail'>{assertion.rationale}</div><div class='change-list'>{', '.join(changes)}</div></div>", unsafe_allow_html=True)
        with st.expander(f"View stored IFC and RDF snapshots for r{assertion.revision_number}"):
            snapshot_left, snapshot_right = st.columns(2)
            with snapshot_left:
                st.dataframe(pd.DataFrame(list(assertion.ifc_snapshot.values.items()), columns=["IFC field", "value"]).astype(str), hide_index=True, use_container_width=True)
            with snapshot_right:
                st.dataframe(pd.DataFrame(list(assertion.rdf_snapshot.values.items()), columns=["RDF field", "value"]).astype(str), hide_index=True, use_container_width=True)


def render_logic_sidebar() -> None:
    with st.sidebar:
        st.markdown("## Validator guide")
        with st.expander("Validation and implementation logic", expanded=True):
            st.markdown("**Overall decision**")
            st.code("ACCEPTABLE = Link RESOLVED AND Data PASS AND IDS PASS AND bSDD not UNALIGNED AND target approved", language="text")
            st.markdown("**Link validation**")
            st.markdown("- Native IFC URI must equal RDF record URI.\n- RDF record must be available.\n- MappingSeries URI must match the GlobalId + record ID when required.")
            st.markdown("**RDF data validation**")
            st.markdown("- Record identity, family, thickness, Rw, dB unit, assembly, source, report, and provenance are checked.\n- Family contradiction is INVALID.\n- Missing or incompatible data is AMBIGUOUS and requires review.\n- A changed record target is UNMATCHED until explicitly approved.")
            st.markdown("**Lifecycle implementation**")
            st.markdown("- Each selected IFC wall has its own history.\n- Every evidence or rule change creates an immutable revision.\n- Identical reruns create no revision.\n- Overrides are stored with a reviewer rationale and become the next baseline.")
            st.markdown("**Standards roles**")
            st.markdown("- IDS checks IFC evidence readiness.\n- bSDD-style mapping normalises terms.\n- PROV-style snapshots and activities explain revision history.")
        with st.expander("Source, enrichment and query logic", expanded=False):
            st.markdown("**Source preservation**")
            st.markdown("- Original IFC remains the source for wall identity and IFC evidence.\n- Original RDF remains the source for acoustic and registry data.\n- Neither source is overwritten; each assessment stores immutable snapshots.")
            st.markdown("**Native IFC link**")
            st.markdown("Technical retrieval link: `IfcDocumentReference.Location` or equivalent native external reference. It locates the RDF/acoustic record.")
            st.markdown("**Pset link**")
            st.markdown("Semantic enrichment link: `Pset_AcousticMapping.RecordURI` and `Pset_AcousticMapping.MappingSeriesURI`. It makes the association discoverable but does not replace the native link.")
            st.markdown("**Query roles**")
            st.markdown("- Link query finds URI-consistent wall-record candidates.\n- Lifecycle query retrieves immutable MappingAssertion revisions and their provenance chain.\n- Queries support discovery and audit; they do not replace compatibility validation.")
            st.markdown("**Enrichment workflow**")
            st.code("IFC + RDF -> links -> MappingSeries -> IDS/bSDD -> data checks -> Link/Data decision -> MappingAssertion", language="text")



def render_mapping_register() -> None:
    rows = []
    for wall_label, wall in IFC_WALL_OPTIONS.items():
        record_label, record = next((label, value) for label, value in RDF_RECORD_OPTIONS.items() if f"-{value['record_id']}" in wall["mapping_series_uri"])
        record_id = record["record_id"]
        rows.append({
            "IFC wall": wall_label,
            "wall name": wall["wall_name"],
            "IFC family": wall["construction_family"],
            "IFC thickness (m)": wall["thickness_m"],
            "RDF record": record_label,
            "record ID": record_id,
            "RDF thickness (m)": record["thickness_m"],
            "Rw (dB)": record["Rw"],
            "MappingSeries": wall["mapping_series_uri"],
        })
    st.markdown("### Wall-to-record register")
    st.caption("This register shows which acoustic RDF record belongs to each IFC wall preset. Values remain editable in Evidence & rules.")
    st.dataframe(pd.DataFrame(rows).astype(str), hide_index=True, use_container_width=True)


def main() -> None:
    initialize_state()
    activate_wall_history()
    render_logic_sidebar()
    st.markdown("<style>body{background:#f3f6f8}.block-container{max-width:1500px;padding-top:2rem}.status-card{background:white;border:1px solid #dce4ea;border-top:4px solid #17324d;padding:12px 10px;min-height:94px}.status-label{font-size:12px;color:#52616b;text-transform:uppercase;letter-spacing:.04em}.status-value{font-size:17px;font-weight:700;margin-top:8px}.status-detail{font-size:12px;color:#667781;margin-top:5px}.flow-strip{display:flex;align-items:stretch;gap:4px;overflow-x:auto;padding:10px 0 18px}.flow-node{background:white;border:1px solid #dce4ea;min-width:112px;padding:10px 8px}.flow-node b,.flow-node span{display:block}.flow-node b{font-size:11px;color:#17324d}.flow-node span{font-size:12px;margin-top:6px}.flow-arrow{align-self:center;color:#8d9aa4;font-size:16px}.rationale{background:white;border-left:5px solid;padding:14px;margin:12px 0}.revision{background:white;border:1px solid #dce4ea;border-left:5px solid #39739d;padding:14px;margin:10px 0}.revision-head{display:flex;justify-content:space-between;color:#17324d}.change-list{font-size:12px;color:#39739d;margin-top:8px}div[data-baseweb='tab-list']{gap:8px;border-bottom:2px solid #c7d2da}button[data-baseweb='tab']{font-size:16px;font-weight:700;padding:14px 20px;min-height:52px;color:#52616b}button[data-baseweb='tab'][aria-selected='true']{color:#17324d;border-bottom:4px solid #39739d}h3{font-size:1.35rem;margin-top:1.6rem}h4{font-size:1.1rem}</style>", unsafe_allow_html=True)
    st.title("MappingSeries Lifecycle Validator")
    st.caption("IFC evidence + native link + MappingSeries routing + IDS readiness + bSDD alignment + RDF evidence")

    render_mapping_register()

    result = st.session_state.get("last_result")
    assertions = st.session_state["assertions"]
    overview_tab, evidence_tab, validation_tab, lifecycle_tab, graph_tab = st.tabs(["Overview", "Evidence & rules", "Validation", "Lifecycle", "Graph"])
    with overview_tab:
        render_flow(result, assertions)
        render_lifecycle_summary(assertions)
        render_assessment(result)
    with evidence_tab:
        st.markdown("### Real IFC source")
        st.caption("Load a real IFC file to replace the simulated IFC-side fields. Acoustic RDF data remains external and is never embedded into the IFC.")
        source_col, load_col = st.columns([4, 1])
        with source_col:
            st.text_input("IFC file path", key="real_ifc_path")
        with load_col:
            st.write("")
            st.button("Load IFC", on_click=load_real_ifc, use_container_width=True)
        if st.session_state.get("real_ifc_error"):
            st.error(st.session_state["real_ifc_error"])
        if st.session_state["real_ifc_walls"]:
            wall_options = [f"{wall['GlobalId']} | {wall['wall_name']} | {wall['thickness_m']:.3f} m" for wall in st.session_state["real_ifc_walls"]]
            labels = {label: wall["GlobalId"] for label, wall in zip(wall_options, st.session_state["real_ifc_walls"])}
            selected_label = next((label for label, global_id in labels.items() if global_id == st.session_state["selected_real_wall"]), wall_options[0])
            st.selectbox("Real IFC wall", wall_options, index=wall_options.index(selected_label), key="selected_real_wall_label")
            st.session_state["selected_real_wall"] = labels[st.session_state["selected_real_wall_label"]]
            if st.button("Use selected real wall", use_container_width=True):
                apply_real_wall()
                st.rerun()
        render_editors()
        st.markdown("### Assessment controls")
        control_left, control_mid, control_right = st.columns([1, 1, 2])
        with control_left:
            st.selectbox("Validation rules", list(VALIDATION_PROFILES), key="validation_profile", on_change=apply_validation_profile)
            st.caption("Profiles define tolerance and semantic/link requirements.")
            st.number_input("thickness_tolerance_m", min_value=0.0, step=0.005, format="%.3f", key="thickness_tolerance_m")
        with control_mid:
            st.checkbox("use_semantic_staleness", key="use_semantic_staleness")
            st.checkbox("require_mapping_series", key="require_mapping_series")
            st.selectbox("Override current status", ["", "ACCEPTABLE", "AMBIGUOUS", "INVALID"], key="semantic_override_status")
            st.text_input("Override rationale", key="semantic_override_note", placeholder="Why should this decision become authoritative?")
        with control_right:
            if st.button("Run lifecycle assessment", type="primary", use_container_width=True):
                ifc, rdf = current_evidence()
                settings = {"validation_profile": st.session_state["validation_profile"], "thickness_tolerance_m": st.session_state["thickness_tolerance_m"], "use_semantic_staleness": st.session_state["use_semantic_staleness"], "require_mapping_series": st.session_state["require_mapping_series"], "semantic_override_status": st.session_state["semantic_override_status"], "semantic_override_note": st.session_state["semantic_override_note"]}
                assertion, new_result, events = evaluate_lifecycle(ifc, rdf, settings, st.session_state["previous_state"], assertions)
                if assertion:
                    assertions.append(assertion)
                    st.session_state["assertions"] = assertions
                st.session_state["last_result"] = new_result
                st.session_state["last_events"] = events
                st.session_state["lifecycle_histories"][active_wall_key()] = {"assertions": assertions, "previous_state": new_result["state"], "last_result": new_result, "last_events": events}
                st.rerun()
    with validation_tab:
        render_validation(result)
    with lifecycle_tab:
        st.markdown("### Change detection")
        events = st.session_state.get("last_events", [])
        if events:
            st.dataframe(pd.DataFrame([event.__dict__ for event in events]).astype(str), hide_index=True, use_container_width=True)
        else:
            st.caption("No changes detected in the latest run. Identical reruns create no new MappingAssertion.")
        render_timeline(assertions)
    with graph_tab:
        st.markdown("### Mapping graph")
        if assertions:
            st.plotly_chart(plot_lifecycle_graph(assertions), use_container_width=True)
            st.download_button("Download lifecycle Turtle", build_rdf_turtle(assertions), "mapping-lifecycle.ttl", "text/turtle")
        else:
            st.caption("Run an assessment to create the graph.")
        with st.expander("Executable architecture queries"):
            st.markdown("**Link validation query**")
            st.code(LINK_VALIDATION_QUERY, language="sparql")
            st.markdown("**Lifecycle query**")
            st.code(LIFECYCLE_QUERY, language="sparql")


if __name__ == "__main__":
    main()
