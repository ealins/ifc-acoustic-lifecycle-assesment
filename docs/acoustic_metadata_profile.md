# Prototype FAIR-Oriented Acoustic Component Metadata Profile

## Purpose and scope

This document describes the thesis-specific metadata profile used by the prototype for acoustic component datasets linked to IFC representations. The profile asks:

> What metadata are needed so that an acoustic dataset linked to an IFC component can be found, understood, assessed, and reused?

The profile is scoped to IFC-based building components, selected acoustic component records, VaBDat-style XML where applicable, and the prototype evaluation cases. It is **not** a universal acoustic metadata standard and does not establish acoustic scientific validity.

The executable authority is `fair_platform/metadata_profile.py`. Every exported package also contains `profiles/acoustic-metadata-profile.json`, generated from that Python registry. The Streamlit **Metadata Profile** workspace renders the same field registry. This synchronization rule avoids maintaining competing hand-written schemas.

## Requirement levels

- `PROTOTYPE_REQUIRED` — needed for the prototype record to meet its declared use-case requirements.
- `CONDITIONALLY_REQUIRED` — required only when a declared dataset origin, access condition, or record type activates the condition.
- `RECOMMENDED` — improves discovery, interpretation, traceability, or reuse but does not by itself block `COMPLETE_FOR_PROTOTYPE`.
- `OPTIONAL` — useful supplementary metadata.
- `NOT_CURRENTLY_SUPPORTED` — recognized by the profile but not operationalized by the current prototype.

Each executable field definition records: field name, label, definition, purpose, datatype, permitted value type, cardinality, requirement level, conditional rule, source of value, acquisition method, validation rule, example, FAIR dimension, research-data-management role, relationship-assessment role, mapped vocabulary, limitation, and model path.

## 1. Package identification

The profile covers package identifier, optional repository/PID identity, title, description, version, creation/modification dates, creators, contributors, keywords, language, citation, metadata-profile version, and metadata language.

A local package ID is valid prototype identity. It must not be represented as a repository-issued DOI/Handle/ARK. Persistent-identifier quality is evaluated separately by selected FAIR-support criteria.

## 2. IFC component metadata

The IFC source remains authoritative for geometry and component representation. Metadata identify and summarize rather than reproduce full geometry.

Covered fields include IFC asset identifier, original filename, media type, IFC schema, source checksum, source version, selected GlobalId, IFC entity type, component name/description, type assignment, classification, material/layer summaries, reliably extracted dimensions, spatial/project context, and the geometry source reference.

`GlobalId`, IFC schema, source checksum, and selected component identity are important relationship baselines. A later change can trigger lifecycle reassessment.

## 3. Acoustic dataset identification

Covered fields include dataset identifier, filename/reference label, package path when embedded, external URI when externally referenced, media type, checksum and byte size when bytes are actually packaged, source version, source dates, dataset-origin classification, record type, measured/reported quantity, units, frequency context, data structure/schema, source report, and source-record identifier.

For a metadata-only external resource, local package-path, byte-size, and checksum requirements become not applicable because the prototype has not retrieved those bytes. It does not fabricate a checksum for an unseen external resource.

### Controlled dataset-origin vocabulary

- `RAW_MEASUREMENT`
- `PROCESSED_MEASUREMENT`
- `DERIVED_RESULT`
- `SIMULATION_RESULT`
- `MANUFACTURER_VALUE`
- `REFERENCE_VALUE`
- `CATALOG_RECORD`
- `PREDICTED_VALUE`
- `UNKNOWN_ORIGIN`

The origin is explicit user/source metadata. XML structure alone does not prove that a record is raw measurement data.

## 4. Measurement and generation context

Context fields cover method, applicable standard, instrument, instrument manufacturer/model/configuration, calibration reference, operator, institution/laboratory, date/location, environmental and boundary conditions, excitation, sampling, point/grid information, coordinate/reference frame, source-receiver configuration, processing software/steps, uncertainty, accuracy, quality notes, and known limitations.

Conditional rules are origin-sensitive. Examples:

- direct/processed measurements activate measurement-method and instrument requirements;
- processed/derived data activate processing/derivation context;
- simulation/prediction results activate software/generation provenance fields;
- manufacturer values activate manufacturer provenance;
- frequency-dependent records activate frequency-context requirements.

The application documents imported simulation-result provenance but does not perform acoustic simulation.

## 5. Provenance

The profile records original source, creator/responsible agent, generating activity, source record/version, processing and derivation activities, previous package/dataset versions, software where applicable, and provenance notes. PROV-O concepts are used in RDF where compatible.

Missing provenance is reported; it is not inferred from filenames or UI state.

## 6. Access and rights

The profile covers access URL, landing page, repository/service identifier, access protocol, access rights, authentication requirements, licence/reuse-rights statement, rights holder, reuse conditions, restrictions, embargo information, external-resource access status, and access-check timestamp.

URI syntax and resource reachability are distinct. Status values distinguish verified reachable, unreachable, access-controlled, not tested, and unknown conditions. A URI string alone is not proof of accessibility.

## 7. Quality and reuse

The profile records intended reuse, known limitations, source/expert validation status when genuinely supplied, supported and unsupported use scenarios, uncertainty/quality information, related reports/publications, citation information, and domain-review status.

`NOT_REVIEWED` is a valid recorded state. The prototype never fabricates an expert review and does not infer scientific acoustic suitability from metadata completeness.

## 8. Component-dataset relationship metadata

Relationship metadata include relationship ID, IFC component ID/GlobalId, acoustic dataset ID, relationship type/scope/rationale, structured evidence, creator/reviewer, review date, source IFC/dataset versions and checksums, relationship version, approval status, lifecycle status, decision history, trigger history, supersession/invalidating references, and recommended action where available.

Relationship metadata are one category within the complete acoustic metadata profile; they are not the whole thesis artifact.

## Value provenance in the UI

The builder and review pages distinguish:

- automatically extracted/calculated values;
- user-entered or source-verified values;
- missing values;
- not-applicable values;
- not-verified values;
- manual-review values.

No factual creator, institution, method, instrument, standard, licence, uncertainty, DOI, persistent identifier, provenance activity, or relationship evidence is invented.

## Machine-readable representation

The executable registry is serialized into each package as:

`profiles/acoustic-metadata-profile.json`

SHACL remains focused on RDF graph constraints and does not duplicate the complete conditional field registry. RO-Crate JSON-LD and `metadata.ttl` serialize package instances; they do not redefine the profile authority.
