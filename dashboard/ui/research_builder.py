from __future__ import annotations

import hashlib
import json
from pathlib import Path

import streamlit as st

from dashboard.backend.fair_bridge import add_package
from dashboard.ui.fair_dashboard import hero
from dashboard.ui.platform_app import _measurement_preview, inspect_ifc_bytes
from fair_platform.export import export_research_object
from fair_platform.metadata_profile import PROFILE_LABEL, PROFILE_VERSION
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.research_object import (
    EvidenceItem,
    EvidenceStatus,
    GeometryMeasurementRelationship,
    LifecycleStewardshipState,
    MeasurementOrigin,
    RelationshipType,
    relationship_strength_statement,
    relationship_type_allowed_for_origin,
)
from fair_platform.stewardship import FairStewardshipService


ACOUSTIC_PROFILE_OPTIONS = {
    "Airborne sound insulation / sound reduction": "AIRBORNE_SOUND_INSULATION_RW",
    "Impact sound insulation": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Sound absorption / impedance": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Room acoustics / impulse response": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Frequency response / spectrum": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Vibration / structural dynamics": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Modal analysis / mode shapes": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Sound field / pressure map": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Catalog / reference acoustic record": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Simulation / prediction result dataset": "GENERIC_ACOUSTIC_MEASUREMENT",
    "Other acoustic dataset": "GENERIC_ACOUSTIC_MEASUREMENT",
}

EVIDENCE_TYPES = [
    "exact specimen identifier",
    "measurement-report component identifier",
    "IFC GlobalId correspondence",
    "assembly identifier",
    "component-type correspondence",
    "material-layer correspondence",
    "total-thickness correspondence",
    "dimension correspondence",
    "manufacturer/product correspondence",
    "project/location correspondence",
    "related document",
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


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _relationship_options(origin: str) -> list[str]:
    values = [item.value for item in RelationshipType]
    if origin in {MeasurementOrigin.SIMULATION_RESULT.value, MeasurementOrigin.PREDICTED_VALUE.value}:
        return [
            RelationshipType.PREDICTED_FOR.value,
            RelationshipType.CHARACTERIZES.value,
            RelationshipType.REFERENCES.value,
            RelationshipType.UNKNOWN.value,
        ]
    if origin in {
        MeasurementOrigin.CATALOG_RECORD.value,
        MeasurementOrigin.REFERENCE_VALUE.value,
        MeasurementOrigin.MANUFACTURER_VALUE.value,
    }:
        return [
            RelationshipType.CHARACTERIZES.value,
            RelationshipType.APPLICABLE_TO_EQUIVALENT_ASSEMBLY.value,
            RelationshipType.REFERENCES.value,
            RelationshipType.UNKNOWN.value,
        ]
    return values


def _readiness(checks: dict[str, tuple[bool, str]]) -> None:
    passed = sum(1 for ok, _ in checks.values() if ok)
    st.markdown("### Pre-build validation preview")
    a, b = st.columns([1, 3])
    a.metric("Core workflow checks", f"{passed}/{len(checks)}")
    b.progress(passed / len(checks) if checks else 0.0)
    st.dataframe(
        [
            {"Check": label, "Status": "READY" if ok else "MISSING/REVIEW", "Why it matters": note}
            for label, (ok, note) in checks.items()
        ],
        use_container_width=True,
        hide_index=True,
    )


def _evidence_editor(ifc_file, measurement_file) -> list[EvidenceItem]:
    st.caption(
        "Evidence explains why the selected acoustic dataset applies to the selected IFC component. "
        "No numerical confidence score is calculated."
    )
    items: list[EvidenceItem] = []
    for index in range(1, 5):
        with st.expander(f"Evidence item {index}", expanded=index == 1):
            c1, c2, c3 = st.columns(3)
            evidence_type = c1.selectbox("Evidence type", ["Not supplied"] + EVIDENCE_TYPES, key=f"evidence_type_{index}")
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
                "Reliability category",
                ["Not specified", "direct source evidence", "documented secondary evidence", "manual expert judgement", "algorithmic candidate only", "unknown"],
                key=f"evidence_reliability_{index}",
            )
            created_by = st.text_input("Evidence recorded by", key=f"evidence_creator_{index}")
            reviewed_by = st.text_input("Evidence reviewed by", key=f"evidence_reviewer_{index}")
            notes = st.text_area("Evidence notes", height=70, key=f"evidence_notes_{index}")
            if evidence_type != "Not supplied":
                source_asset = None
                if source_choice == "IFC source" and ifc_file:
                    source_asset = ifc_file.name
                elif source_choice == "Primary acoustic source" and measurement_file:
                    source_asset = measurement_file.name
                elif source_choice == "External report/reference":
                    source_asset = source_location or None
                items.append(
                    EvidenceItem(
                        evidence_type=evidence_type,
                        comparison_result=EvidenceStatus(comparison),
                        observed_value=observed or None,
                        expected_value=expected or None,
                        source_asset=source_asset,
                        source_location=source_location or None,
                        created_by=created_by or None,
                        reviewed_by=reviewed_by or None,
                        reliability=None if reliability == "Not specified" else reliability,
                        notes=notes or None,
                    )
                )
    return items


