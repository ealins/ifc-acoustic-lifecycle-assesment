# FAIR Acoustic Component Platform

> A FAIR-oriented research data management framework and acoustic component library integrating IFC geometry, measurement datasets, semantic metadata and lifecycle stewardship.

## Research thesis

**A FAIR-oriented research data management framework and acoustic component library integrating IFC geometry, measurement datasets and metadata.**

This repository is an architectural pivot of the original **IFC Acoustic Lifecycle Assessment** research prototype. The lifecycle work has not been removed or replaced. Its existing association, provenance, versioning, MappingSeries, MappingAssertion, semantic validity and change-detection mechanisms now operate as a **FAIR Stewardship Engine** inside a broader research-data-management platform.

The key change is therefore conceptual and architectural:

```text
OLD
IFC Element
    ↓
External Record
    ↓
Association
    ↓
Lifecycle Assessment

NEW
IFC Geometry + Measurement Dataset + Metadata
                    ↓
            FairAcousticPackage
                    ↓
             FAIR Assessment
                    +
          Lifecycle Stewardship
```

## Three managed information objects

### 1. Geometry — IFC

The geometry resource remains an IFC file. The platform extracts and records component-level evidence including:

- IFC `GlobalId`
- IFC entity class
- component name
- material layers and material names
- layer-derived or property-derived thickness
- semantic/predefined classification
- spatial containment context
- model version / source filename
- source SHA-256 evidence

The source IFC is not overwritten.

### 2. Measurements — external research datasets

Measurement datasets remain independent from IFC. Supported package inputs currently include XML, CSV, JSON, text/data files, HDF5 and VTK-style files. The research model is intentionally broader than one acoustic metric and can represent:

- VaBDat-style XML records
- frequency spectra
- airborne sound-insulation results
- vibration datasets
- mode shapes
- experimental measurements
- derived acoustic metrics

The builder records measurement type, method, instrument, assembly/specimen, construction family, thickness, report reference and—when applicable—`Rw`, `C` and `Ctr` values.

### 3. Metadata — RDF / Linked Data

Metadata describes and connects the research objects. It includes:

- package and measurement identifiers
- provenance
- creator / authorship
- institution
- measurement method
- instrument
- version
- uncertainty
- quality / calibration information
- license / rights
- descriptive title, description and keywords
- FAIR assessment evidence
- lifecycle stewardship identity
- checksums

Metadata is generated as RDF/Turtle using RDFLib and a FAIR Acoustic vocabulary alongside DCAT, Dublin Core Terms and PROV concepts.

## Central entity: `FairAcousticPackage`

`fair_platform.models.FairAcousticPackage` is the aggregate research-data object.

It contains references to geometry, measurement and metadata resources while also carrying the two independent assessment states:

```python
FairAcousticPackage(
    package_id=...,
    geometry_reference="geometry.ifc",
    measurement_reference="measurement.xml",
    metadata_reference="metadata.ttl",
    provenance=...,
    version=...,
    identifier=...,
    fair_status=...,
    lifecycle_status=...,
    findable=...,
    accessible=...,
    interoperable=...,
    reusable=...,
)
```

The package does **not** replace `MappingSeries` or `MappingAssertion`.

- `FairAcousticPackage` = packaged research-data object.
- `MappingSeries` = stable stewardship relationship between IFC and a measurement identity.
- `MappingAssertion` = immutable lifecycle assessment revision.

## Portable package structure

The export service produces a real ZIP archive:

```text
<FAP-ID>.zip
├── geometry.ifc
├── measurement.<source-extension>
├── metadata.ttl
└── manifest.json
```

The source measurement extension is retained. A VaBDat XML input therefore becomes `measurement.xml`, while a vibration CSV becomes `measurement.csv`.

`manifest.json` records:

- package identifier and version
- creator and license
- geometry and measurement resource metadata
- original source filenames
- media types
- IFC GlobalId
- dataset URI
- FAIR status and criterion-level assessment
- lifecycle stewardship status
- MappingSeries and latest MappingAssertion references
- SHA-256 checksums
- resource sizes

## FAIR assessment engine

The FAIR assessment is deliberately explainable. Each criterion records:

- pass/fail
- evidence used for the decision
- remediation guidance

### Findable

Checks:

- persistent identifier exists and has an HTTP(S), URN or DOI-like form
- searchable descriptive metadata exists
- IFC GlobalId exists

### Accessible

Checks:

- dataset URI / landing-page identifier exists
- measurement bytes are included in the package
- metadata resource is included

