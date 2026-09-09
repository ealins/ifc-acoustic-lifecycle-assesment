from __future__ import annotations

from rdflib import Graph

from .metadata import build_metadata_graph
from .models import FairAcousticPackage


class MetadataCatalog:
    """Prototype RDF-backed catalog for acoustic component research objects.

    This catalog does not issue DOIs, certify repository preservation, or guarantee
    long-term availability. It indexes locally persisted prototype research objects.
    """

    def __init__(self, packages: list[FairAcousticPackage] | None = None):
        self.packages = list(packages or [])

    @property
    def graph(self) -> Graph:
        graph = Graph()
        for package in self.packages:
            graph += build_metadata_graph(package)
        return graph

    def search(
        self,
        query: str = "",
        fair_status: str | None = None,
        lifecycle_status: str | None = None,
        measurement_type: str | None = None,
        *,
        fair_support_status: str | None = None,
        ifc_type: str | None = None,
        relationship_type: str | None = None,
    ) -> list[FairAcousticPackage]:
        needle = query.strip().lower()
        results: list[FairAcousticPackage] = []
        for package in self.packages:
            haystack = " ".join([
                package.package_id,
                package.identifier,
                package.ifc_global_id or "",
                package.creator or "",
                package.title,
                str(package.metadata),
                str(package.measurement_context),
                str(package.research_context),
                str(package.simulation_context),
                str(package.provenance),
                str(package.relationships),
            ]).lower()
            if needle and needle not in haystack:
                continue
            if fair_status and fair_status != "ALL" and package.fair_status.value != fair_status:
                continue
            if fair_support_status and fair_support_status != "ALL" and package.fair_support_status != fair_support_status:
                continue
            if lifecycle_status and lifecycle_status != "ALL" and package.lifecycle_display_status != lifecycle_status and package.lifecycle_status != lifecycle_status:
                continue
            current_type = str(package.measurement_context.get("measurement_type", ""))
            if measurement_type and measurement_type != "ALL" and current_type != measurement_type:
                continue
            current_ifc_type = str(package.metadata.get("geometry_ifc_class", ""))
            if ifc_type and ifc_type != "ALL" and current_ifc_type != ifc_type:
                continue
            relationship_types = {str(item.get("relationship_type")) for item in package.relationships}
            if relationship_type and relationship_type != "ALL" and relationship_type not in relationship_types:
                continue
            results.append(package)
        return results

    def sparql(self, query: str) -> list[dict[str, str | None]]:
        rows = []
        for row in self.graph.query(query):
            rows.append({str(name): (str(value) if value is not None else None) for name, value in row.asdict().items()})
        return rows


PackageCatalog = MetadataCatalog
