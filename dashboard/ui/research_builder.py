from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from dashboard.backend.fair_bridge import add_package
from dashboard.ui.fair_dashboard import hero
from dashboard.ui.platform_app import _measurement_preview, inspect_ifc_bytes
from fair_platform.export import export_fair_package
from fair_platform.package_builder import FairPackageBuilder


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


def _file_dict(uploaded_files) -> dict[str, bytes]:
    return {item.name: item.getvalue() for item in uploaded_files or []}


def _clean_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _research_readiness(checks: dict[str, bool]) -> None:
    passed = sum(checks.values())
    score = passed / len(checks) if checks else 0.0
    st.markdown("### Research-object completeness preview")
    a, b = st.columns([1, 3])
    a.metric("Evidence supplied", f"{passed}/{len(checks)}")
    b.progress(score)
    st.dataframe(
        [
            {"Evidence block": label, "Status": "READY" if ok else "MISSING / OPTIONAL"}
            for label, ok in checks.items()
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_research_builder() -> None:
    hero(
        "Build a FAIR Acoustic Research Package",
        "Create a portable research object that links IFC geometry with acoustic measurements or simulation outputs, research-method metadata, solver provenance, validation evidence, uncertainty and reproducibility artefacts. Source files remain byte-preserved inside the package.",
        "Workspace 01 · FAIR Package Builder · research + simulation profile",
    )

    st.markdown("### 1 · Research design")
    r1, r2, r3 = st.columns(3)
    with r1:
        study_mode = st.selectbox("Study mode", STUDY_MODES)
        study_title = st.text_input(
            "Research study title",
            placeholder="FEM validation of airborne sound insulation for a masonry wall",
        )
        objective = st.text_area(
            "Objective / research question",
            placeholder="Quantify the agreement between laboratory Rw measurements and numerical prediction...",
            height=100,
        )
    with r2:
        hypothesis = st.text_area(
            "Hypothesis / expected relationship",
            placeholder="The calibrated model will reproduce the measured one-third-octave response within...",
            height=100,
        )
        study_phase = st.selectbox(
            "Study phase",
            ["Exploratory", "Calibration", "Validation", "Benchmark", "Production analysis", "Replication"],
        )
        protocol = st.text_input(
            "Protocol / standard / method reference",
            placeholder="ISO 10140, ISO 717-1, ISO 354, custom FEM protocol...",
        )
    with r3:
        project = st.text_input("Project / work package")
        funding = st.text_input("Funding / grant identifier")
        related_publication = st.text_input("Related publication / DOI")
        preregistration = st.text_input("Protocol / preregistration URI")

    st.markdown("### 2 · Geometry and primary acoustic evidence")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**IFC geometry**")
        ifc_file = st.file_uploader("Upload IFC", type=["ifc"], key="research_ifc")
        walls = inspect_ifc_bytes(ifc_file.getvalue()) if ifc_file else []
        selected_wall = None
        if walls:
            labels = []
            for wall in walls:
                thickness = wall.get("total_thickness_m")
                thickness_text = f"{thickness:.3f} m" if isinstance(thickness, (int, float)) else "thickness n/a"
                labels.append(
                    f"{wall.get('name')} · {wall.get('ifc_class')} · "
                    f"{wall.get('construction_family')} · {thickness_text}"
                )
            selected_index = st.selectbox(
                "IFC component",
                range(len(walls)),
                format_func=lambda index: labels[index],
                key="research_ifc_component",
            )
            selected_wall = walls[selected_index]
            st.caption(f"GlobalId `{selected_wall.get('global_id')}`")
            with st.expander("Geometry evidence"):
                st.json(selected_wall)
        elif ifc_file:
            st.warning("No IfcWall element was extracted. The IFC can still be packaged with a manually supplied GlobalId.")
        ifc_global_id = st.text_input(
            "IFC GlobalId",
            value=(selected_wall or {}).get("global_id", ""),
            key=f"research_global_{(selected_wall or {}).get('global_id', 'manual')}",
        )

    with right:
        primary_label = "Primary simulation output" if study_mode == "Numerical simulation" else "Primary acoustic dataset"
        st.markdown(f"**{primary_label}**")
        measurement_file = st.file_uploader(
            primary_label,
            type=[
                "xml", "csv", "json", "txt", "dat", "h5", "hdf5", "vtk", "vtu", "xdmf",
                "ttl", "rdf", "msh", "med", "res", "out", "log",
            ],
            key="research_primary_dataset",
        )
        _measurement_preview(measurement_file)
        measurement_identifier = st.text_input(
            "Dataset identifier",
            placeholder="LAB-RW-2026-014 / FEM-RUN-042 / DOI dataset ID",
        )
        dataset_uri = st.text_input(
            "Dataset URI / landing page",
            placeholder="https://repository.example.org/dataset/...",
        )
        measurement_label = st.selectbox("Acoustic data type", list(ACOUSTIC_PROFILE_OPTIONS))
        stewardship_profile = ACOUSTIC_PROFILE_OPTIONS[measurement_label]
        data_role = st.selectbox(
            "Primary dataset role",
            ["measurement", "simulation_output", "calibration_reference", "validation_reference", "derived_result"],
            index=1 if study_mode == "Numerical simulation" else 0,
        )

    st.markdown("### 3 · Experimental / measurement evidence")
    if study_mode == "Numerical simulation":
        st.caption("This section is optional for a simulation-only package; use it when the model is calibrated or validated against experimental evidence.")
    e1, e2, e3 = st.columns(3)
    with e1:
        measurement_method = st.text_input("Measurement method", placeholder="ISO 10140-2, swept sine, modal hammer test...")
        instrument = st.text_input("Instrument / acquisition system", placeholder="Microphone array, analyzer, accelerometers...")
        laboratory = st.text_input("Laboratory / facility")
        specimen = st.text_input("Specimen / assembly")
    with e2:
        family = st.text_input(
            "Construction family",
            value=(selected_wall or {}).get("construction_family", ""),
        )
        base_thickness = (selected_wall or {}).get("total_thickness_m") or 0.0
        measured_thickness = st.number_input(
            "Assembly thickness (m)", min_value=0.0, value=float(base_thickness), step=0.005
        )
        environmental_conditions = st.text_area(
            "Environmental conditions",
            placeholder="Temperature, humidity, room volumes, mounting conditions...",
            height=88,
        )
    with e3:
        uncertainty = st.text_input("Measurement uncertainty", placeholder="±1.2 dB / confidence interval / sensor accuracy")
        calibration = st.text_input("Calibration / QA reference")
        sampling = st.text_input("Sampling / acquisition settings", placeholder="48 kHz, 24 bit, 10 averages...")
        report_reference = st.text_input("Report / experiment reference")

    rw_db = None
    unit = "dB"
    spectrum_c = None
    spectrum_ctr = None
    if stewardship_profile == "AIRBORNE_SOUND_INSULATION_RW":
        with st.expander("Rw-specific performance metadata", expanded=True):
            q1, q2, q3, q4 = st.columns(4)
            rw_db = q1.number_input("Rw (dB)", min_value=0.0, max_value=100.0, value=50.0, step=0.5)
            unit = q2.text_input("Unit", value="dB")
            spectrum_c = q3.number_input("C", value=0.0, step=0.5)
            spectrum_ctr = q4.number_input("Ctr", value=0.0, step=0.5)

    st.markdown("### 4 · Acoustic simulation model and solver provenance")
    simulation_enabled = study_mode in {"Numerical simulation", "Hybrid validation (measurement + simulation)"}
    if not simulation_enabled:
        st.caption("Optional for an experimental study. Fill this section if a numerical model is used for interpretation, calibration or sensitivity analysis.")
    s1, s2, s3 = st.columns(3)
    with s1:
        numerical_method = st.selectbox("Numerical method", NUMERICAL_METHODS, index=0)
        software = st.text_input("Solver / simulation software", placeholder="COMSOL, ANSYS, Abaqus, OpenFOAM, custom code...")
        software_version = st.text_input("Software version")
        solver_module = st.text_input("Physics / solver module", placeholder="Pressure acoustics, structural dynamics, vibroacoustics...")
        solver_settings = st.text_area("Solver settings", placeholder="Direct/iterative solver, tolerances, formulation...", height=95)
    with s2:
        mesh_description = st.text_area("Mesh / discretization", placeholder="Element type, order, target size, boundary layer mesh...", height=95)
        degrees_of_freedom = st.text_input("Degrees of freedom / model size")
        frequency_range = st.text_input("Frequency range / resolution", placeholder="50–5000 Hz, 1/3 octave or 5 Hz steps")
        time_step = st.text_input("Time step / simulation duration", placeholder="For transient models")
        convergence = st.text_input("Convergence criterion / mesh independence")
    with s3:
        boundary_conditions = st.text_area("Boundary conditions", placeholder="Rigid, impedance, radiation, periodic, symmetry, supports...", height=95)
        excitation = st.text_input("Excitation / source definition", placeholder="Diffuse field, point source, force, plane wave...")
        receivers = st.text_input("Receiver / evaluation locations")
        damping = st.text_input("Damping / loss factor / impedance model")
        material_model = st.text_area("Acoustic / structural material model", placeholder="Density, E, nu, damping, flow resistivity, porosity...", height=75)

    st.markdown("#### Simulation inputs, outputs and computational environment")
    si1, si2 = st.columns(2)
    with si1:
        simulation_files = st.file_uploader(
            "Simulation artefacts",
            type=[
                "json", "yaml", "yml", "txt", "csv", "xml", "ini", "toml", "msh", "med", "vtk", "vtu",
                "xdmf", "h5", "hdf5", "res", "out", "log", "mph", "inp", "dat",
            ],
            accept_multiple_files=True,
            key="research_simulation_assets",
            help="Examples: solver input deck, mesh, parameter file, output table, field result, convergence log.",
        )
        computational_environment = st.text_area(
            "Computational environment",
            placeholder="OS, CPU/GPU, RAM, container image, HPC cluster / queue...",
            height=95,
        )
    with si2:
        model_assumptions = st.text_area(
            "Model assumptions / simplifications",
            placeholder="2D approximation, linear acoustics, diffuse field assumption, homogenized material...",
            height=95,
        )
        preprocessing = st.text_area(
            "Pre-processing / parameter derivation",
            placeholder="IFC-to-mesh transformation, material mapping, filtering, interpolation...",
            height=95,
        )

    st.markdown("### 5 · Validation, uncertainty and reproducibility")
    v1, v2, v3 = st.columns(3)
    with v1:
        validation_method = st.text_input("Validation / calibration method", placeholder="Measured vs simulated spectrum, cross-validation, benchmark case...")
        validation_reference = st.text_input("Validation reference dataset / package")
        validation_metrics = st.text_input("Validation metrics", placeholder="RMSE=1.8 dB, R²=0.94, MAC=0.91...")
        sensitivity = st.text_area("Sensitivity / uncertainty analysis", placeholder="Parameter ranges, Monte Carlo, mesh sensitivity...", height=90)
    with v2:
        code_repository = st.text_input("Code repository URI")
        code_commit = st.text_input("Code commit / release / tag")
        random_seed = st.text_input("Random seed", placeholder="When stochastic methods are used")
        workflow_description = st.text_area("Reproduction workflow", placeholder="Steps required to regenerate the model and outputs...", height=90)
    with v3:
        research_files = st.file_uploader(
            "Research / reproducibility artefacts",
            type=["py", "ipynb", "r", "m", "jl", "csv", "json", "yaml", "yml", "txt", "md", "pdf", "ttl", "rdf", "sh"],
            accept_multiple_files=True,
            key="research_repro_assets",
            help="Examples: scripts, notebooks, parameter tables, protocol, report, README or supplementary metadata.",
        )
        quality_statement = st.text_area("Scientific quality statement", placeholder="Known limitations, QA checks, excluded runs, validity domain...", height=90)

    st.markdown("### 6 · Descriptive metadata, provenance and reuse")
    m1, m2, m3 = st.columns(3)
    with m1:
        title = st.text_input("Package title", value=study_title, placeholder="Acoustic research package title")
        description = st.text_area("Description / abstract", height=110)
        keywords = st.text_input("Keywords", placeholder="FEM, airborne sound insulation, validation, masonry")
        contributors = st.text_input("Contributors", placeholder="Comma-separated names")
    with m2:
        creator = st.text_input("Creator / author")
        creator_orcid = st.text_input("Creator ORCID")
        institution = st.text_input("Institution")
        version = st.text_input("Package version", value="1.0.0")
        identifier = st.text_input("Package persistent identifier", placeholder="Leave blank to mint a prototype URI")
    with m3:
        license_uri = st.text_input("Reuse license / rights URI", value="https://creativecommons.org/licenses/by/4.0/")
        access_rights = st.selectbox("Access status", ["open", "embargoed", "restricted", "metadata-only"])
        embargo_until = st.text_input("Embargo until", placeholder="YYYY-MM-DD, if applicable")
        repository_name = st.text_input("Target repository / archive")
        citation = st.text_area("Preferred citation", height=78)

    simulation_assets = _file_dict(simulation_files)
    research_assets = _file_dict(research_files)
    _research_readiness(
        {
            "IFC geometry": bool(ifc_file),
            "Primary acoustic dataset": bool(measurement_file),
            "Research objective": bool(objective),
            "Method / protocol": bool(protocol or measurement_method),
            "Creator + institution": bool(creator and institution),
            "Persistent dataset URI": bool(dataset_uri),
            "License / rights": bool(license_uri),
            "Uncertainty / QA": bool(uncertainty or quality_statement),
            "Simulation provenance": bool(software and numerical_method) if simulation_enabled else True,
            "Validation / reproducibility": bool(validation_method or workflow_description or code_repository),
        }
    )

    ready = bool(ifc_file and measurement_file)
    if st.button(
        "Generate FAIR Acoustic Research Package",
        type="primary",
        use_container_width=True,
        disabled=not ready,
    ):
        geometry = selected_wall or {}
        package = FairPackageBuilder().build(
            ifc_file.getvalue(),
            ifc_file.name,
            measurement_file.getvalue(),
            measurement_file.name,
            ifc_global_id=ifc_global_id,
            creator=creator,
            version=version,
            identifier=identifier or None,
            dataset_uri=dataset_uri,
            license_uri=license_uri,
            provenance={
                "creator": creator,
                "creator_orcid": creator_orcid,
                "institution": institution,
                "project": project,
                "funding": funding,
                "note": f"Research package created from {ifc_file.name} and {measurement_file.name}",
            },
            measurement_context={
                "measurement_type": measurement_label,
                "dataset_role": data_role,
                "stewardship_profile": stewardship_profile,
                "measurement_method": measurement_method,
                "instrument": instrument,
                "laboratory": laboratory,
                "assembly": specimen,
                "construction_family": family,
                "total_thickness_m": measured_thickness,
                "environmental_conditions": environmental_conditions,
                "sampling_settings": sampling,
                "report_reference": report_reference,
                "rw_db": rw_db,
                "unit": unit,
                "spectrum_adaptation_C": spectrum_c,
                "spectrum_adaptation_Ctr": spectrum_ctr,
            },
            quality_information={
                "uncertainty": uncertainty,
                "calibration_reference": calibration,
                "quality_statement": quality_statement,
                "validation_metrics": validation_metrics,
                "sensitivity_analysis": sensitivity,
            },
            research_context={
                "study_mode": study_mode,
                "study_title": study_title,
                "objective": objective,
                "hypothesis": hypothesis,
                "study_phase": study_phase,
                "protocol_standard": protocol,
                "project": project,
                "funding": funding,
                "related_publication": related_publication,
                "preregistration_uri": preregistration,
                "validation_method": validation_method,
                "validation_reference": validation_reference,
                "validation_metrics": validation_metrics,
                "sensitivity_analysis": sensitivity,
                "code_repository": code_repository,
                "code_commit": code_commit,
                "random_seed": random_seed,
                "workflow_description": workflow_description,
                "contributors": _clean_list(contributors),
                "access_rights": access_rights,
                "embargo_until": embargo_until,
                "repository_name": repository_name,
                "preferred_citation": citation,
            },
            simulation_context={
                "enabled": simulation_enabled or bool(software or simulation_assets),
                "numerical_method": numerical_method,
                "software": software,
                "software_version": software_version,
                "solver_module": solver_module,
                "solver_settings": solver_settings,
                "mesh_description": mesh_description,
                "degrees_of_freedom": degrees_of_freedom,
                "frequency_range": frequency_range,
                "time_step": time_step,
                "convergence_criterion": convergence,
                "boundary_conditions": boundary_conditions,
                "excitation_source": excitation,
                "receiver_configuration": receivers,
                "damping_model": damping,
                "material_model": material_model,
                "computational_environment": computational_environment,
                "model_assumptions": model_assumptions,
                "preprocessing": preprocessing,
            },
            simulation_assets=simulation_assets,
            research_assets=research_assets,
            metadata={
                "title": title or study_title or measurement_identifier or "Untitled acoustic research package",
                "description": description,
                "keywords": _clean_list(keywords),
                "measurement_identifier": measurement_identifier,
                "creator_orcid": creator_orcid,
                "geometry_name": geometry.get("name", ""),
                "geometry_ifc_class": geometry.get("ifc_class", "IfcWall"),
                "geometry_semantic_classification": geometry.get("semantic_classification", ""),
                "geometry_construction_family": geometry.get("construction_family", ""),
                "geometry_total_thickness_m": geometry.get("total_thickness_m"),
                "geometry_materials": geometry.get("material_evidence", []),
                "geometry_material_layers": geometry.get("material_layers", []),
                "geometry_spatial_context": geometry.get("spatial_context", {}),
                "model_version": geometry.get("model_version", Path(ifc_file.name).stem),
                "source_ifc_sha256": geometry.get("source_sha256", ""),
            },
        )
        add_package(package)
        st.success(
            f"Created {package.package_id} — FAIR status: {package.fair_status.value} · "
            f"{len(simulation_assets)} simulation artefact(s) · {len(research_assets)} research artefact(s)"
        )
        st.download_button(
            "Download research package.zip",
            export_fair_package(package),
            file_name=f"{package.package_id}.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )
        with st.expander("Generated research manifest", expanded=True):
            st.json(json.loads(package.assets["manifest.json"]))
        with st.expander("Simulation context"):
            st.json(package.simulation_context)
        with st.expander("Research context"):
            st.json(package.research_context)
    elif not ready:
        st.caption(
            "An IFC file and one primary acoustic dataset are required. The primary dataset may be an experimental measurement or a simulation output. Additional simulation and reproducibility artefacts are optional but improve the research object."
        )
