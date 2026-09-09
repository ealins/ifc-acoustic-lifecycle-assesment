# FAIR-Oriented Acoustic Component Metadata Prototype

> **A prototype FAIR-oriented metadata profile, research-object package, and workflow for reusable acoustic component datasets linked to IFC representations.**

## Research focus

The repository supports the thesis direction:

**“A FAIR-oriented metadata profile and package workflow for reusable acoustic component datasets linked to IFC representations.”**

Primary research question:

> What metadata are needed so that an acoustic measurement or acoustic component dataset linked to an IFC component can be understood, assessed, discovered, and reused?

The primary contribution is metadata-centered. Existing lifecycle assessment remains a supporting relationship-stewardship mechanism.

## Contribution hierarchy

```text
PRIMARY ARTIFACT
Acoustic Component Research Object / Package
        │
        ├── defined by
        │   ├── FAIR-oriented Acoustic Metadata Profile
        │   └── Acoustic Component Package Model
        │
        ├── operationalized through
        │   ├── Package Creation Workflow
        │   └── Prototype Component Library
        │
        ├── semantically connected through
        │   ├── Component-Dataset Relationship Model
        │   └── Structured Relationship Evidence
        │
        ├── maintained through
        │   └── Relationship Lifecycle Stewardship
        │
        └── evaluated through
            ├── Metadata Completeness
            ├── Selected FAIR-Support Indicators
            ├── Package Integrity
            └── Controlled Lifecycle Scenarios
```

## What the prototype does

- loads an IFC source and resolves a real component/GlobalId with IfcOpenShell;
- preserves the source IFC rather than duplicating complete geometry in metadata;
- loads or references acoustic data and explicitly classifies dataset origin;
- captures a formal executable acoustic metadata profile with conditional requirements;
- creates a typed, evidenced component-dataset relationship;
- records provenance, access, rights, quality, limitations and version context when supplied;
- evaluates metadata completeness separately from FAIR support;
- evaluates selected Findable, Accessible, Interoperable and Reusable indicators without claiming FAIR certification;
- preserves the existing lifecycle engine for relationship stewardship and reassessment triggers;
- exports RO-Crate-style JSON-LD, domain RDF/Turtle, manifest/index, assessment reports and checksums;
- catalogs packages in a searchable local prototype component library.

## What it does not claim

The repository does not claim to provide:

- a universal acoustic metadata standard;
- formal FAIR certification or universal FAIR compliance;
- repository certification or guaranteed long-term accessibility;
- DOI/Handle/ARK minting;
- a certified preservation repository;
- automatic scientific validation of acoustic values;
- an acoustic simulation engine;
- an IDS or bSDD replacement.

**Visible scope statement:**

> This prototype evaluates metadata coverage, package structure, FAIR support, and component-dataset relationship status. It does not establish the scientific validity or acoustic suitability of the measurement values.

## Information responsibilities

### IFC

IFC is authoritative for component identity, geometry, placement, spatial relationships and available material/type information. Metadata records the selected GlobalId, IFC class/schema, source checksum/version and selected summaries without translating the complete model to RDF.

### Acoustic dataset

The scientific/catalog/reference values remain in their source dataset. Supported origin classification includes:

- `RAW_MEASUREMENT`
- `PROCESSED_MEASUREMENT`
- `DERIVED_RESULT`
- `SIMULATION_RESULT`
- `MANUFACTURER_VALUE`
- `REFERENCE_VALUE`
- `CATALOG_RECORD`
- `PREDICTED_VALUE`
- `UNKNOWN_ORIGIN`

The application does not infer raw measurement provenance from XML structure alone.

### FAIR-oriented metadata

The executable profile covers package identity, IFC context, dataset identity, measurement/generation context, provenance, access/rights, quality/reuse and relationship metadata.

### Component-dataset relationship

`GeometryMeasurementRelationship` is explicit, typed, versioned, evidenced and reviewable. `MEASURED_ON` is restricted to measurement-origin data; catalog/reference/manufacturer/simulation records use weaker or different relationship semantics where appropriate.

## Metadata profile

Authoritative executable profile:

`fair_platform/metadata_profile.py`

Each exported package contains the generated snapshot:

`profiles/acoustic-metadata-profile.json`

Requirement levels:

- `PROTOTYPE_REQUIRED`
- `CONDITIONALLY_REQUIRED`
- `RECOMMENDED`
- `OPTIONAL`
- `NOT_CURRENTLY_SUPPORTED`

The **Metadata Profile** workspace renders the same registry used by the completeness evaluator and package export.

## Independent outcomes

The application deliberately reports separate outcomes:

```text
Metadata completeness:        COMPLETE_FOR_PROTOTYPE / ...
FAIR support:                 READY_FOR_PROTOTYPE_REUSE / ...
Relationship lifecycle:       ACCEPTABLE / STALE / BROKEN / ...
Acoustic scientific suitability: NOT_ASSESSED
```

No combined FAIR/acoustic-quality score is produced.

## Metadata completeness

Field states:

