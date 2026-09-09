from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from dashboard.backend.fair_bridge import add_package
from dashboard.ui.fair_dashboard import hero
from dashboard.ui.platform_app import _measurement_preview, inspect_ifc_bytes
from fair_platform.export import export_research_object
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.research_object import (
    EvidenceItem,
    EvidenceStatus,
    GeometryMeasurementRelationship,
    LifecycleStewardshipState,
    MeasurementOrigin,
    RelationshipType,
    relationship_strength_statement,
)


ACOUSTIC_PROFILE_OPTIONS = {
    "Airborne sound insulation (Rw)": "AIRBORNE_SOUND_INSULATION_RW",
    "Impact sound insulation (Ln,w)": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Sound absorption / impedance": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Room acoustics / impulse response": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Frequency response / spectrum": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Vibration / structural dynamics": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Modal analysis / mode shapes": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Sound field / pressure map": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Simulation result dataset": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Other acoustic dataset": "GENERIC_ACOUSTIC_MEASUREMENT",
}

STUDY_MODES = [
    "Experimental measurement",
    "Numerical simulation",
    "Hybrid validation (measurement + simulation)",
]

NUMERICAL_METHODS = [
    "Not specified",
    "Finite Element Method (FEM)",
    "Boundary Element Method (BEM)",
    "Finite-Difference Time-Domain (FDTD)",
    "Statistical Energy Analysis (SEA)",
    "Geometrical / ray acoustics",
    "Transfer Matrix Method (TMM)",
    "Analytical / semi-analytical",
    "Coupled structural-acoustic",
    "Other",
]

EVIDENCE_TYPES = [
    "exact physical specimen identifier",
    "test report component identifier",
    "IFC GlobalId",
    "assembly identifier",
    "material-layer match",
    "total-thickness match",
    "dimension match",
    "construction-type match",
    "manufacturer/product match",
    "project-location match",
    "laboratory specimen reference",
    "measurement-grid reference",
    "source-document reference",
    "manual expert approval",
    "algorithmic candidate match",
    "unknown evidence",
]


def _file_dict(uploaded_files) -> dict[str, bytes]:
    return {item.name: item.getvalue() for item in uploaded_files or []}


def _clean_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _clean_dict(mapping: dict) -> dict:
    return {key: value for key, value in mapping.items() if value not in (None, "", [], {}, "Not specified")}


def _readiness(checks: dict[str, tuple[bool, str]]) -> None:
    passed = sum(1 for ok, _ in checks.values() if ok)
    st.markdown("### Validation preview")
    a, b = st.columns([1, 3])
    a.metric("Prototype-required evidence", f"{passed}/{len(checks)}")
    b.progress(passed / len(checks) if checks else 0.0)
    st.dataframe(
        [
            {"Check": label, "Status": "READY" if ok else "MISSING", "Why it matters": note}
            for label, (ok, note) in checks.items()
        ],
        use_container_width=True,
        hide_index=True,
    )


