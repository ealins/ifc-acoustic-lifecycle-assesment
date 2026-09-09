# FAIR Acoustic Component Platform — Implementation Evidence

This file exists to make the architectural pivot auditable from the repository itself. It distinguishes **implemented/executable capability**, **where it is visible in the Streamlit UI**, and **prototype boundaries**.

## Capability map

| # | Requested capability | Executable implementation | UI evidence |
|---|---|---|---|
| 1 | FAIR domain layer | `fair_platform/models.py` | Overview, FAIR Assessment, Platform Evidence |
| 2 | FAIR assessment engine | `fair_platform/assessment.py` | FAIR Assessment → criterion evidence and remediation queue |
| 3 | Real package management | `fair_platform/repository.py`, `export.py`, `manifest.py` | Builder, FAIR Assessment, Library, Platform Evidence |
| 4 | Metadata Catalog | `fair_platform/catalog.py`, `metadata.py`, `shacl.py` | Component Library → SPARQL; Platform Evidence → SHACL/catalog export |
| 5 | Lifecycle Stewardship | `fair_platform/stewardship.py` wrapping `engine.py` and the generic validator | Lifecycle Stewardship → MappingSeries, MappingAssertion revisions, decision details, PROV |
| 6 | IFC Geometry evidence | `dashboard/backend/ifc_parser.py` | Builder → Geometry evidence; Stewardship → IFC evidence |
| 7 | Measurement datasets | `fair_platform/measurement.py` | Platform Evidence → measurement structural inspection |
| 8 | Canonical UI | `dashboard/ui/enhanced_app.py`, `platform_app.py` | Sidebar: Overview / Builder / FAIR / Stewardship / Library / Platform Evidence |
| 9 | Research documentation | `README.md`, `docs/FAIR_PIVOT_ARCHITECTURE.md`, this file | Platform Evidence → architecture/boundaries |
| 10 | Lifecycle preservation | existing `engine.py`, `association_lifecycle.py`, `lifecycle_engine/*` remain the stewardship core | Lifecycle Stewardship shows which engine profile is used |
| 11 | Tests / CI | `tests/*`, `.github/workflows/test.yml` | Platform Evidence describes verification scope; GitHub Actions shows the run |

## What changed after implementation review

The first FAIR pivot contained several capabilities that were present in code but not sufficiently observable. This revision closes that gap:

- **SHACL is now executed**, not merely stored as a shapes file. `fair_platform/shacl.py` runs `pyshacl` against the generated RDF graph. The compact validation report is retained in package metadata and `manifest.json` and shown in the UI.
- **Measurement files are now inspected structurally**, not merely uploaded. XML, CSV, JSON, HDF5, VTK and text/data files produce a serializable inspection record with format structure, detected signal names and warnings. The original measurement bytes are still preserved unchanged.
- **Platform Evidence** is a dedicated UI workspace that exposes all requested capabilities, live package resource/checksum evidence, FAIR criteria, measurement inspection, SHACL results, lifecycle revision history and export artifacts.
- **Metadata Catalog export** is visible as Turtle, in addition to direct SPARQL execution.

## Package evidence

A generated package persists as:

```text
packages/<package-id>/
├── geometry.ifc
├── measurement.<source-extension>
├── metadata.ttl
├── manifest.json
└── package.json
```

The portable ZIP contains the requested research package resources:

```text
geometry.ifc
measurement.<source-extension>
metadata.ttl
manifest.json
```

`package.json` is a local repository sidecar used to reload the Python domain object; it is not required in the portable ZIP.

## Explicit prototype boundaries

The following are **not** claimed as production infrastructure:

1. `PackageRepository` is local filesystem persistence, not a multi-user database, repository server or institutional archival service.
2. Automatically minted `https://example.org/...` package identifiers are prototype identifiers. A real DOI/Handle/ARK must be supplied or minted by an external PID service.
3. HDF5/VTK inspection exposes file structure and signal-name hints. It does not assert domain-complete interpretation of every laboratory-specific schema.
4. FAIR Accessibility checks evaluate declared dataset access metadata and included package assets. Continuous remote HTTP reachability is not currently monitored.
5. The component extractor remains focused on the IFC wall/component evidence used by the existing acoustic lifecycle research path; this is not a universal BIM geometry engine.

These boundaries are now shown in the **Platform Evidence** workspace so the application does not imply capabilities beyond the implemented prototype.