`PRESENT`, `MISSING`, `INVALID`, `NOT_APPLICABLE`, `NOT_VERIFIED`, `MANUAL_REVIEW`

Overall labels:

- `COMPLETE_FOR_PROTOTYPE`
- `PARTIALLY_COMPLETE`
- `INSUFFICIENT_FOR_INTERPRETATION`
- `INSUFFICIENT_FOR_REUSE`
- `VALIDATION_INCOMPLETE`

Recommended-field coverage is reported separately and does not by itself prevent `COMPLETE_FOR_PROTOTYPE`.

## FAIR-support assessment

Criterion statuses:

`PASS`, `PARTIAL`, `FAIL`, `NOT_APPLICABLE`, `NOT_VERIFIED`, `MANUAL_REVIEW`

Checks include identifiers/discovery, packaged/external access evidence, machine-readable formats and qualified relationships, provenance/method/instrument/version/licence/limitations/reuse context. URI syntax is distinct from verified reachability.

## Relationship lifecycle stewardship

Preserved lifecycle states include:

- `ACCEPTABLE`
- `SEMANTICALLY_STALE` (displayed as `STALE` where appropriate)
- `BROKEN`
- `AMBIGUOUS`
- `MULTIPLE_CANDIDATES`
- `UNMATCHED`
- `INVALID`
- `MANUAL_REVIEW`

Reassessment triggers cover IFC/content/version/semantic changes, acoustic dataset checksum/version/URI/availability changes, provenance/licence/access changes, relationship target/type/evidence changes, competing candidates and profile-version changes. Editorial changes are distinguished from semantic changes.

## Package structure

Preferred export:

```text
acoustic-component-package/
├── ro-crate-metadata.json
├── metadata.ttl
├── manifest.json
├── profiles/acoustic-metadata-profile.json
├── geometry/source-model.ifc
├── measurements/acoustic-record.*
├── evidence/relationship-evidence.json
├── reports/metadata-completeness-assessment.json
├── reports/fair-support-assessment.json
├── reports/relationship-lifecycle-assessment.json
├── reports/package-validation.json
├── checksums/sha256sums.txt
└── README.txt
```

Serialization responsibilities:

1. in-memory domain model — authoritative application state;
2. `ro-crate-metadata.json` — principal portable research-object representation;
3. `metadata.ttl` — domain RDF/provenance/relationship/assessment graph;
4. `manifest.json` — derived compatibility/index representation;
5. profile JSON — generated snapshot of the executable metadata profile.

For external resources whose bytes were not retrieved, the package stores URI/access metadata but does not fabricate byte size or checksum.

## Streamlit workflow

Canonical navigation:

1. Overview
2. Build Component Package
3. Metadata Profile
4. Component Library
5. Metadata Completeness
6. FAIR-Support Assessment
7. Relationship Lifecycle Assessment
8. RDF / JSON-LD Explorer
9. Documentation

The builder follows: IFC → acoustic dataset → relationship/evidence → metadata → validation → completeness → FAIR support → lifecycle → preview → export/catalog.

## Prototype component library

The local catalog supports search/filtering by title/text, GlobalId, IFC component type, acoustic record type, dataset origin, metadata completeness, FAIR-support status, relationship/lifecycle status and relationship type. Entries expose provenance, evidence, RDF/JSON-LD and downloadable packages.

It is a prototype library, not a certified repository or DOI service.

## IDS and bSDD

IDS and bSDD are optional supporting mechanisms. IDS can validate IFC-side information requirements; bSDD can provide shared concepts/property semantics where real references are supplied. The metadata profile remains usable without live external connectivity.

## Run locally

From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If port 8501 is occupied:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

Canonical entrypoint: `app.py`.

## Tests

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

CI additionally performs compile/import checks, a research-object/metadata-profile export smoke test and a headless Streamlit health check.

Controlled regression cases cover complete metadata, missing licence, missing direct-measurement method, catalog-record relationship restrictions, IFC semantic change, unavailable external dataset, multiple candidates and invalid relationship state while checking assessment independence.

## Documentation

- `docs/research_positioning.md`
- `docs/acoustic_metadata_profile.md`
- `docs/acoustic_component_package.md`
- `docs/component_dataset_relationship.md`
- `docs/metadata_completeness_assessment.md`
- `docs/fair_support_assessment.md`
- `docs/relationship_lifecycle_assessment.md`
- `docs/package_specification.md`
- `docs/ids_bsdd_positioning.md`
- `docs/evaluation_methodology.md`
- `docs/acoustic_metadata_expert_review_form.md`
- `docs/migration_matrix.md`

## Research contribution statement

> The thesis develops and evaluates a FAIR-oriented acoustic component metadata profile and package model. The profile specifies the identification, component-context, measurement-context, provenance, access, rights, quality, version, and relationship metadata required for the selected IFC/VaBDat use case. The implementation operationalizes the profile as an acoustic component package builder and prototype library, while FAIR-support and relationship lifecycle assessments provide independent evaluation mechanisms.