The prototype checks declared accessibility evidence; it does not claim that an external HTTP endpoint is continuously reachable unless a separate network-resolution service is added.

### Interoperable

Checks:

- IFC geometry resource is linked to a GlobalId
- RDF metadata parses successfully
- standard/documented representations are used

### Reusable

Checks:

- provenance exists
- version exists
- quality / uncertainty information exists
- reuse license exists
- measurement type and method provide measurement context

### FAIR states

The platform supports the requested states:

```text
FAIR_READY
PARTIALLY_FAIR
NOT_FINDABLE
NOT_ACCESSIBLE
NOT_INTEROPERABLE
NOT_REUSABLE
```

Every F/A/I/R dimension remains separately visible. `PARTIALLY_FAIR` is used when some criteria fail but no dimension is completely absent. A `NOT_*` state can represent a dimension with no satisfied evidence, while the full assessment still records all other deficiencies.

## Dual assessment model

FAIR readiness and lifecycle validity are intentionally independent.

Examples:

```text
FAIR Status:      FAIR_READY
Lifecycle Status: STALE
```

```text
FAIR Status:      PARTIALLY_FAIR
Lifecycle Status: ACCEPTABLE
```

A reusable, well-described package can become semantically stale when its geometry or measurement evidence changes. Conversely, a currently valid IFC-to-measurement relationship may still be poorly FAIR because it lacks a reuse license or quality metadata.

## Lifecycle Stewardship — preserved existing engine

The original lifecycle implementation remains the authoritative stewardship logic.

Core lifecycle implementation files are retained rather than rewritten by the FAIR pivot:

- `engine.py`
- `models.py`
- `association_lifecycle.py`
- `lifecycle_engine/assessment.py`
- `lifecycle_engine/change_detector.py`
- `lifecycle_engine/evaluation_runner.py`
- `lifecycle_engine/ifc_extractor.py`
- `lifecycle_engine/models.py`

For `Rw`-oriented airborne-sound-insulation packages, `fair_platform.stewardship.FairStewardshipService` calls the existing advanced `engine.evaluate_lifecycle()` pipeline. This preserves the existing:

- native-link checks
- MappingSeries validation
- IFC/RDF data checks
- IDS-style readiness
- bSDD-style alignment
- semantic status decision
- retargeting detection
- change events
- immutable revisions
- PROV-style RDF history

For other acoustic measurement types such as vibration or mode-shape datasets, the package uses the existing generic three-tier lifecycle validator rather than forcing an `Rw`-specific record schema.

Existing lifecycle states remain visible:

```text
ACCEPTABLE
STALE                 # user-facing alias of existing SEMANTICALLY_STALE
BROKEN
INVALID
AMBIGUOUS
MULTIPLE_CANDIDATES
UNMATCHED
```

The internal `SEMANTICALLY_STALE` value is preserved for compatibility with the existing engine; the FAIR UI presents it as `STALE`.

## Metadata Catalog

The former record-centric "RDF Registry" role becomes a package-centric **Metadata Catalog**.

`fair_platform.catalog.MetadataCatalog` builds one RDF graph from the package metadata and supports:

- library search
- FAIR-state filtering
- lifecycle-state filtering
- measurement-type filtering
- direct SPARQL queries

The Streamlit Component Library includes a SPARQL workbench. Example queries are in:

- `queries.sparql`
- `metadata/fair_queries.sparql`

## RDF metadata profile

The package metadata uses:

- RDF
- RDFLib
- DCAT
- Dublin Core Terms
- PROV
- the project FAIR Acoustic vocabulary
- the preserved MappingSeries / MappingAssertion vocabulary

Ontology/profile resources:

```text
metadata/fair_acoustic.ttl
metadata/fair_shapes.ttl
metadata/fair_queries.sparql
```

The SHACL file defines structural expectations for FAIR packages, IFC geometry nodes and measurement dataset nodes. It is supplied as an explicit validation profile and can be executed by a SHACL processor such as pySHACL when required.

## Streamlit application

The root application is now the canonical FAIR platform:

```bash
streamlit run app.py
```

The `dashboard/app.py` entrypoint remains as a compatibility path and launches the same platform shell.

### Workspace 1 — FAIR Package Builder

- upload IFC
- automatically inspect `IfcWall` components
- select a component by GlobalId
- inspect IFC class, materials, thickness and spatial context
- upload measurement data
- preview XML / JSON / CSV content structure
- enter measurement context
- enter descriptive metadata
- enter provenance, quality and license information
- generate a FAIR package
- immediately export ZIP + manifest