def render_research_builder() -> None:
    hero(
        "Build Component Package",
        "Create a metadata-centered acoustic component research object from an IFC component and an acoustic dataset or external record, then validate, assess, lifecycle-check, export, and register it in the prototype library.",
        f"Workspace 02 · {PROFILE_LABEL} v{PROFILE_VERSION}",
    )
    st.info(
        "The workflow preserves source files and records missing metadata as missing. It does not invent creators, institutions, licences, methods, instruments, standards, PIDs, uncertainty, provenance, bSDD/IDS references, or relationship evidence."
    )

    # ------------------------------------------------------------------ Step 1
    st.markdown("## Step 1 · Add IFC source")
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
            selected_index = st.selectbox("Select IFC component", range(len(components)), format_func=lambda i: labels[i], key="ro_component")
            selected_component = components[selected_index]
            st.success(f"Resolved actual IFC component by GlobalId: {selected_component.get('global_id')}")
        elif ifc_file:
            st.error("No supported IFC component was resolved. A real GlobalId must be selected before package creation.")
    with right:
        if selected_component:
            st.json({
                "source": "AUTO_EXTRACTED_FROM_IFC",
                "IFC schema": selected_component.get("ifc_schema"),
                "GlobalId": selected_component.get("global_id"),
                "entity type": selected_component.get("ifc_class"),
                "name": selected_component.get("name"),
                "type assignment": selected_component.get("type_assignment"),
                "materials": selected_component.get("material_evidence"),
                "layers": selected_component.get("material_layers"),
                "thickness_m": selected_component.get("total_thickness_m"),
                "spatial context": selected_component.get("spatial_context"),
                "source SHA-256": selected_component.get("source_sha256") or (_sha256(ifc_file.getvalue()) if ifc_file else None),
            })
        else:
            st.caption("IFC-derived component metadata will appear here after parsing.")

    # ------------------------------------------------------------------ Step 2
    st.markdown("## Step 2 · Add acoustic dataset")
    mode = st.radio("Dataset source", ["Upload local acoustic file", "External metadata-only reference"], horizontal=True)
    d1, d2 = st.columns(2)
    with d1:
        measurement_file = None
        if mode == "Upload local acoustic file":
            measurement_file = st.file_uploader(
                "Upload primary acoustic data",
                type=["xml", "csv", "json", "txt", "dat", "h5", "hdf5", "vtk", "vtu", "xdmf", "ttl", "rdf", "msh", "med", "res", "out", "log"],
                key="ro_measurement",
            )
            _measurement_preview(measurement_file)
        measurement_filename = measurement_file.name if measurement_file else st.text_input("External/original filename", placeholder="acoustic-record.xml")
        measurement_identifier = st.text_input("Dataset identifier", placeholder="M01, LAB-001, source record ID...")
        measurement_version = st.text_input("Dataset/source version")
        dataset_uri = st.text_input("External dataset URI / landing URI", placeholder="Optional for packaged data; required for metadata-only reference")
        dataset_creation_date = st.text_input("Dataset creation date", placeholder="Optional source value")
        dataset_modification_date = st.text_input("Dataset modification date", placeholder="Optional source value")
    with d2:
        measurement_label = st.selectbox("Acoustic record type", list(ACOUSTIC_PROFILE_OPTIONS))
        stewardship_profile = ACOUSTIC_PROFILE_OPTIONS[measurement_label]
        origin = st.selectbox(
            "Dataset-origin classification",
            [item.value for item in MeasurementOrigin],
            index=[item.value for item in MeasurementOrigin].index(MeasurementOrigin.UNKNOWN_ORIGIN.value),
            help="Classify source evidence explicitly; file structure alone does not establish measurement origin.",
        )
        measured_quantity = st.text_input("Measured / reported quantity")
        unit = st.text_input("Units")
        frequency_range = st.text_input("Frequency range / resolution", placeholder="When applicable")
        data_structure = st.text_input("Data schema / structure", placeholder="VaBDat XML, CSV table, HDF5 schema...")
        related_report = st.text_input("Source report / related document")
        source_record_identifier = st.text_input("Source record identifier")

    related_acoustic_files = st.file_uploader(
        "Additional related acoustic files (optional)",
        accept_multiple_files=True,
        key="ro_related_acoustic_assets",
        help="These are preserved as related acoustic assets. No scientific dataset identifiers are fabricated for them.",
    )

    # ------------------------------------------------------------------ Step 3
    st.markdown("## Step 3 · Create component-dataset connection")
    relationship_options = _relationship_options(origin)
    r1, r2, r3 = st.columns(3)
    with r1:
        relationship_type_value = st.selectbox("Relationship type", relationship_options, index=len(relationship_options) - 1)
        relationship_scope = st.text_input("Relationship scope", value="component")
        relationship_version = st.text_input("Relationship version", value="1.0.0")
        approval_status = st.selectbox("Approval status", ["Not specified", "DRAFT", "REVIEWED", "APPROVED", "REJECTED"])
    with r2:
        rationale = st.text_area(
            "Relationship rationale",
            placeholder="Explain why this dataset describes, characterizes, predicts, references, or is applicable to this IFC component.",
            height=120,
        )
        matching_attributes = st.text_input("Matching attributes", placeholder="Comma-separated: specimen ID, layers, total thickness, product ID...")
        excluded_attributes = st.text_input("Excluded / not-comparable attributes", placeholder="Comma-separated")
    with r3:
        relationship_created_by = st.text_input("Relationship created by")
        last_reviewed_by = st.text_input("Relationship reviewer")
        last_reviewed_at = st.text_input("Review date/time")
        approved_by = st.text_input("Approved by")
        confidence_basis = st.text_input("Qualitative confidence basis", placeholder="No numerical confidence score")

    allowed, relation_note = relationship_type_allowed_for_origin(origin, relationship_type_value)
    if allowed:
        st.caption(relation_note)
    else:
        st.error(relation_note)
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
            approval_status=None if approval_status == "Not specified" else approval_status,
            last_reviewed_by=last_reviewed_by or None,
            last_reviewed_at=last_reviewed_at or None,
            relationship_version=relationship_version,
            source_component_version=str(selected_component.get("model_version") or Path(ifc_file.name).stem if ifc_file else "") or None,
            source_measurement_version=measurement_version or None,
            source_ifc_checksum=(selected_component.get("source_sha256") or (_sha256(ifc_file.getvalue()) if ifc_file else None)),
            source_dataset_checksum=_sha256(measurement_file.getvalue()) if measurement_file else None,
            status=LifecycleStewardshipState.UNASSESSED,
        )
        st.caption(relationship_strength_statement(relationship))

    # ------------------------------------------------------------------ Step 4
    st.markdown("## Step 4 · Complete FAIR-oriented acoustic metadata")
    st.caption("Fields are grouped by the executable metadata profile. Source/entry provenance is shown again in the review step.")
    m1, m2, m3 = st.columns(3)
    with m1:
        title = st.text_input("Package title")
        description = st.text_area("Package description / abstract", height=90)
        keywords = st.text_input("Keywords", placeholder="Comma-separated")
        package_version = st.text_input("Package version", value="1.0.0")
        package_identifier = st.text_input("Repository/PID identifier", placeholder="Optional; local package ID is generated separately")
        metadata_language = st.text_input("Metadata language", placeholder="e.g. en")
    with m2:
        creator = st.text_input("Creator / responsible person")
        creator_orcid = st.text_input("Creator ORCID")
        contributors = st.text_input("Contributors", placeholder="Comma-separated")
        institution = st.text_input("Institution / laboratory")
        preferred_citation = st.text_area("Preferred citation", height=70)
        responsible_agent = st.text_input("Responsible provenance agent")
    with m3:
        license_uri = st.text_input("Licence / reuse-rights statement")
        access_rights = st.selectbox("Access rights", ["Not specified", "open", "embargoed", "restricted", "metadata-only"])
        access_url = st.text_input("Access URL")
        landing_page = st.text_input("Landing page")
        repository_identifier = st.text_input("Repository identifier / service")
        access_protocol = st.text_input("Access protocol", placeholder="HTTPS, API, request workflow...")

    st.markdown("### Measurement / generation context")
    c1, c2, c3 = st.columns(3)
    with c1:
        method = st.text_input("Measurement method")
        standard = st.text_input("Applicable standard / protocol")
        instrument = st.text_input("Instrument / acquisition system")
        instrument_manufacturer = st.text_input("Instrument manufacturer")
        instrument_model = st.text_input("Instrument model")
        instrument_configuration = st.text_area("Instrument configuration", height=65)
        calibration_reference = st.text_input("Calibration reference")
    with c2:
        operator = st.text_input("Operator")
        measurement_date = st.text_input("Measurement date")
        measurement_location = st.text_input("Measurement location")
        environmental_conditions = st.text_area("Environmental conditions", height=65)
        boundary_conditions = st.text_area("Boundary conditions", height=65)
        excitation = st.text_input("Excitation method")
        source_receiver = st.text_input("Source-receiver configuration")
    with c3:
        sampling = st.text_input("Sampling information")
        measurement_points = st.text_input("Measurement point / grid information")
        local_reference_frame = st.text_input("Coordinate / local reference frame")
        processing_software = st.text_input("Processing software / version")
        processing_steps = st.text_area("Processing steps", height=65)
        uncertainty = st.text_input("Uncertainty")
        accuracy_statement = st.text_input("Accuracy statement")

    simulation_context: dict = {}
    simulation_files = []
    if origin in {MeasurementOrigin.SIMULATION_RESULT.value, MeasurementOrigin.PREDICTED_VALUE.value}:
        st.markdown("### Simulation / prediction provenance (description only)")
        st.warning("This section documents how an imported result was produced. The application does not run acoustic simulation or calculate acoustic values.")
        s1, s2 = st.columns(2)
        with s1:
            generation_method = st.text_input("Generation / numerical method")
            simulation_software = st.text_input("Simulation / prediction software")
            simulation_version = st.text_input("Software version")
            generation_conditions = st.text_area("Model / boundary assumptions", height=75)
        with s2:
            simulation_files = st.file_uploader("Supplied simulation/prediction provenance artefacts", accept_multiple_files=True, key="ro_simulation_assets")
        simulation_context = _clean_dict({
            "numerical_method": generation_method,
            "software": simulation_software,
            "software_version": simulation_version,
            "model_assumptions": generation_conditions,
        })

    if origin == MeasurementOrigin.MANUFACTURER_VALUE.value:
        manufacturer = st.text_input("Manufacturer responsible for supplied value")
    else:
        manufacturer = ""

    st.markdown("### Provenance")
    p1, p2 = st.columns(2)
    with p1:
        original_source = st.text_input("Original source", placeholder="Source record, repository, report, or URI")
        source_record = st.text_input("Provenance source record")
        source_record_version = st.text_input("Provenance source record version")
        generating_activity = st.text_input("Generating activity", placeholder="Only describe an actual known activity")
        processing_activity = st.text_input("Processing activity")
    with p2:
        derivation_activity = st.text_input("Derivation activity")
        previous_package_version = st.text_input("Previous package version")
        previous_dataset_version = st.text_input("Previous dataset version")
        provenance_notes = st.text_area("Provenance notes", height=75)

    st.markdown("### Access, rights, quality, and reuse")
    a1, a2, a3 = st.columns(3)
    with a1:
        authentication = st.text_input("Authentication requirements")
        rights_holder = st.text_input("Rights holder")
        reuse_conditions = st.text_area("Reuse conditions", height=70)
        restrictions = st.text_area("Restrictions", height=70)
        embargo_until = st.text_input("Embargo until", placeholder="YYYY-MM-DD")
        external_uri_status = st.selectbox("External URI reachability", ["NOT_TESTED", "REACHABLE", "UNREACHABLE", "ACCESS_CONTROLLED", "UNKNOWN"], index=0)
        external_uri_checked_at = st.text_input("Access-status timestamp")
    with a2:
        intended_reuse = st.text_area("Intended use / reuse", height=70)
        limitations = st.text_area("Known limitations", height=70, help="Do not leave scientific limitations implicit; an explicit 'not documented' statement is different from an invented limitation.")
        quality_notes = st.text_area("Quality notes", height=70)
        validation_status = st.text_input("Source/domain validation status", placeholder="Only if actually supplied/reviewed")
        domain_review_status = st.selectbox("Acoustic-domain review status", ["NOT_REVIEWED", "PENDING", "REVIEWED"], index=0)
    with a3:
        supported_reuse = st.text_input("Supported reuse scenarios", placeholder="Comma-separated")
        unsupported_uses = st.text_input("Unsupported uses", placeholder="Comma-separated")
        related_publication = st.text_input("Related publication / DOI")
        related_research_report = st.text_input("Related research report")

    st.markdown("### Optional IFC semantic support")
    x1, x2 = st.columns(2)
    with x1:
        ids_reference = st.text_input("IDS specification reference")
        ids_result = st.text_input("IDS validation status")
    with x2:
        bsdd_concept_uri = st.text_input("bSDD concept URI")
        bsdd_property_uri = st.text_input("Property vocabulary URI")
        vocabulary_mapping = st.text_input("Vocabulary mapping status")
    st.caption("IDS and bSDD are optional supporting mechanisms; no live connection or fabricated concept URI is required.")

    research_files = st.file_uploader("Research / reproducibility attachments", accept_multiple_files=True, key="ro_research_assets")

    # ------------------------------------------------------------------ Step 5
    st.markdown("## Step 5 · Validate metadata inputs")
    packaged_or_external = bool(measurement_file or dataset_uri)
    checks = {
        "IFC component selected": (bool(selected_component and selected_component.get("global_id")), "Required component identity from the IFC source."),
        "Acoustic dataset available/referenced": (packaged_or_external, "A local file or explicit external URI is required."),
        "Dataset identified": (bool(measurement_identifier), "Required so relationship and reports resolve to a specific dataset."),
        "Dataset origin classified": (origin != MeasurementOrigin.UNKNOWN_ORIGIN.value, "Required to distinguish measurement, catalog/reference, manufacturer, simulation/prediction, and derived data."),
        "Relationship type compatible": (allowed and relationship_type_value != RelationshipType.UNKNOWN.value, "Relationship semantics must match the dataset origin."),
        "Relationship rationale": (bool(rationale.strip()), "Required to make the component-dataset claim reviewable."),
        "Structured relationship evidence": (bool(evidence_items), "Complete prototype relationships require explicit evidence."),
        "Package title": (bool(title.strip()), "Descriptive metadata are not fabricated from package IDs."),
        "Creator / provenance": (bool(creator and original_source and generating_activity), "Complete prototype reuse metadata require responsibility and source provenance."),
        "Licence / reuse rights": (bool(license_uri), "Required for complete prototype reuse metadata."),
        "Known limitations": (bool(limitations.strip()), "Required to bound reuse without inferring scientific validity."),
    }
    _readiness(checks)

    # ------------------------------------------------------------------ Steps 6-9 preview
    st.markdown("## Step 6 · Metadata completeness")
    st.caption("The generated package will report required, active conditional, recommended, invalid, unverified, and manual-review fields independently from FAIR.")
    st.markdown("## Step 7 · Selected FAIR-support indicators")
    st.caption("Findable, Accessible, Interoperable, and Reusable criteria run after package serializations are generated. This is not FAIR certification.")
    st.markdown("## Step 8 · Relationship lifecycle assessment")
    st.caption("The preserved lifecycle engine assesses the component-dataset connection after package creation; it does not replace metadata completeness or FAIR support.")
    st.markdown("## Step 9 · Preview research object")
    review_left, review_right = st.columns(2)
    with review_left:
        st.markdown("**Relationship claim**")
        st.json(relationship.to_dict() if relationship else {"status": "relationship unresolved"})
    with review_right:
        st.markdown("**Metadata value provenance**")
        st.json({
            "AUTO_EXTRACTED": {
                "IFC GlobalId": (selected_component or {}).get("global_id"),
                "IFC class": (selected_component or {}).get("ifc_class"),
                "IFC schema": (selected_component or {}).get("ifc_schema"),
                "materials": (selected_component or {}).get("material_evidence"),
                "IFC checksum": (selected_component or {}).get("source_sha256"),
                "dataset checksum": _sha256(measurement_file.getvalue()) if measurement_file else None,
            },
            "USER_ENTERED_OR_SOURCE_VERIFIED": {
                "dataset origin": origin,
                "title": title or None,
                "creator": creator or None,
                "licence": license_uri or None,
                "method": method or None,
                "instrument": instrument or None,
                "standard": standard or None,
                "repository/PID": package_identifier or None,
            },
            "NOT_INFERRED": [
                "scientific acoustic suitability",
                "unprovided creator/institution/method/instrument/standard/licence/uncertainty",
                "external URI reachability when status is NOT_TESTED/UNKNOWN",
            ],
        })
    st.warning(
        "Acoustic scientific suitability: NOT ASSESSED. Metadata completeness, FAIR support, and relationship lifecycle status do not establish whether the acoustic values are scientifically valid or suitable for a design decision."
    )

    # ------------------------------------------------------------------ Step 10
    st.markdown("## Step 10 · Export and catalog")
    ready_to_build = bool(ifc_file and selected_component and packaged_or_external and measurement_identifier and relationship and measurement_filename)
    if st.button("Generate, assess, catalog, and export component package", type="primary", use_container_width=True, disabled=not ready_to_build):
        geometry = selected_component or {}
        measurement_context = _clean_dict({
            "measurement_type": measurement_label,
            "origin_classification": origin,
            "measurement_version": measurement_version,
            "dataset_creation_date": dataset_creation_date,
            "dataset_modification_date": dataset_modification_date,
            "stewardship_profile": stewardship_profile,
            "measured_quantity": measured_quantity,
            "unit": unit,
            "frequency_range": frequency_range,
            "data_structure": data_structure,
            "related_report": related_report,
            "source_record_identifier": source_record_identifier,
            "measurement_method": method,
            "applicable_standard": standard,
            "instrument": instrument,
            "instrument_manufacturer": instrument_manufacturer,
            "instrument_model": instrument_model,
            "instrument_configuration": instrument_configuration,
            "calibration_reference": calibration_reference,
            "operator": operator,
            "measurement_date": measurement_date,
            "location": measurement_location,
            "environmental_conditions": environmental_conditions,
            "boundary_conditions": boundary_conditions,
            "excitation_method": excitation,
            "source_receiver_configuration": source_receiver,
            "sampling_information": sampling,
            "measurement_points": measurement_points,
            "local_reference_frame": local_reference_frame,
            "processing_software": processing_software,
            "processing_steps": processing_steps,
            "manufacturer": manufacturer,
        })
        quality_information = _clean_dict({
            "uncertainty": uncertainty,
            "accuracy_statement": accuracy_statement,
            "quality_notes": quality_notes,
            "limitations": limitations,
            "validation_status": validation_status,
            "supported_reuse_scenarios": _clean_list(supported_reuse),
            "unsupported_uses": _clean_list(unsupported_uses),
            "domain_review_status": domain_review_status,
        })
        research_context = _clean_dict({
            "intended_reuse": intended_reuse,
            "related_publication": related_publication,
            "related_report": related_research_report,
            "contributors": _clean_list(contributors),
            "preferred_citation": preferred_citation,
        })
        access_context = _clean_dict({
            "access_url": access_url,
            "landing_page": landing_page,
            "repository_identifier": repository_identifier,
            "access_protocol": access_protocol,
            "access_rights": access_rights,
            "authentication_requirements": authentication,
            "rights_holder": rights_holder,
            "reuse_conditions": reuse_conditions,
            "restrictions": restrictions,
            "embargo_until": embargo_until,
            "external_uri_status": external_uri_status,
            "external_uri_checked_at": external_uri_checked_at,
        })
        metadata = _clean_dict({
            "title": title,
            "description": description,
            "keywords": _clean_list(keywords),
            "metadata_language": metadata_language,
            "measurement_identifier": measurement_identifier,
            "creator_orcid": creator_orcid,
            "geometry_ifc_schema": geometry.get("ifc_schema"),
            "geometry_name": geometry.get("name"),
            "geometry_description": geometry.get("description"),
            "geometry_ifc_class": geometry.get("ifc_class"),
            "geometry_type_assignment": geometry.get("type_assignment"),
            "geometry_semantic_classification": geometry.get("semantic_classification"),
            "geometry_construction_family": geometry.get("construction_family"),
            "geometry_total_thickness_m": geometry.get("total_thickness_m"),
            "geometry_materials": geometry.get("material_evidence", []),
            "geometry_material_layers": geometry.get("material_layers", []),
            "geometry_spatial_context": geometry.get("spatial_context", {}),
            "model_version": geometry.get("model_version") or Path(ifc_file.name).stem,
            "source_ifc_sha256": geometry.get("source_sha256") or _sha256(ifc_file.getvalue()),
            "ids_specification_reference": ids_reference,
            "ids_validation_result": ids_result,
            "bsdd_concept_uri": bsdd_concept_uri,
            "bsdd_property_uri": bsdd_property_uri,
            "vocabulary_mapping_status": vocabulary_mapping,
        })
        provenance = _clean_dict({
            "original_source": original_source,
            "creator": creator,
            "creator_orcid": creator_orcid,
            "institution": institution,
            "responsible_agent": responsible_agent,
            "generating_activity": generating_activity,
            "source_record": source_record,
            "source_record_version": source_record_version,
            "processing_activity": processing_activity,
            "derivation_activity": derivation_activity,
            "previous_package_version": previous_package_version,
            "previous_dataset_version": previous_dataset_version,
            "notes": provenance_notes,
        })
        package = FairPackageBuilder().build(
            ifc_file.getvalue(),
            ifc_file.name,
            measurement_file.getvalue() if measurement_file else None,
            measurement_filename,
            ifc_global_id=str(geometry.get("global_id") or ""),
            creator=creator,
            version=package_version,
            identifier=package_identifier or None,
            dataset_uri=dataset_uri or None,
            license_uri=license_uri or None,
            provenance=provenance,
            measurement_context=measurement_context,
            quality_information=quality_information,
            research_context=research_context,
            simulation_context=simulation_context,
            access_context=access_context,
            relationships=[relationship.to_dict()],
            simulation_assets=_file_dict(simulation_files),
            research_assets=_file_dict(research_files),
            additional_acoustic_assets=_file_dict(related_acoustic_files),
            metadata=metadata,
            research_object_layout=True,
        )
        try:
            outcome = FairStewardshipService().assess(package)
            lifecycle_note = f"Lifecycle assessment: {outcome.status}"
        except Exception as exc:
            lifecycle_note = f"Lifecycle assessment could not complete automatically: {exc}"
        add_package(package)
        archive = export_research_object(package, strict=False)
        v = package.validation_report or {}
        st.success(
            f"Created {package.package_id} · Metadata: {package.metadata_completeness_status} · "
            f"FAIR support: {package.fair_support_status} · Lifecycle: {package.lifecycle_display_status}"
        )
        st.caption(lifecycle_note)
        outcomes = st.columns(4)
        outcomes[0].metric("Metadata completeness", package.metadata_completeness_status)
        outcomes[1].metric("FAIR support", package.fair_support_status)
        outcomes[2].metric("Relationship lifecycle", package.lifecycle_display_status)
        outcomes[3].metric("Acoustic suitability", package.scientific_suitability_status)
        if not v.get("valid", False):
            st.warning("The research object was exported with validation findings. Review the field-level and package-validation reports before reuse.")
        st.download_button(
            "Download acoustic component research-object ZIP",
            archive,
            file_name=f"{package.package_id}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        tabs = st.tabs(["Metadata completeness", "FAIR support", "Lifecycle", "Package validation", "RO-Crate JSON-LD"])
        with tabs[0]:
            st.json(package.metadata_completeness_assessment)
        with tabs[1]:
            st.json(package.fair_support_assessment)
        with tabs[2]:
            st.json({"status": package.lifecycle_display_status, "history": package.stewardship_history, "triggers": package.reassessment_triggers})
        with tabs[3]:
            st.json(v)
        with tabs[4]:
            st.json(json.loads(package.assets["ro-crate-metadata.json"]))
    elif not ready_to_build:
        st.caption("A parsed IFC component, local or externally referenced acoustic dataset, dataset identifier, source filename, and explicit relationship are required before generation.")
