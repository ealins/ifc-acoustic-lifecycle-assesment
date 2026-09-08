# FAIR Acoustic Component Platform

> A FAIR-oriented research data management framework and acoustic component library integrating IFC geometry, measurement datasets, RDF metadata and lifecycle stewardship.

## Research thesis

**A FAIR-oriented research data management framework and acoustic component library integrating IFC geometry, measurement datasets and metadata.**

The repository is an architectural pivot of the existing IFC Acoustic Lifecycle Assessment prototype. The lifecycle implementation is preserved and repositioned as a **FAIR Stewardship Engine** rather than removed.

## Three information objects

The platform manages:

1. **Geometry** — IFC GlobalId, geometry-related evidence, materials, dimensions, semantic classification and spatial context.
2. **Measurements** — VaBDat-style XML, spectra, vibration data, mode shapes, insulation metrics and other experimental datasets.
3. **Metadata** — provenance, authorship, method, institution, instrument, version, uncertainty, quality, license, FAIR information and persistent identifiers.

These objects are aggregated into a `FairAcousticPackage`.

```text
IFC Geometry + Measurement Dataset + Metadata
                       ↓
              FairAcousticPackage
                       ↓
           FAIR Assessment
                 +
        Lifecycle Stewardship
```

## FAIR package structure

A portable package contains:

```text
package.zip
├── geometry.ifc
├── measurement.<source-extension>
├── metadata.ttl
└── manifest.json
```

The manifest includes package identity, resource references, FAIR state, lifecycle state and SHA-256 checksums.

## FAIR assessment

The platform evaluates four dimensions with criterion-level evidence:

- **Findable** — persistent identifier, searchable metadata, IFC GlobalId.
- **Accessible** — dataset URI, measurement availability, metadata accessibility.
- **Interoperable** — IFC linkage, RDF linkage, standard representations.
- **Reusable** — provenance, version, quality information, reuse license and measurement context.

States include:

`FAIR_READY`, `PARTIALLY_FAIR`, `NOT_FINDABLE`, `NOT_ACCESSIBLE`, `NOT_INTEROPERABLE`, `NOT_REUSABLE`.

The individual F/A/I/R results are always retained so a package can expose multiple deficiencies rather than hiding them behind one score.

## Lifecycle stewardship

Existing lifecycle functionality remains part of the architecture. The current validation and revision mechanisms become the stewardship layer that verifies whether package relationships remain technically resolvable, semantically defensible and version-aware.

Existing lifecycle states remain valid, including:

`ACCEPTABLE`, `STALE` / `SEMANTICALLY_STALE`, `BROKEN`, `INVALID`, `AMBIGUOUS`, `MULTIPLE_CANDIDATES`, `UNMATCHED`.

FAIR state and lifecycle state are independent. For example, a package may be `FAIR_READY` but `SEMANTICALLY_STALE`, or `PARTIALLY_FAIR` while the current association is `ACCEPTABLE`.

## Streamlit workspaces

The revised UI is organized around four research workflows:

1. **FAIR Package Builder** — upload IFC and measurements, inspect IFC evidence, create metadata and generate a package.
2. **FAIR Assessment** — inspect Findable, Accessible, Interoperable and Reusable checks on a dedicated dashboard.
3. **Lifecycle Stewardship** — reuse the existing three-tier validation engine for association monitoring and semantic validity.
4. **Component Library** — search packages, inspect metadata and export portable ZIP packages.

## Architecture

New FAIR functionality lives in `fair_platform/` and wraps the existing code rather than replacing it.

```text
fair_platform/
├── models.py
├── assessment.py
├── package_builder.py
├── manifest.py
├── metadata.py
├── catalog.py
└── export.py

lifecycle_engine/              # preserved lifecycle implementation
dashboard/backend/             # adapters and existing validation services
dashboard/pages/               # FAIR workspaces
metadata/fair_acoustic.ttl     # FAIR acoustic vocabulary
```

The existing `MappingSeries`, `MappingAssertion`, RDFLib/SPARQL, IFC/IfcOpenShell, provenance, versioning and semantic association logic remain available as stewardship mechanisms.

## Run the FAIR UI

```bash
python -m pip install -r dashboard/requirements.txt
streamlit run dashboard/app.py
```

The original root-level lifecycle prototype remains in the repository for reproducibility and comparison.

## Research design principle

The source IFC and source measurement datasets are not overwritten. FAIR packaging and lifecycle assessment create a governed metadata/stewardship layer around them. This keeps source evidence independently inspectable while allowing derived package status, provenance, version history and association decisions to evolve.

## Current implementation status

The FAIR layer currently provides:

- `FairAcousticPackage` aggregate model
- explainable F/A/I/R evaluation
- RDF/Turtle metadata generation
- package manifest generation
- SHA-256 package checksums
- ZIP export
- IFC inspection in the package builder
- lifecycle-engine reuse through the Stewardship workspace
- in-session searchable component library

Persistent catalog storage and repository-grade persistent identifiers are intentionally left as extension points rather than simulated as production infrastructure.
