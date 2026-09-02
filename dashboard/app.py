"""
Streamlit Dashboard Home Page - IFC-VaBDat Bi-directional Lifecycle

Main landing page for the dashboard with:
- Project overview
- Quick start guide
- Links to main sections
- Status dashboard
"""

import streamlit as st

st.set_page_config(
    page_title="IFC-VaBDat Dashboard",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🏗️ IFC-VaBDat Bi-directional Lifecycle Dashboard")

st.markdown(
    """
    Validate IFC wall element mappings to external bSDD (buildingSMART Data Dictionary) 
    acoustic records using a comprehensive 3-tier validation framework.
    """
)

# Overview section
st.markdown("## 📋 Project Overview")

col1, col2, col3 = st.columns(3)

with col1:
    st.info(
        """
        **IFC Integration**
        
        Parse and extract wall evidence from Industry Foundation Classes (IFC) models
        including geometry, materials, and construction family information.
        """
    )

with col2:
    st.info(
        """
        **bSDD Mapping**
        
        Link IFC elements to buildingSMART Data Dictionary records for acoustic
        properties, enabling semantic interoperability.
        """
    )

with col3:
    st.info(
        """
        **Lifecycle Tracking**
        
        Maintain complete audit trail of mapping assertions with versioning,
        status tracking, and review workflows.
        """
    )

# Features section
st.markdown("## ✨ Key Features")

features = [
    ("**Tier 1: Link Validation**", "Verify basic entity identifiers and URI validity"),
    ("**Tier 2: Mapping Validation**", "Check semantic alignment between IFC and bSDD"),
    ("**Tier 3: Lifecycle Validation**", "Assess versioning, consistency, and review requirements"),
    ("**Standards Panel**", "IDS compliance checks, bSDD alignment, inline constraints"),
    ("**JSON Export**", "Download validation results for integration into other systems"),
    ("**Multi-file Support**", "Upload IFC and TTL files or enter data manually"),
]

for title, description in features:
    st.markdown(f"- {title}: {description}")

# Validation tiers explanation
st.markdown("## 🔍 Validation Tiers Explained")

tier_tabs = st.tabs(["Tier 1: Link", "Tier 2: Mapping", "Tier 3: Lifecycle"])

with tier_tabs[0]:
    st.markdown(
        """
        ### Link Validation (5 checks)
        
        Ensures basic structural integrity:
        - Wall Global ID Present
        - Wall Name Present
        - Record URI Valid
        - Record Identifier Present
        - Record Version Present
        """
    )

with tier_tabs[1]:
    st.markdown(
        """
        ### Mapping Validation (4 checks)
        
        Verifies semantic alignment:
        - Construction Family Match
        - Material Evidence Present
        - Record Available
        - Assembly Information
        """
    )

with tier_tabs[2]:
    st.markdown(
        """
        ### Lifecycle Validation (3 checks)
        
        Assesses versioning and consistency:
        - Model Version Present
        - Record Version Traceable
        - Semantic Assessment
        """
    )

st.divider()

st.markdown(
    """
    **Status**: Dashboard implementation in progress  
    **Created**: September 1, 2026  
    **Validation Engine**: association_lifecycle.py
    """
)


# Quick start guide
st.markdown("## 🚀 Quick Start")

st.markdown(
    """
    1. **Go to Upload & Validate page** (left sidebar)
    2. **Enter evidence data** in the "Manual Entry" tab or upload IFC/TTL files
    3. **Click "Run Validation"** to execute the 3-tier validation
    4. **Review results** with detailed check results and export JSON for records
    """
)
