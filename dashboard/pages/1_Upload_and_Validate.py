"""IFC-VaBDat Validator - Upload & Validate with Architecture"""
import streamlit as st
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from dashboard.backend.validators import TieredValidator, WallEvidence, RecordEvidence
from dashboard.backend.ifc_parser import extract_walls_from_ifc
from dashboard.backend.rdf_registry import RDFRegistryBuilder, RDFVisualizationHelper

MOCK_RECORDS = {
    "vabdat-310 (Masonry, 0.185m)": {
        "uri": "https://example.org/hft-acoustic/record/vabdat-310",
        "identifier": "vabdat-310", "assembly": "Exterior Wall Assembly",
        "construction_family": "Masonry Wall", "total_thickness_m": 0.185,
        "record_version": "prototype-v2", "available": True,
    },
    "vabdat-311 (Timber, 0.150m)": {
        "uri": "https://example.org/hft-acoustic/record/vabdat-311",
        "identifier": "vabdat-311", "assembly": "Timber Exterior Wall",
        "construction_family": "Timber Frame", "total_thickness_m": 0.150,
        "record_version": "prototype-v2", "available": True,
    },
    "vabdat-312 (Steel, 0.200m)": {
        "uri": "https://example.org/hft-acoustic/record/vabdat-312",
        "identifier": "vabdat-312", "assembly": "Steel Frame Wall Assembly",
        "construction_family": "Steel Frame", "total_thickness_m": 0.200,
        "record_version": "prototype-v2", "available": True,
    },
}

MOCK_WALLS = {
    "Wall_001 (Masonry, 0.185m)": {
        "global_id": "2qL6OSUnz6ZAzEOn1HxeD2", "name": "Wall_001",
        "construction_family": "Masonry Wall", "total_thickness_m": 0.185,
        "material_evidence": ["Brick", "Mortar", "Insulation"], "model_version": "bau1-2026-02-18",
    },
    "Wall_002 (Timber, 0.150m)": {
        "global_id": "3rM7PQVoa7aByFpO2IyeE3", "name": "Wall_002",
        "construction_family": "Timber Frame", "total_thickness_m": 0.150,
        "material_evidence": ["Wood", "Insulation", "Gypsum"], "model_version": "bau1-2026-02-18",
    },
    "Wall_003 (Steel, 0.200m)": {
        "global_id": "4sN8QRWpb8bCzGqP3JzfF4", "name": "Wall_003",
        "construction_family": "Steel Frame", "total_thickness_m": 0.200,
        "material_evidence": ["Steel", "Insulation", "Brick"], "model_version": "bau1-2026-02-18",
    },
}

for k in ["validation_result", "wall_evidence", "record_evidence", "extracted_walls"]:
    if k not in st.session_state:
        st.session_state[k] = None if k != "extracted_walls" else {}

# Auto-populate with first mock data on first load (for immediate demo)
if st.session_state.wall_evidence is None:
    first_wall = list(MOCK_WALLS.values())[0]
    st.session_state.wall_evidence = first_wall

if st.session_state.record_evidence is None:
    first_record = list(MOCK_RECORDS.values())[0]
    st.session_state.record_evidence = first_record

st.set_page_config(page_title="IFC-VaBDat Validator", page_icon="✅", layout="wide")
st.title("🏗️ IFC-VaBDat Bi-directional Lifecycle Validator")

with st.sidebar:
    with st.expander("📐 3-Tier Architecture", expanded=True):
        st.markdown("""
**TIER 1: LINK** (Structural Connectivity)
- ✓ IFC GlobalID exists | ✗ Missing/malformed
- ✓ URI resolvable | ✗ Dead link
- ✓ Names correlate | ✗ No link
→ Purpose: Ensure wall & record can connect

**TIER 2: MAPPING** (Semantic Correspondence)
- ✓ Family matches | ✗ Masonry≠Steel
- ✓ Thickness ±20mm | ✗ Too different
- ✓ Materials overlap | ✗ No common
→ Purpose: Verify properties correspond

**TIER 3: LIFECYCLE** (Audit Trail & Stability)
- ✓ Model version | ✗ No version
- ✓ Record version | ✗ No version
- ✓ Semantics valid | ✗ Stale
→ Purpose: Enable auditable history
        """)
    
    with st.expander("📊 Status Reference"):
        st.markdown("""
✅ ACCEPTABLE → Ready for production
⚠️ AMBIGUOUS → Manual review needed
❌ INVALID → Fails checks
❓ UNMATCHED → No record
🔗 BROKEN → Record unavailable
⏱️ SEMANTICALLY_STALE → No longer matches
        """)

