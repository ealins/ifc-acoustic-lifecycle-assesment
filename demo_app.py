"""
GeoBIM Semantic Lifecycle Engine - Demo Prototype

Research-focused demonstration of IFC-external performance-record 
association lifecycle governance with assessment and change detection.

Focus: Acoustic domain, assessment + change detection only (no RDF viz).
"""

import streamlit as st
import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent))

from lifecycle_engine.ifc_extractor import extract_walls_from_ifc, sample_walls_from_ifc
from lifecycle_engine.assessment import IFCEvidence, RecordEvidence, assess_association, SemanticStatus
from lifecycle_engine.change_detector import detect_changes

st.set_page_config(page_title="GeoBIM Lifecycle Engine", page_icon="🏗️", layout="wide")

st.title("🏗️ GeoBIM Semantic Lifecycle Engine")
st.markdown("**Research Prototype**: IFC-external performance-record association lifecycle governance  \n*Acoustic domain • Assessment + Change Detection • No RDF visualization*")

st.sidebar.markdown("## 📖 Navigation")
page = st.sidebar.radio("Select Page", ["📊 IFC Analysis", "🔍 Semantic Assessment", "📈 Change Detection"])

ifc_path = Path("data/HFT_Bau4_2025.04.22 (1).ifc")
if not ifc_path.exists():
    st.error(f"❌ IFC file not found: {ifc_path}")
    st.stop()

