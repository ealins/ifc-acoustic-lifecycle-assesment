# FAIR Acoustic Platform — Architecture and Migration Record

## Decision

The repository is pivoted from an association-centric lifecycle validator to a package-centric FAIR research-data-management platform **without redesigning the lifecycle engine from scratch**.

The architectural aggregate is `FairAcousticPackage`; lifecycle association objects remain separate stewardship entities.

## Target architecture

```text
IFC Geometry            Measurement Dataset             Metadata
     │                           │                          │
     └──────────────┬────────────┴──────────────┬───────────┘
                    │                           │
                    └────── FairAcousticPackage ┘
                               │        │
                 FAIR Assessment        Lifecycle Stewardship
                    F A I R             existing lifecycle engine
                               │        │
                               └── Metadata Catalog ── RDF/SPARQL
                                              │
                                      Component Library
                                              │
                                         package.zip
```

## Preservation boundary

The FAIR migration treats the following existing files as preserved lifecycle core:

- `engine.py`
- `models.py`
- `association_lifecycle.py`
- `lifecycle_engine/__init__.py`
- `lifecycle_engine/assessment.py`
- `lifecycle_engine/change_detector.py`
- `lifecycle_engine/evaluation_runner.py`
- `lifecycle_engine/ifc_extractor.py`
- `lifecycle_engine/models.py`

The FAIR implementation is additive around these modules. This exceeds the requirement to retain at least 80% of lifecycle functionality because the core lifecycle implementation remains in place and is called through adapters.

## Concept mapping

| Old concept | New interpretation | Implementation strategy |
| --- | --- | --- |
| IFC element | IFC Geometry resource | Preserve IFC identity; enrich extraction |
| External record | Measurement Dataset | Preserve external-data ownership; broaden formats |
| Association | Package relationship / stewardship link | Keep MappingSeries semantics internally |
| RDF Registry | Metadata Catalog | Add package RDF graph and SPARQL discovery |
| Lifecycle Assessment | Lifecycle Stewardship | Preserve engine and expose as separate package state |
| MappingSeries | Stable stewardship identity | Preserve |
| MappingAssertion | Immutable stewardship revision | Preserve |
| Provenance | FAIR Reusability + lifecycle evidence | Reuse and expose in metadata |
| Version tracking | FAIR Reusability + lifecycle stewardship | Preserve |
| URI resolution | Accessibility evidence + lifecycle technical state | Reuse |
| GlobalId | Findability + IFC identity | Reuse |

## Files created

### FAIR domain/services

- `fair_platform/__init__.py`
- `fair_platform/models.py`
- `fair_platform/assessment.py`
- `fair_platform/package_builder.py`
- `fair_platform/manifest.py`
- `fair_platform/metadata.py`
- `fair_platform/export.py`
- `fair_platform/repository.py`
- `fair_platform/catalog.py`
- `fair_platform/stewardship.py`

### Metadata profile

- `metadata/fair_acoustic.ttl`
- `metadata/fair_shapes.ttl`
- `metadata/fair_queries.sparql`

### UI/platform

- `dashboard/backend/fair_bridge.py`
- `dashboard/ui/fair_dashboard.py`
- `dashboard/ui/platform_app.py`
- `.streamlit/config.toml`

### Tests/docs

- `tests/test_fair_assessment.py`
- `tests/test_fair_package_io.py`
- `tests/test_stewardship.py`
- `docs/FAIR_PIVOT_ARCHITECTURE.md`
- `.github/workflows/test.yml`

## Files modified

- `app.py` — FAIR platform becomes canonical entrypoint.
- `dashboard/app.py` — compatibility entrypoint to the same platform.
- `dashboard/backend/ifc_parser.py` — richer geometry evidence extraction.
- `dashboard/backend/rdf_registry.py` — Metadata Catalog terminology + compatibility alias.
- `dashboard/.streamlit/config.toml` — theme / custom navigation.
- `README.md` — complete thesis repositioning.
- `queries.sparql` — preserved lifecycle queries + FAIR package queries.
- `.gitignore` — ignore generated package repository.
- `dashboard/requirements.txt` — align runtime versions.

## Files deliberately not rewritten

- `engine.py`
- `models.py`
- `association_lifecycle.py`
- all `lifecycle_engine/*` core files
- historical lifecycle evaluation outputs
- previous upgrade experiment directories

These remain research evidence and regression/reference material.

## FAIR state algorithm

Each dimension is a set of explicit criterion results. A criterion contains pass/fail, evidence and remediation.

- all criteria across all dimensions pass → `FAIR_READY`
- incomplete criteria but no dimension completely absent → `PARTIALLY_FAIR`
- a dimension has zero supporting criteria → corresponding `NOT_*` primary state

All dimension scores and deficiency classes remain stored even when one primary status is shown.

## Stewardship profiles

### `AIRBORNE_SOUND_INSULATION_RW`

Calls existing `engine.evaluate_lifecycle()` and therefore preserves:

- MappingSeries validation
- native/Pset link logic
- complete acoustic record checks
- IDS readiness
- bSDD alignment
- semantic staleness
- retargeting
- immutable MappingAssertions
- change events
- PROV Turtle generation

### `GENERIC_ACOUSTIC_MEASUREMENT`

Calls the existing `dashboard.backend.validators.TieredValidator`, which wraps `association_lifecycle.semantic_assessment`. It is used for vibration, spectra, mode-shape and other packages where forcing an `Rw` record schema would be semantically incorrect.

## Persistence strategy

Phase 1 uses a filesystem adapter under `packages/`. Each package stores canonical assets plus `package.json` for application-state reconstruction.

This isolates persistence behind `PackageRepository` so a later migration can replace local storage with:

- institutional repository
- S3/object storage
- Fedora/Dataverse/Zenodo-like repository adapter
- triplestore
- PID service

without changing the FAIR domain model.

## Logical commit plan

1. `feat(fair): introduce FAIR package domain and explainable assessment`
2. `feat(package): add RDF metadata, manifest, checksums and ZIP export`
3. `feat(catalog): add persistent package repository and RDF/SPARQL catalog`
4. `feat(stewardship): bridge packages to preserved lifecycle engines`
5. `feat(ui): make FAIR platform canonical and improve IFC evidence extraction`
6. `docs(metadata): add ontology, SHACL, queries and thesis documentation`
7. `test: add package, FAIR and stewardship regression tests`

The implementation history may combine adjacent items, but the architectural boundaries remain explicit.

## Future production extensions

- real DOI/Handle/ARK minting
- authenticated remote measurement repositories
- URI reachability policies and cached access evidence
- automated pySHACL validation
- external controlled vocabularies / bSDD API integration
- triplestore persistence
- access-rights enforcement
- object-level provenance activities for package creation and export
- package version supersession graph
- richer geometry-resource support beyond walls