tab1, tab2 = st.tabs(["✏️ Manual Entry", "📊 Results"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🧱 IFC Wall")
        ifc_file = st.file_uploader("Upload IFC", type=["ifc"])
        if ifc_file:
            try:
                tmp = Path(f"/tmp/{ifc_file.name}")
                tmp.parent.mkdir(parents=True, exist_ok=True)
                tmp.write_bytes(ifc_file.getbuffer())
                extracted = extract_walls_from_ifc(tmp)
                ew = {}
                for w in extracted:
                    if w.get("extraction_success"):
                        k = f"{w['name']} ({w['construction_family']}, {w['total_thickness_m']:.3f}m)"
                        ew[k] = w
                if ew:
                    st.success(f"✅ {len(ew)} walls")
                    st.session_state.extracted_walls = ew
            except Exception as e:
                st.error(f"Error: {e}")
        
        walls = st.session_state.extracted_walls or MOCK_WALLS
        sel_wall = st.selectbox("Wall", list(walls.keys()), label_visibility="collapsed")
        wd = walls[sel_wall]
        
        st.text_input("GlobalID", wd["global_id"], key="wgid")
        st.text_input("Name", wd["name"], key="wname")
        st.selectbox("Family", ["Masonry Wall", "Timber Frame", "Steel Frame", "Concrete"],
                    index=["Masonry Wall", "Timber Frame", "Steel Frame", "Concrete"].index(wd["construction_family"]), key="wfam")
        st.number_input("Thickness (m)", 0.05, 1.0, wd["total_thickness_m"], 0.01, key="wthick")
        st.multiselect("Materials", ["Brick", "Mortar", "Insulation", "Wood", "Gypsum", "Steel"], 
                      default=wd["material_evidence"], key="wmat")
        st.text_input("Model Version", wd["model_version"], key="wver")
        
    
    with col2:
        st.markdown("### 🔊 bSDD Record")
        sel_rec = st.selectbox("Record", list(MOCK_RECORDS.keys()), label_visibility="collapsed")
        rd = MOCK_RECORDS[sel_rec]
        
        st.text_input("URI", rd["uri"], key="ruri")
        st.text_input("ID", rd["identifier"], key="rid")
        st.text_input("Assembly", rd["assembly"], key="rasm")
        st.selectbox("Family", ["Masonry Wall", "Timber Frame", "Steel Frame", "Concrete"],
                    index=["Masonry Wall", "Timber Frame", "Steel Frame", "Concrete"].index(rd["construction_family"]), key="rfam")
        st.number_input("Thickness (m)", 0.05, 1.0, rd["total_thickness_m"], 0.01, key="rthick")
        st.text_input("Record Version", rd["record_version"], key="rver")
        st.checkbox("Available", rd["available"], key="ravail")
        
        st.session_state.record_evidence = {
            "uri": st.session_state.get("ruri", rd["uri"]),
            "identifier": st.session_state.get("rid", rd["identifier"]),
            "assembly": st.session_state.get("rasm", rd["assembly"]),
            "construction_family": st.session_state.get("rfam", rd["construction_family"]),
            "total_thickness_m": st.session_state.get("rthick", rd["total_thickness_m"]),
            "record_version": st.session_state.get("rver", rd["record_version"]),
            "available": st.session_state.get("ravail", rd["available"]),
        }

with tab2:
    if st.session_state.wall_evidence and st.session_state.record_evidence:
        if st.button("▶️ Run 3-Tier Validation", type="primary", use_container_width=True):
            try:
                wall = WallEvidence(**st.session_state.wall_evidence)
                record = RecordEvidence(**st.session_state.record_evidence)
                result = TieredValidator(0.02).validate_all(wall, record)
                st.session_state.validation_result = result
                st.success("✅ Validation complete!")
            except Exception as e:
                st.error(f"❌ Error: {e}")
        
        if st.session_state.validation_result:
            r = st.session_state.validation_result
            st.markdown(f"### **{r.overall_status.value}**\n{r.rationale}")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### 🔗 Tier 1: Link")
                p = sum(1 for x in r.tier_1_link if x.passed)
                st.metric("Passed", f"{p}/{len(r.tier_1_link)}")
                for c in r.tier_1_link:
                    st.write(f"{'✅' if c.passed else '❌'} {c.name}\n{c.description}")
                    if c.details:
                        st.caption(c.details)
            with c2:
                st.markdown("#### 🗺️ Tier 2: Mapping")
                p = sum(1 for x in r.tier_2_mapping if x.passed)
                st.metric("Passed", f"{p}/{len(r.tier_2_mapping)}")
                for c in r.tier_2_mapping:
                    st.write(f"{'✅' if c.passed else '❌'} {c.name}\n{c.description}")
                    if c.details:
                        st.caption(c.details)
            with c3:
                st.markdown("#### 🔄 Tier 3: Lifecycle")
                p = sum(1 for x in r.tier_3_lifecycle if x.passed)
                st.metric("Passed", f"{p}/{len(r.tier_3_lifecycle)}")
                for c in r.tier_3_lifecycle:
                    st.write(f"{'✅' if c.passed else '❌'} {c.name}\n{c.description}")
                    if c.details:
                        st.caption(c.details)
            
            st.download_button("📥 Download Report (JSON)", json.dumps(r.to_dict(), indent=2), "report.json")
            
            # RDF Registry Visualization Tab
            st.markdown("---")
            st.markdown("### 📋 RDF Registry Visualization")
            
            # Build RDF representation
            builder = RDFRegistryBuilder()
            rdf_data = builder.build_rdf(st.session_state.wall_evidence, st.session_state.record_evidence)
            
            # Display RDF Summary
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total Triples", rdf_data["total"])
            with col2:
                st.metric("🔗 Nodes", len(rdf_data["nodes"]))
            with col3:
                external_links = RDFVisualizationHelper.get_external_links(rdf_data)
                st.metric("🌐 Registry Links", len(external_links))
            
            # Display Triples Table
            st.markdown("#### RDF Triples")
            triple_display = []
            for pred, subj, obj in rdf_data.get("triples", []):
                triple_display.append({
                    "Predicate": pred,
                    "Subject": RDFVisualizationHelper.abbreviate(subj),
                    "Object": obj[:50] + "..." if len(obj) > 50 else obj
                })
            st.dataframe(triple_display, use_container_width=True)
            
            # External Registry Links
            if external_links:
                st.markdown("#### 🔗 External Registry Links")
                for link in external_links:
                    st.info(f"**{link['type']}**: {link.get('link', 'N/A')}")
            
            # RDF/Turtle Export
            st.markdown("#### 📤 Export Formats")
            turtle_export = f"""
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix hft: <https://example.org/hft-acoustic/> .

# IFC Wall
<{rdf_data['wall_uri']}> a hft:mapping/vocab/IfcWall ;
    hft:mapping/vocab/name "{st.session_state.wall_evidence.get('name', '')}" ;
    hft:mapping/vocab/construction_family "{st.session_state.wall_evidence.get('construction_family', '')}" .

# Acoustic Record
<{rdf_data['record_uri']}> a hft:mapping/vocab/AcousticRecord ;
    hft:mapping/vocab/identifier "{st.session_state.record_evidence.get('identifier', '')}" ;
    hft:mapping/vocab/construction_family "{st.session_state.record_evidence.get('construction_family', '')}" .
"""
            st.download_button("📥 Export as Turtle (.ttl)", turtle_export, "registry.ttl", "text/plain")
            
            # JSON-LD Export
            jsonld_export = json.dumps({
                "@context": {
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "hft": "https://example.org/hft-acoustic/",
                    "mapping": {"@id": "hft:mapping/vocab/"}
                },
                "@graph": [
                    {
                        "@id": rdf_data['wall_uri'],
                        "@type": "mapping:IfcWall",
                        "mapping:name": st.session_state.wall_evidence.get('name', ''),
                        "mapping:construction_family": st.session_state.wall_evidence.get('construction_family', '')
                    },
                    {
                        "@id": rdf_data['record_uri'],
                        "@type": "mapping:AcousticRecord",
                        "mapping:identifier": st.session_state.record_evidence.get('identifier', ''),
                        "mapping:construction_family": st.session_state.record_evidence.get('construction_family', '')
                    }
                ]
            }, indent=2)
            st.download_button("📥 Export as JSON-LD", jsonld_export, "registry.jsonld", "application/ld+json")

    else:
        st.info("⚠️ Enter wall & record data in Manual Entry tab first")

