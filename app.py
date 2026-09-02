"""Basic Streamlit dashboard for GeoBIM lifecycle visualization."""

import streamlit as st
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lifecycle_engine.evaluation_runner import run_lifecycle_evaluation


def load_json(path):
    with open(path) as f:
        return json.load(f)


st.set_page_config(page_title="GeoBIM Lifecycle", layout="wide")
st.title("🏗️ GeoBIM IFC-Acoustic Lifecycle")

# Load data
data_dir = project_root / "data"
ifc_wall = load_json(data_dir / "sample_ifc_wall.json")
acoustic_record = load_json(data_dir / "sample_acoustic_record.json")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["IFC Evidence", "Acoustic Record", "Assessment", "Changes"])

# TAB 1: IFC EVIDENCE
with tab1:
    st.header("IFC Building Element")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Global ID", ifc_wall["global_id"][:20])
        st.metric("Name", ifc_wall["name"])
        st.metric("Family", ifc_wall["construction_family"].upper())
        st.metric("Thickness", f"{ifc_wall['total_thickness_m']:.3f} m")
    
    with col2:
        st.write("**Materials:**")
        for mat in ifc_wall["material_evidence"]:
            st.write(f"• {mat}")
    
    with st.expander("Full IFC JSON"):
        st.json(ifc_wall)

# TAB 2: ACOUSTIC RECORD
with tab2:
    st.header("External Acoustic Record")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Identifier", acoustic_record["identifier"])
        st.metric("Family", acoustic_record["construction_family"].upper())
        st.metric("Thickness", f"{acoustic_record['total_thickness_m']:.3f} m")
        st.metric("Rw", f"{acoustic_record['rw']} dB")
    
    with col2:
        st.metric("Source", acoustic_record["source"])
        st.metric("Report", acoustic_record["report_reference"])
        st.metric("Year", acoustic_record["year"])
        status = "🟢 Available" if acoustic_record["available"] else "🔴 Unavailable"
        st.metric("Status", status)
    
    with st.expander("Full Record JSON"):
        st.json(acoustic_record)

# TAB 3: ASSESSMENT
with tab3:
    st.header("Semantic Assessment")
    
    evaluation = run_lifecycle_evaluation(ifc_wall, acoustic_record)
    assessment = evaluation["assessment"]
    
    col1, col2, col3, col4 = st.columns(4)
    
    status = assessment["semantic_status"]
    colors = {"acceptable": "🟢", "ambiguous": "🟡", "broken": "🔴", "invalid": "🟠"}
    color = colors.get(status, "⚪")
    
    with col1:
        st.metric("Semantic", f"{color} {status.upper()}")
    with col2:
        st.metric("Technical", assessment["technical_status"].upper())
    with col3:
        st.metric("Confidence", f"{assessment['confidence']:.0%}")
    with col4:
        review = "⚠️ YES" if evaluation["requires_review"] else "✅ NO"
        st.metric("Review", review)
    
    st.divider()
    st.info(assessment["reason"])
    
    st.subheader("Evidence Matching")
    
    ifc_t = ifc_wall["total_thickness_m"]
    rec_t = acoustic_record["total_thickness_m"]
    diff = abs(ifc_t - rec_t)
    thick_match = "✅" if diff <= 0.02 else "❌"
    
    ifc_f = ifc_wall["construction_family"]
    rec_f = acoustic_record["construction_family"]
    fam_match = "✅" if ifc_f == rec_f else "❌"
    
    st.write(f"{thick_match} **Thickness:** IFC {ifc_t:.3f}m vs Record {rec_t:.3f}m (Δ {diff:.3f}m)")
    st.write(f"{fam_match} **Family:** IFC {ifc_f} vs Record {rec_f}")

# TAB 4: CHANGES
with tab4:
    st.header("Change Detection")
    
    st.write("**Scenario: Identical Rerun**")
    
    eval1 = run_lifecycle_evaluation(ifc_wall, acoustic_record)
    eval2 = run_lifecycle_evaluation(ifc_wall, acoustic_record, previous_assessment=eval1["assessment"])
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("First Run", eval1["revision_action"])
        st.write(f"Status: {eval1['assessment']['semantic_status']}")
    
    with col2:
        st.metric("Second Run", eval2["revision_action"])
        st.write(f"Status: {eval2['assessment']['semantic_status']}")
    
    st.divider()
    
    if eval2["change_report"]:
        cr = eval2["change_report"]
        st.write(f"**Changes:** {cr.get('overall_category', 'no_change')}")
        st.write(f"**Meaningful:** {cr.get('has_meaningful_changes', False)}")
        
        if cr.get("events"):
            st.write(f"**{len(cr['events'])} events detected**")
            for e in cr["events"]:
                st.write(f"  • {e['category']}: {e['field']}")
    else:
        st.success("✅ No changes - no revision needed!")