def _evidence_editor(ifc_file, measurement_file) -> list[EvidenceItem]:
    st.caption(
        "Evidence explains why the selected acoustic dataset may characterize the selected IFC component. "
        "No numerical confidence score is calculated."
    )
    items: list[EvidenceItem] = []
    for index in range(1, 5):
        with st.expander(f"Evidence item {index}", expanded=index == 1):
            c1, c2, c3 = st.columns(3)
            evidence_type = c1.selectbox(
                "Evidence type",
                ["Not supplied"] + EVIDENCE_TYPES,
                key=f"evidence_type_{index}",
            )
            comparison = c2.selectbox(
                "Comparison result",
                [item.value for item in EvidenceStatus],
                index=[item.value for item in EvidenceStatus].index(EvidenceStatus.NOT_VERIFIED.value),
                key=f"evidence_status_{index}",
            )
            source_choice = c3.selectbox(
                "Evidence source",
                ["Not specified", "IFC source", "Primary acoustic source", "External report/reference", "Manual review"],
                key=f"evidence_source_{index}",
            )
            observed = st.text_input("Observed value", key=f"evidence_observed_{index}")
            expected = st.text_input("Expected / claimed value", key=f"evidence_expected_{index}")
            source_location = st.text_input(
                "Source location",
                placeholder="XML path, report page, IFC property, row/column, URL...",
                key=f"evidence_location_{index}",
            )
            reliability = st.selectbox(
                "Reliability note",
                ["Not specified", "direct source evidence", "documented secondary evidence", "manual expert judgement", "algorithmic candidate only", "unknown"],
                key=f"evidence_reliability_{index}",
            )
            notes = st.text_area("Evidence notes", height=70, key=f"evidence_notes_{index}")
            if evidence_type != "Not supplied":
                source_asset = None
                if source_choice == "IFC source" and ifc_file:
                    source_asset = ifc_file.name
                elif source_choice == "Primary acoustic source" and measurement_file:
                    source_asset = measurement_file.name
                elif source_choice not in {"Not specified", "IFC source", "Primary acoustic source"}:
                    source_asset = source_choice
                items.append(
                    EvidenceItem(
                        evidence_type=evidence_type,
                        comparison_result=EvidenceStatus(comparison),
                        observed_value=observed or None,
                        expected_value=expected or None,
                        source_asset=source_asset,
                        source_location=source_location or None,
                        reliability=None if reliability == "Not specified" else reliability,
                        notes=notes or None,
                    )
                )
    return items