### Workspace 2 — FAIR Assessment

Displays:

```text
Findable       readiness + criteria
Accessible     readiness + criteria
Interoperable  readiness + criteria
Reusable       readiness + criteria
```

It also provides:

- overall FAIR status
- composite readiness score
- criterion evidence table
- remediation queue
- resource manifest
- re-assessment / metadata regeneration
- package export

### Workspace 3 — Lifecycle Stewardship

Displays:

- geometry evidence
- measurement evidence
- FAIR status
- lifecycle status
- stewardship profile
- MappingSeries URI
- latest MappingAssertion URI
- immutable revision history
- latest discrepancies / validation checks
- PROV/RDF stewardship history

### Workspace 4 — Component Library

Provides:

- persistent package listing
- search
- FAIR filter
- lifecycle filter
- measurement-type filter
- RDF triple count
- package inspection
- metadata Turtle inspection
- ZIP export
- local deletion
- SPARQL workbench

## Persistence

Generated packages are persisted by `fair_platform.repository.PackageRepository` under:

```text
packages/<package-id>/
├── geometry.ifc
├── measurement.<ext>
├── metadata.ttl
├── manifest.json
└── package.json
```

`packages/` is runtime data and is ignored by Git.

Set a different package store with:

```bash
FAIR_PACKAGE_STORE=/path/to/store streamlit run app.py
```

This filesystem repository is intentionally an adapter. It can later be replaced by object storage, an institutional repository, a triple store or a PID-backed research-data repository without changing the `FairAcousticPackage` domain model.

## Repository architecture

```text
.
├── app.py                              # canonical FAIR Streamlit entrypoint
├── engine.py                           # preserved advanced lifecycle engine
├── models.py                           # preserved MappingSeries/Assertion models
├── association_lifecycle.py            # preserved lifecycle/RDF logic
├── queries.sparql                      # lifecycle + FAIR SPARQL examples
│
├── fair_platform/
│   ├── __init__.py
│   ├── models.py                       # FairAcousticPackage + FAIR result model
│   ├── assessment.py                   # F/A/I/R evaluation
│   ├── package_builder.py              # package construction
│   ├── manifest.py                     # manifest model
│   ├── metadata.py                     # RDF/DCAT/PROV generation
│   ├── export.py                       # finalization, hashes, ZIP export
│   ├── repository.py                   # persistent local package store
│   ├── catalog.py                      # RDF metadata catalog + SPARQL
│   └── stewardship.py                  # adapter to preserved lifecycle engines
│
├── dashboard/
│   ├── app.py                          # compatibility entrypoint
│   ├── backend/
│   │   ├── ifc_parser.py               # richer FAIR geometry extraction
│   │   ├── validators.py               # preserved generic lifecycle wrapper
│   │   ├── lifecycle_bridge.py         # preserved lifecycle bridge
│   │   ├── rdf_registry.py             # compatibility layer
│   │   └── fair_bridge.py              # Streamlit ↔ persistent repository bridge
│   └── ui/
│       ├── fair_dashboard.py           # visual system / FAIR cards
│       └── platform_app.py             # four FAIR workspaces
│
├── lifecycle_engine/                   # preserved lifecycle package
├── metadata/
│   ├── fair_acoustic.ttl
│   ├── fair_shapes.ttl
│   └── fair_queries.sparql
├── tests/
└── packages/                           # runtime, ignored
```

## Run

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Alternative compatibility entrypoint:

```bash
streamlit run dashboard/app.py
```

## Tests

```bash
python -m pytest -q tests
```

Tests cover FAIR assessment, canonical ZIP resources, manifest checksums, repository round trips and core package services. GitHub Actions also compiles the application modules and runs the test suite.

## Research scope and limitations

This is a research prototype, not a laboratory measurement system, acoustic simulation package, institutional repository or production PID service.

The platform currently demonstrates the architectural integration of:

```text
IFC geometry
+
measurement datasets
+
semantic metadata
+
FAIR assessment
+
lifecycle stewardship
+
component-library discovery
```

External URI reachability is represented through declared access metadata and the existing lifecycle technical-resolution mechanisms where applicable. Production deployment should add repository authentication, robust HTTP resolution policies, real PID minting, access-control metadata, institutional storage, automated SHACL execution and controlled vocabulary services.

## Migration / implementation specification

The detailed preservation map, exact file changes and logical commit plan are documented in:

`docs/FAIR_PIVOT_ARCHITECTURE.md`
