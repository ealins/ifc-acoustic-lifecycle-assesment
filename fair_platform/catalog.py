from __future__ import annotations

from .models import FairAcousticPackage


class PackageCatalog:
    """Small in-memory catalog facade; RDF-backed persistence can replace this adapter later."""

    @staticmethod
    def search(packages: list[FairAcousticPackage], query: str = "", fair_status: str | None = None) -> list[FairAcousticPackage]:
        query = query.strip().lower()
        results = []
        for package in packages:
            haystack = " ".join([
                package.package_id,
                package.identifier,
                package.ifc_global_id or "",
                package.creator or "",
                str(package.metadata),
                str(package.measurement_context),
            ]).lower()
            if query and query not in haystack:
                continue
            if fair_status and fair_status != "ALL" and package.fair_status.value != fair_status:
                continue
            results.append(package)
        return results