def render_research_builder() -> None:
    hero(
        "Build an Acoustic Component Research Object",
        "Create a prototype FAIR-oriented research object linking one selected IFC component to an acoustic measurement, prediction, reference value, or simulation result through an explicit qualified relationship and structured evidence.",
        "Workspace 02 · Prototype Acoustic Component Research-Object Profile",
    )
    st.info(
        "The builder preserves source files and records missing metadata as missing. It does not invent creators, institutions, licences, methods, instruments, standards, PIDs, bSDD URIs, or relationship evidence."
    )

    st.markdown("## Step 1 · Load IFC")
    left, right = st.columns([1.2, 1])
    with left:
        ifc_file = st.file_uploader("Upload IFC", type=["ifc"], key="ro_ifc")
        components = inspect_ifc_bytes(ifc_file.getvalue()) if ifc_file else []
        selected_component = None
        if components:
            labels = []
            for item in components:
                thickness = item.get("total_thickness_m")
                t = f"{thickness:.3f} m" if isinstance(thickness, (int, float)) else "thickness n/a"
                labels.append(f"{item.get('name')} · {item.get('ifc_class')} · {t} · {item.get('global_id')}")
            selected_index = st.selectbox(
                "Select IFC component",
                range(len(components)),
                format_func=lambda i: labels[i],
                key="ro_component",
            )
            selected_component = components[selected_index]
            st.success(f"Resolved component by GlobalId: {selected_component.get('global_id')}")
        elif ifc_file:
            st.error("No supported IFC component was resolved. Select a valid IFC component before creating a research object.")
    with right:
        if selected_component:
            st.json(
                {
                    "IFC schema": selected_component.get("ifc_schema"),
                    "GlobalId": selected_component.get("global_id"),
                    "entity type": selected_component.get("ifc_class"),
                    "name": selected_component.get("name"),
                    "type assignment": selected_component.get("type_assignment"),
                    "materials": selected_component.get("material_evidence"),
                    "thickness_m": selected_component.get("total_thickness_m"),
                    "spatial context": selected_component.get("spatial_context"),
                    "source SHA-256": selected_component.get("source_sha256"),
                }
            )
        else:
            st.caption("Component evidence will appear here after IFC parsing.")

    st.markdown("## Step 2 · Load acoustic data")
    d1, d2 = st.columns(2)
    with d1:
        measurement_file = st.file_uploader(
            "Upload primary acoustic data",
            type=["xml", "csv", "json", "txt", "dat", "h5", "hdf5", "vtk", "vtu", "xdmf", "ttl", "rdf", "msh", "med", "res", "out", "log"],
            key="ro_measurement",
        )
        _measurement_preview(measurement_file)
        measurement_identifier = st.text_input("Measurement/dataset identifier", placeholder="LAB-001, RUN-042, report record ID...")
        measurement_version = st.text_input("Measurement/source version")
        dataset_uri = st.text_input("External dataset URI / landing page", placeholder="Optional; a URI string is not treated as proof of reachability")
    with d2:
        measurement_label = st.selectbox("Acoustic data type", list(ACOUSTIC_PROFILE_OPTIONS))
        stewardship_profile = ACOUSTIC_PROFILE_OPTIONS[measurement_label]
        origin = st.selectbox(
            "Data origin classification",
            [item.value for item in MeasurementOrigin],
            index=[item.value for item in MeasurementOrigin].index(MeasurementOrigin.UNKNOWN.value),
            help="Explicitly distinguish raw/processed measurement, derived/reference/manufacturer/predicted values, simulation results, and unknown origin.",
        )
        measured_quantity = st.text_input("Measured / represented quantity")
        unit_default = "dB" if measurement_label == "Airborne sound insulation (Rw)" else ""
        unit = st.text_input("Units", value=unit_default)
        data_structure = st.text_input("Data structure / schema", placeholder="VaBDat XML, CSV table, HDF5 schema, VTK field...")
        related_report = st.text_input("Related report / source document")

    st.markdown("## Step 3 · Create qualified geometry-measurement relationship")
    r1, r2, r3 = st.columns(3)
    with r1:
        relationship_type_value = st.selectbox(
            "Relationship type",
            [item.value for item in RelationshipType],
            index=[item.value for item in RelationshipType].index(RelationshipType.UNKNOWN.value),
        )
        relationship_scope = st.text_input("Scope", value="component")
        relationship_version = st.text_input("Relationship version", value="1.0.0")
    with r2:
        rationale = st.text_area(
            "Relationship rationale",
            placeholder="Explain why this measurement/prediction/reference is associated with this specific IFC component.",
            height=120,
        )
        matching_attributes = st.text_input("Matching attributes", placeholder="Comma-separated: material layers, total thickness, assembly ID...")
        excluded_attributes = st.text_input("Excluded / not-comparable attributes", placeholder="Comma-separated")
    with r3:
        relationship_created_by = st.text_input("Relationship created by")
        approved_by = st.text_input("Approved by")
        last_reviewed_by = st.text_input("Last reviewed by")
        confidence_basis = st.text_input("Confidence basis", placeholder="Qualitative basis only; no pseudo-score")

    evidence_items = _evidence_editor(ifc_file, measurement_file)

    relationship = None
    if selected_component and measurement_identifier:
        relationship = GeometryMeasurementRelationship(
            subject_component_id=f"ifc:{selected_component.get('global_id')}",
            subject_ifc_global_id=str(selected_component.get("global_id") or ""),
            subject_ifc_file_id=ifc_file.name if ifc_file else "",
            object_measurement_id=measurement_identifier,
            relationship_type=RelationshipType(relationship_type_value),
            scope=relationship_scope or "component",
            rationale=rationale,
            evidence=evidence_items,
            matching_attributes=_clean_list(matching_attributes),
            excluded_attributes=_clean_list(excluded_attributes),
            confidence_basis=confidence_basis or None,
            created_by=relationship_created_by or None,
            approved_by=approved_by or None,
            last_reviewed_by=last_reviewed_by or None,
            relationship_version=relationship_version,
            source_component_version=str(selected_component.get("model_version") or "") or None,
            source_measurement_version=measurement_version or None,
            status=LifecycleStewardshipState.UNASSESSED,
        )
        st.caption(relationship_strength_statement(relationship))

    st.markdown("## Step 4 · Complete metadata")
    m1, m2, m3 = st.columns(3)
    with m1:
        title = st.text_input("Package title")
        description = st.text_area("Description / abstract", height=95)
        keywords = st.text_input("Keywords", placeholder="Comma-separated")
        package_version = st.text_input("Package version", value="1.0.0")
        package_identifier = st.text_input("Repository/PID identifier", placeholder="Optional; leave blank if none has been issued")
    with m2:
        creator = st.text_input("Creator / responsible person")
        creator_orcid = st.text_input("Creator ORCID")
        contributors = st.text_input("Contributors", placeholder="Comma-separated")
        institution = st.text_input("Organization / institution")
        preferred_citation = st.text_area("Preferred citation", height=70)
    with m3:
        license_uri = st.text_input("Licence / reuse statement URI")
        access_rights = st.selectbox("Access rights", ["Not specified", "open", "embargoed", "restricted", "metadata-only"])
        authentication = st.text_input("Authentication requirements")
        embargo_until = st.text_input("Embargo until", placeholder="YYYY-MM-DD")
        external_uri_status = st.selectbox("External URI reachability", ["NOT_TESTED", "REACHABLE", "UNREACHABLE"], index=0)

    st.markdown("### Measurement context")
    c1, c2, c3 = st.columns(3)
    with c1:
        method = st.text_input("Method")
        standard = st.text_input("Applicable standard / protocol")
        instrument = st.text_input("Instrument / acquisition system")
        instrument_configuration = st.text_area("Instrument configuration", height=75)
    with c2:
        operator = st.text_input("Operator")
        measurement_date = st.text_input("Measurement date")
        environmental_conditions = st.text_area("Environmental conditions", height=75)
        boundary_conditions = st.text_area("Boundary conditions", height=75)
    with c3:
        excitation = st.text_input("Excitation method")
        sampling = st.text_input("Sampling information")
        measurement_points = st.text_input("Measurement points / grid")
        local_reference_frame = st.text_input("Coordinate / local reference frame")

    q1, q2 = st.columns(2)
    with q1:
        processing_software = st.text_input("Processing software / version")
        processing_steps = st.text_area("Processing steps", height=80)
        uncertainty = st.text_input("Uncertainty")
        quality_notes = st.text_area("Quality notes / limitations", height=80)
    with q2:
        ids_reference = st.text_input("IDS specification reference", help="Optional IFC-side information requirement reference")
        ids_result = st.text_input("IDS validation result")
        bsdd_concept_uri = st.text_input("bSDD concept URI", help="Only enter a real known URI; the application does not fabricate one")
        bsdd_property_uri = st.text_input("bSDD property URI")
        vocabulary_mapping = st.text_input("Vocabulary mapping status")

    st.markdown("### Research and acoustic simulation context")
    s1, s2, s3 = st.columns(3)
    with s1:
        study_mode = st.selectbox("Study mode", STUDY_MODES)
        objective = st.text_area("Research objective / question", height=90)
        intended_reuse = st.text_area("Intended reuse", height=75)
        related_publication = st.text_input("Related publication / DOI")
    with s2:
        numerical_method = st.selectbox("Numerical method", NUMERICAL_METHODS)
        simulation_software = st.text_input("Solver / simulation software")
        simulation_version = st.text_input("Solver version")
        mesh_description = st.text_area("Mesh / discretization", height=70)
        solver_settings = st.text_area("Solver settings / tolerances", height=70)
    with s3:
        simulation_boundary = st.text_area("Simulation boundary conditions", height=70)
        simulation_excitation = st.text_input("Simulation excitation / source")
        frequency_range = st.text_input("Frequency range / resolution")
        computational_environment = st.text_area("Computational environment", height=70)
        model_assumptions = st.text_area("Model assumptions / simplifications", height=70)

    simulation_files = st.file_uploader(
        "Simulation artefacts",
        accept_multiple_files=True,
        key="ro_simulation_assets",
    )
    research_files = st.file_uploader(
        "Research / reproducibility artefacts",
        accept_multiple_files=True,
        key="ro_research_assets",
    )

    st.markdown("## Step 5 · Validate")
    checks = {
        "IFC component selected": (bool(selected_component and selected_component.get("global_id")), "Required to resolve the subject component."),
        "Acoustic dataset loaded": (bool(measurement_file), "Required primary acoustic asset."),
        "Dataset identified": (bool(measurement_identifier), "Required so the relationship resolves to a specific dataset."),
        "Origin classified": (origin != MeasurementOrigin.UNKNOWN.value, "Required to distinguish measurement, prediction, reference, simulation, or unknown origin."),
        "Relationship typed": (relationship_type_value != RelationshipType.UNKNOWN.value, "Required so measuredOn, predictedFor, references, etc. are not treated as equivalent."),
        "Relationship rationale": (bool(rationale.strip()), "Required to justify the claim."),
        "Structured relationship evidence": (bool(evidence_items), "Required evidence is explicit rather than inferred."),
        "Package title": (bool(title.strip()), "Required descriptive metadata; no fallback title is treated as user metadata."),
        "Package provenance": (bool(creator or institution), "At least a responsible person or organization should be identified."),
    }
    _readiness(checks)

    st.markdown("## Step 6 · Review")
    review_left, review_right = st.columns(2)
    with review_left:
        st.markdown("**Relationship claim**")
        if relationship:
            st.json(relationship.to_dict())
        else:
            st.warning("Relationship cannot yet be resolved because the selected component or dataset identifier is missing.")
    with review_right:
        st.markdown("**Metadata provenance**")
        st.json(
            {
                "automatically extracted": {
                    "IFC GlobalId": (selected_component or {}).get("global_id"),
                    "IFC class": (selected_component or {}).get("ifc_class"),
                    "IFC schema": (selected_component or {}).get("ifc_schema"),
                    "materials": (selected_component or {}).get("material_evidence"),
                    "thickness_m": (selected_component or {}).get("total_thickness_m"),
                    "IFC checksum": (selected_component or {}).get("source_sha256"),
                },
                "user entered": {
                    "title": title or None,
                    "creator": creator or None,
                    "institution": institution or None,
                    "licence": license_uri or None,
                    "method": method or None,
                    "instrument": instrument or None,
                    "standard": standard or None,
                    "PID": package_identifier or None,
                },
            }
        )
    st.warning(
        "Acoustic scientific suitability: NOT ASSESSED. FAIR-support and lifecycle stewardship do not establish whether the acoustic values are scientifically valid or suitable for a design decision."
    )

    st.markdown("## Step 7 · Export")
    ready_to_build = bool(ifc_file and selected_component and measurement_file and measurement_identifier and relationship)
    if st.button("Generate Acoustic Component Research Object", type="primary", use_container_width=True, disabled=not ready_to_build):
        geometry = selected_component or {}
        measurement_context = _clean_dict({
            "measurement_type": measurement_label,
            "origin_classification": origin,
            "measurement_version": measurement_version,
            "stewardship_profile": stewardship_profile,
            "measured_quantity": measured_quantity,
            "unit": unit,
            "data_structure": data_structure,
            "related_report": related_report,
            "measurement_method": method,
            "applicable_standard": standard,
            "instrument": instrument,
            "instrument_configuration": instrument_configuration,
            "operator": operator,
            "measurement_date": measurement_date,
            "environmental_conditions": environmental_conditions,
            "boundary_conditions": boundary_conditions,
            "excitation_method": excitation,
            "sampling_information": sampling,
            "measurement_points": measurement_points,
            "local_reference_frame": local_reference_frame,
            "processing_software": processing_software,
            "processing_steps": processing_steps,
        })
        quality_information = _clean_dict({
            "uncertainty": uncertainty,
            "quality_notes": quality_notes,
        })
        research_context = _clean_dict({
            "study_mode": study_mode,
            "objective": objective,
            "intended_reuse": intended_reuse,
            "related_publication": related_publication,
            "contributors": _clean_list(contributors),
            "preferred_citation": preferred_citation,
        })
        simulation_context = _clean_dict({
            "numerical_method": numerical_method,
            "software": simulation_software,
            "software_version": simulation_version,
            "mesh_description": mesh_description,
            "solver_settings": solver_settings,
            "boundary_conditions": simulation_boundary,
            "excitation_source": simulation_excitation,
            "frequency_range": frequency_range,
            "computational_environment": computational_environment,
            "model_assumptions": model_assumptions,
        })
        access_context = _clean_dict({
            "access_rights": access_rights,
            "authentication_requirements": authentication,
            "embargo_until": embargo_until,
            "external_uri_status": external_uri_status,
        })
        metadata = _clean_dict({
            "title": title,
            "description": description,
            "keywords": _clean_list(keywords),
            "measurement_identifier": measurement_identifier,
            "creator_orcid": creator_orcid,
            "geometry_ifc_schema": geometry.get("ifc_schema"),
            "geometry_name": geometry.get("name"),
            "geometry_ifc_class": geometry.get("ifc_class"),
            "geometry_type_assignment": geometry.get("type_assignment"),
            "geometry_semantic_classification": geometry.get("semantic_classification"),
            "geometry_construction_family": geometry.get("construction_family"),
            "geometry_total_thickness_m": geometry.get("total_thickness_m"),
            "geometry_materials": geometry.get("material_evidence", []),
            "geometry_material_layers": geometry.get("material_layers", []),
            "geometry_spatial_context": geometry.get("spatial_context", {}),
            "model_version": geometry.get("model_version") or Path(ifc_file.name).stem,
            "source_ifc_sha256": geometry.get("source_sha256"),
            "ids_specification_reference": ids_reference,
            "ids_validation_result": ids_result,
            "bsdd_concept_uri": bsdd_concept_uri,
            "bsdd_property_uri": bsdd_property_uri,
            "vocabulary_mapping_status": vocabulary_mapping,
        })
        package = FairPackageBuilder().build(
            ifc_file.getvalue(),
            ifc_file.name,
            measurement_file.getvalue(),
            measurement_file.name,
            ifc_global_id=str(geometry.get("global_id") or ""),
            creator=creator,
            version=package_version,
            identifier=package_identifier or None,
            dataset_uri=dataset_uri or None,
            license_uri=license_uri or None,
            provenance=_clean_dict({
                "creator": creator,
                "creator_orcid": creator_orcid,
                "institution": institution,
                "generating_activity": "Acoustic component research-object creation",
            }),
            measurement_context=measurement_context,
            quality_information=quality_information,
            research_context=research_context,
            simulation_context=simulation_context,
            access_context=access_context,
            relationships=[relationship.to_dict()],
            simulation_assets=_file_dict(simulation_files),
            research_assets=_file_dict(research_files),
            metadata=metadata,
            research_object_layout=True,
        )
        add_package(package)
        archive = export_research_object(package, strict=False)
        v = package.validation_report or {}
        st.success(
            f"Created {package.package_id} · FAIR-support: {package.fair_support_status} · "
            f"Lifecycle: {package.lifecycle_display_status} · Acoustic suitability: {package.scientific_suitability_status}"
        )
        if not v.get("valid", False):
            st.warning("The research object was exported with validation findings. Review the package-validation report before reuse.")
        st.download_button(
            "Download research-object ZIP",
            archive,
            file_name=f"{package.package_id}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        with st.expander("Package validation report", expanded=True):
            st.json(v)
        with st.expander("RO-Crate JSON-LD", expanded=False):
            st.json(json.loads(package.assets["ro-crate-metadata.json"]))
        with st.expander("Compatibility manifest", expanded=False):
            st.json(json.loads(package.assets["manifest.json"]))
    elif not ready_to_build:
        st.caption("A parsed IFC component, primary acoustic file, dataset identifier, and explicit relationship are required before generation.")