# PAGE 1: IFC Analysis
if page == "📊 IFC Analysis":
    st.header("📊 IFC Model Analysis")
    st.markdown("Extract and analyze walls from your IFC model.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("IFC File Info")
        st.metric("IFC Path", str(ifc_path))
        if st.button("🔄 Extract All Walls"):
            with st.spinner("Parsing IFC file..."):
                walls = extract_walls_from_ifc(str(ifc_path))
                st.session_state['all_walls'] = walls
                st.success(f"✅ Extracted {len(walls)} walls")
    
    with col2:
        st.subheader("Sample for Demo")
        if st.button("📋 Load Sample Walls (5)"):
            with st.spinner("Extracting sample..."):
                sample = sample_walls_from_ifc(str(ifc_path), sample_size=5)
                st.session_state['sample_walls'] = sample
                st.success(f"✅ Loaded {len(sample)} sample walls")
    
    st.divider()
    
    if 'sample_walls' in st.session_state:
        st.subheader("Sampled Walls")
        for i, wall in enumerate(st.session_state['sample_walls'], 1):
            with st.expander(f"Wall {i}: {wall['name']}", expanded=(i==1)):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**GlobalID**: {wall['global_id']}")
                    st.write(f"**Family**: {wall['construction_family']}")
                with col2:
                    thick = wall['total_thickness_m']
                    st.write(f"**Thickness**: {thick} m" if thick else "**Thickness**: N/A")
                    st.write(f"**Materials**: {', '.join(wall['material_evidence']) if wall['material_evidence'] else 'None'}")

# PAGE 2: Semantic Assessment
elif page == "🔍 Semantic Assessment":
    st.header("🔍 Semantic Assessment")
    st.markdown("3-tier assessment determines if an IFC wall can map to an external acoustic record.")
    
    thickness_tolerance = st.slider("Thickness Tolerance (m)", 0.01, 0.10, 0.02, 0.01)
    st.info(f"📏 Using {thickness_tolerance}m tolerance")
    
    st.divider()
    
    if 'sample_walls' not in st.session_state:
        st.session_state['sample_walls'] = sample_walls_from_ifc(str(ifc_path), 3)
    
    mock_records = [
        {'uri': 'https://example.org/record/acoustic/001', 'identifier': 'VAB-DAT-055-GENERIC', 'construction_family': 'Generic Wall', 'total_thickness_m': 0.55, 'available': True, 'assembly': 'Composite', 'record_version': '2025.01'},
        {'uri': 'https://example.org/record/acoustic/002', 'identifier': 'VAB-DAT-100-MASONRY', 'construction_family': 'Masonry Wall', 'total_thickness_m': 0.30, 'available': True, 'assembly': 'Masonry', 'record_version': '2025.01'},
        {'uri': 'https://example.org/record/acoustic/003', 'identifier': 'BSDD-WOOD-FRAME', 'construction_family': 'Wood Frame', 'total_thickness_m': 0.20, 'available': False, 'assembly': 'Wood', 'record_version': '2024.12'},
    ]
    
    st.subheader("Available Acoustic Records")
    for r in mock_records:
        icon = "✅" if r['available'] else "❌"
        st.write(f"{icon} **{r['identifier']}** ({r['construction_family']} • {r['total_thickness_m']}m)")
    
    st.divider()
    
    if st.button("🚀 Run Assessment", type="primary", use_container_width=True):
        st.subheader("Assessment Results")
        assessments = []
        for wall in st.session_state['sample_walls']:
            ifc_ev = IFCEvidence(global_id=wall['global_id'], name=wall['name'], construction_family=wall['construction_family'], total_thickness_m=wall['total_thickness_m'], material_evidence=wall['material_evidence'], model_version=wall['model_version'])
            for record in mock_records:
                rec_ev = RecordEvidence(uri=record['uri'], identifier=record['identifier'], assembly=record['assembly'], construction_family=record['construction_family'], total_thickness_m=record['total_thickness_m'], record_version=record['record_version'], available=record['available'])
                result = assess_association(ifc_ev, rec_ev, thickness_tolerance)
                assessments.append(result)
        
        total = len(assessments)
        acceptable = sum(1 for a in assessments if a.semantic_status == SemanticStatus.ACCEPTABLE)
        ambiguous = sum(1 for a in assessments if a.semantic_status == SemanticStatus.AMBIGUOUS)
        invalid = sum(1 for a in assessments if a.semantic_status == SemanticStatus.INVALID)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Total Pairs", total)
        with c2:
            st.metric("✅ Acceptable", acceptable, f"{acceptable/total*100:.0f}%")
        with c3:
            st.metric("⚠️ Ambiguous", ambiguous, f"{ambiguous/total*100:.0f}%")
        with c4:
            st.metric("❌ Invalid", invalid, f"{invalid/total*100:.0f}%")
        
        st.divider()
        st.subheader("Detailed Results")
        for i, result in enumerate(assessments, 1):
            icon = {"acceptable": "✅", "ambiguous": "⚠️", "invalid": "❌", "broken": "🔴"}.get(result.semantic_status.value, "❓")
            with st.expander(f"{icon} {result.ifc_global_id} ↔ {result.record_id}", expanded=(i <= 2)):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Status**: {result.semantic_status.value}")
                    st.write(f"**Confidence**: {result.confidence:.1%}")
                with c2:
                    st.write(f"**Family**: {'✅' if result.family_match else '❌'}")
                    st.write(f"**Thickness**: {'✅' if result.thickness_match else '❌'}")
                st.write(f"**Reason**: {result.reason}")

# PAGE 3: Change Detection
elif page == "📈 Change Detection":
    st.header("📈 Change Detection & Lifecycle Governance")
    st.markdown("Detect meaningful changes between assessment snapshots.")
    
    st.subheader("Change Detection Demo")
    st.write("**Snapshot 1 (Previous)**")
    c1, c2, c3 = st.columns(3)
    with c1:
        snap1_status = st.selectbox("Status", ["acceptable", "ambiguous", "invalid"], key="snap1_status")
    with c2:
        snap1_conf = st.slider("Confidence", 0.0, 1.0, 0.95, key="snap1_conf")
    with c3:
        snap1_tech = st.selectbox("Technical", ["resolved", "broken"], key="snap1_tech")
    
    st.divider()
    
    st.write("**Snapshot 2 (Current)**")
    c1, c2, c3 = st.columns(3)
    with c1:
        snap2_status = st.selectbox("Status", ["acceptable", "ambiguous", "invalid"], value="ambiguous", key="snap2_status")
    with c2:
        snap2_conf = st.slider("Confidence", 0.0, 1.0, 0.70, key="snap2_conf")
    with c3:
        snap2_tech = st.selectbox("Technical", ["resolved", "broken"], value="resolved", key="snap2_tech")
    
    st.divider()
    
    if st.button("🔍 Detect Changes", type="primary", use_container_width=True):
        previous = {"ifc_global_id": "2a3F4E5D6C7B8A9F0E1D2C3B", "record_id": "VAB-DAT-055-GENERIC", "semantic_status": snap1_status, "confidence": snap1_conf, "technical_status": snap1_tech, "assessment_timestamp": "2025-12-01T10:00:00Z"}
        current = {"ifc_global_id": "2a3F4E5D6C7B8A9F0E1D2C3B", "record_id": "VAB-DAT-055-GENERIC", "semantic_status": snap2_status, "confidence": snap2_conf, "technical_status": snap2_tech, "assessment_timestamp": "2025-12-15T14:30:00Z"}
        
        report = detect_changes(previous, current)
        
        st.subheader("Change Report")
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Changes Detected", len(report.changes))
            st.metric("Overall Category", report.overall_category.value.replace("_", " ").title())
        with c2:
            review_icon = "🚨" if report.requires_review else "✅"
            st.metric("Review Required", f"{review_icon} {'Yes' if report.requires_review else 'No'}")
        
        st.divider()
        
        if report.changes:
            st.subheader("Detected Changes")
            for change in report.changes:
                with st.expander(f"🔄 {change.field_name}"):
                    st.write(f"**Category**: {change.change_category.value}")
                    st.write(f"**Previous**: `{change.previous_value}`")
                    st.write(f"**Current**: `{change.current_value}`")
        else:
            st.info("ℹ️ No changes detected")
        
        st.divider()
        if st.button("💾 Export Report as JSON"):
            report_json = json.dumps(report.to_dict(), indent=2)
            st.download_button("Download Report", report_json, "change_report.json", "application/json")


st.divider()
st.markdown("---\n**GeoBIM Semantic Lifecycle Engine** • Research Prototype  \n*Acoustic domain assessment & change detection • No RDF visualization*  \nBuilt with: ifcopenshell, Streamlit")


