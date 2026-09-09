import json
from io import BytesIO
from zipfile import ZipFile

from rdflib import Graph, Namespace, RDF

from fair_platform.export import export_fair_package
from fair_platform.metadata import metadata_turtle
from fair_platform.package_builder import FairPackageBuilder
from fair_platform.repository import PackageRepository


FAIRAC = Namespace("https://example.org/fair-acoustic/vocab/")


def _research_package():
    return FairPackageBuilder().build(
        b"ISO-10303-21;",
        "wall.ifc",
        b"frequency_hz,spl_db\n100,42\n125,44\n",
        "simulation_result.csv",
        ifc_global_id="2X_test_wall",
        creator="Acoustic Researcher",
        version="2.0.0",
        dataset_uri="https://example.org/datasets/fem-042",
        license_uri="https://creativecommons.org/licenses/by/4.0/",
        provenance={"creator": "Acoustic Researcher", "institution": "Acoustics Lab"},
        measurement_context={
            "measurement_type": "Simulation result dataset",
            "dataset_role": "simulation_output",
            "stewardship_profile": "GENERIC_ACOUSTIC_MEASUREMENT",
            "construction_family": "masonry",
            "total_thickness_m": 0.24,
        },
        quality_information={
            "uncertainty": "mesh and material sensitivity evaluated",
            "validation_metrics": "RMSE=1.8 dB",
        },
        research_context={
            "study_mode": "Hybrid validation (measurement + simulation)",
            "objective": "Validate predicted airborne sound insulation against laboratory evidence.",
            "protocol_standard": "ISO 10140 / ISO 717-1",
            "validation_method": "Measured versus simulated one-third-octave spectrum",
            "code_repository": "https://example.org/code/acoustic-model",
            "code_commit": "abc123",
        },
        simulation_context={
            "enabled": True,
            "numerical_method": "Finite Element Method (FEM)",
            "software": "ExampleSolver",
            "software_version": "1.2.3",
            "mesh_description": "quadratic tetrahedral mesh",
            "boundary_conditions": "radiation + structural supports",
            "frequency_range": "50-5000 Hz",
            "convergence_criterion": "<1% Rw change after mesh refinement",
            "computational_environment": "Linux; 16 CPU cores",
        },
        simulation_assets={
            "model.msh": b"mesh-bytes",
            "solver.yaml": b"solver: direct\nrelative_tolerance: 1e-6\n",
        },
        research_assets={
            "analysis.py": b"print('reproduce')\n",
            "README.md": b"Reproduction instructions",
        },
        metadata={
            "title": "Hybrid FEM validation package",
            "measurement_identifier": "FEM-042",
            "geometry_ifc_class": "IfcWall",
        },
    )


def test_research_package_exports_simulation_and_reproducibility_assets():
    package = _research_package()
    with ZipFile(BytesIO(export_fair_package(package))) as archive:
        names = set(archive.namelist())
        assert "simulation/model.msh" in names
        assert "simulation/solver.yaml" in names
        assert "research/analysis.py" in names
        assert "research/README.md" in names
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["schema"].endswith("/v2")
    assert manifest["simulation"]["context"]["software"] == "ExampleSolver"
    assert manifest["research"]["context"]["validation_method"].startswith("Measured versus simulated")
    assert len(manifest["simulation"]["resources"]) == 2
    assert len(manifest["research"]["resources"]) == 2
    assert manifest["checksums"]["simulation/model.msh"].startswith("sha256:")


def test_research_and_simulation_context_are_present_in_rdf():
    package = _research_package()
    graph = Graph().parse(data=metadata_turtle(package), format="turtle")
    research_nodes = list(graph.subjects(RDF.type, FAIRAC.AcousticResearchStudy))
    simulation_nodes = list(graph.subjects(RDF.type, FAIRAC.AcousticSimulationStudy))
    resource_nodes = list(graph.subjects(RDF.type, FAIRAC.ResearchResource))

    assert len(research_nodes) == 1
    assert len(simulation_nodes) == 1
    assert len(resource_nodes) == 4
    assert (simulation_nodes[0], FAIRAC.software, None) in graph
    assert (research_nodes[0], FAIRAC.validation_method, None) in graph


def test_repository_round_trip_preserves_research_context(tmp_path):
    package = _research_package()
    repository = PackageRepository(tmp_path)
    repository.save(package)
    restored = repository.load(package.package_id)

    assert restored.research_context["code_commit"] == "abc123"
    assert restored.simulation_context["numerical_method"] == "Finite Element Method (FEM)"
    assert restored.assets["simulation/model.msh"] == b"mesh-bytes"
