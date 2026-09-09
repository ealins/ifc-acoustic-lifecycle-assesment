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
        metadata_completeness: str | None = None,
        dataset_origin: str | None = None,
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
                str(package.provenance),
                str(package.relationships),
                str(package.acoustic_datasets),
            ]).lower()
            if needle and needle not in haystack:
                continue
            if fair_status and fair_status != "ALL" and package.fair_status.value != fair_status:
                continue
            if fair_support_status and fair_support_status != "ALL" and package.fair_support_status != fair_support_status:
                continue
            if metadata_completeness and metadata_completeness != "ALL" and package.metadata_completeness_status != metadata_completeness:
                continue
            if lifecycle_status and lifecycle_status != "ALL" and package.lifecycle_display_status != lifecycle_status and package.lifecycle_status != lifecycle_status:
                continue
            current_type = str(package.measurement_context.get("measurement_type", ""))
            if measurement_type and measurement_type != "ALL" and current_type != measurement_type:
                continue
            current_origin = str(package.measurement_context.get("origin_classification") or (package.metadata.get("measurement_inspection") or {}).get("origin_classification") or "")
            if dataset_origin and dataset_origin != "ALL" and current_origin != dataset_origin:
                continue
            current_ifc_type = str(package.metadata.get("geometry_ifc_class", ""))
            if ifc_type and ifc_type != "ALL" and current_ifc_type != ifc_type:
                continue
            relationship_types = {str(item.get("relationship_type")) for item in package.relationships}
            if relationship_type and relationship_type != "ALL" and relationship_type not in relationship_types:
                continue
            results.append(package)
        return results

    def entry(self, package: FairAcousticPackage) -> dict[str, str | None]:
        """Return the metadata-centered library card fields used by UI/tests."""
        relationship = package.relationships[0] if package.relationships else {}
        return {
            "package_title": package.title,
            "package_identifier": package.identifier or package.package_id,
            "ifc_global_id": package.ifc_global_id,
            "ifc_component_type": package.metadata.get("geometry_ifc_class"),
            "acoustic_dataset_identifier": package.metadata.get("measurement_identifier"),
            "dataset_origin": package.measurement_context.get("origin_classification") or (package.metadata.get("measurement_inspection") or {}).get("origin_classification"),
            "record_type": package.measurement_context.get("measurement_type"),
            "metadata_completeness": package.metadata_completeness_status,
            "fair_support": package.fair_support_status,
            "relationship_status": package.lifecycle_display_status,
            "relationship_type": relationship.get("relationship_type"),
            "package_version": package.version,
            "last_review_date": relationship.get("last_reviewed_at"),
        }

    def sparql(self, query: str) -> list[dict[str, str | None]]:
        rows = []
        for row in self.graph.query(query):
            rows.append({str(name): (str(value) if value is not None else None) for name, value in row.asdict().items()})
        return rows


PackageCatalog = MetadataCatalog
