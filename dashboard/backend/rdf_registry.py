"""RDF Registry Visualization - Semantic Graph for Records"""
from enum import Enum
from typing import List, Dict, Optional


class RDFNamespace(Enum):
    """RDF Namespaces"""
    RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    RDFS = "http://www.w3.org/2000/01/rdf-schema#"
    OWL = "http://www.w3.org/2002/07/owl#"
    SKOS = "http://www.w3.org/2004/02/skos/core#"
    BSDD = "https://identifier.buildingsmart.org/uri/"
    HFT = "https://example.org/hft-acoustic/"


class RDFRegistryBuilder:
    """Builds RDF representation for records and mappings"""
    
    def build_rdf(self, wall_data: Dict, record_data: Dict) -> Dict:
        """Build complete RDF registry"""
        triples = []
        
        # Wall node
        wall_uri = f"{RDFNamespace.HFT.value}ifc/element/{wall_data.get('global_id', 'unknown')}"
        triples.append(("rdf:type", wall_uri, "IfcWall"))
        triples.append(("name", wall_uri, wall_data.get("name", "")))
        triples.append(("construction_family", wall_uri, wall_data.get("construction_family", "")))
        triples.append(("thickness_m", wall_uri, str(wall_data.get("total_thickness_m", 0))))
        
        for mat in wall_data.get("material_evidence", []):
            triples.append(("has_material", wall_uri, mat))
        
        # Record node
        record_uri = record_data.get("uri", "https://example.org/record/unknown")
        record_id = record_data.get("identifier", "unknown")
        triples.append(("rdf:type", record_uri, "AcousticRecord"))
        triples.append(("identifier", record_uri, record_id))
        triples.append(("assembly", record_uri, record_data.get("assembly", "")))
        triples.append(("construction_family", record_uri, record_data.get("construction_family", "")))
        triples.append(("thickness_m", record_uri, str(record_data.get("total_thickness_m", 0))))
        
        # External registry link
        if "bsdd" in record_id.lower() or "vabdat" in record_id.lower():
            bsdd_uri = f"{RDFNamespace.BSDD.value}bSDD_{record_id}"
            triples.append(("owl:sameAs", record_uri, bsdd_uri))
        
        # Mapping assertion
        assertion_uri = f"{RDFNamespace.HFT.value}mapping/{wall_data.get('global_id')}-{record_id}"
        triples.append(("rdf:type", assertion_uri, "MappingAssertion"))
        triples.append(("maps_ifc", assertion_uri, wall_uri))
        triples.append(("references_record", assertion_uri, record_uri))
        
        return {
            "triples": triples,
            "total": len(triples),
            "nodes": [wall_uri, record_uri, assertion_uri],
            "record_uri": record_uri,
            "wall_uri": wall_uri,
        }


class RDFVisualizationHelper:
    """Helpers for RDF visualization in Streamlit"""
    
    @staticmethod
    def abbreviate(uri: str) -> str:
        """Shorten URI for display"""
        if len(uri) > 70:
            if "example.org" in uri:
                parts = uri.replace("https://example.org/", "").split("/")
                if len(parts) >= 2:
                    return f".../{parts[-2]}/{parts[-1]}"
            return uri[:67] + "..."
        return uri
    
    @staticmethod
    def get_external_links(rdf_data: Dict) -> List[Dict]:
        """Extract external registry links"""
        links = []
        for pred, subj, obj in rdf_data.get("triples", []):
            if "sameAs" in pred:
                links.append({"type": "[LINK] External Registry", "link": obj})
        return links
