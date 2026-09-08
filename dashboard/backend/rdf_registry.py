"""Metadata Catalog compatibility layer.

The FAIR platform uses fair_platform.catalog.MetadataCatalog for package-level RDF/SPARQL.
This module keeps the former RDFRegistryBuilder import working for older dashboard code.
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List

from fair_platform.metadata import build_metadata_graph
from fair_platform.models import FairAcousticPackage


class RDFNamespace(Enum):
    RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    RDFS = "http://www.w3.org/2000/01/rdf-schema#"
    OWL = "http://www.w3.org/2002/07/owl#"
    SKOS = "http://www.w3.org/2004/02/skos/core#"
    BSDD = "https://identifier.buildingsmart.org/uri/"
    HFT = "https://example.org/hft-acoustic/"


class MetadataCatalogBuilder:
    """Build package RDF while retaining the previous wall/record graph adapter."""

    def build_package_graph(self, package: FairAcousticPackage):
        return build_metadata_graph(package)

    def build_rdf(self, wall_data: Dict, record_data: Dict) -> Dict:
        triples = []
        wall_uri = f"{RDFNamespace.HFT.value}ifc/element/{wall_data.get('global_id', 'unknown')}"
        record_uri = record_data.get("uri", "https://example.org/record/unknown")
        record_id = record_data.get("identifier", "unknown")
        assertion_uri = f"{RDFNamespace.HFT.value}mapping/{wall_data.get('global_id')}-{record_id}"
        triples.extend([
            ("rdf:type", wall_uri, "IfcWall"),
            ("name", wall_uri, wall_data.get("name", "")),
            ("construction_family", wall_uri, wall_data.get("construction_family", "")),
            ("rdf:type", record_uri, "MeasurementDataset"),
            ("identifier", record_uri, record_id),
            ("rdf:type", assertion_uri, "MappingAssertion"),
            ("maps_ifc", assertion_uri, wall_uri),
            ("references_measurement", assertion_uri, record_uri),
        ])
        for material in wall_data.get("material_evidence", []):
            triples.append(("has_material", wall_uri, material))
        if "bsdd" in record_id.lower() or "vabdat" in record_id.lower():
            triples.append(("owl:sameAs", record_uri, f"{RDFNamespace.BSDD.value}bSDD_{record_id}"))
        return {
            "triples": triples,
            "total": len(triples),
            "nodes": [wall_uri, record_uri, assertion_uri],
            "record_uri": record_uri,
            "wall_uri": wall_uri,
        }


RDFRegistryBuilder = MetadataCatalogBuilder


class RDFVisualizationHelper:
    @staticmethod
    def abbreviate(uri: str) -> str:
        return uri if len(uri) <= 70 else uri[:67] + "..."

    @staticmethod
    def get_external_links(rdf_data: Dict) -> List[Dict]:
        return [
            {"type": "External Registry", "link": obj}
            for pred, _, obj in rdf_data.get("triples", [])
            if "sameAs" in pred
        ]
