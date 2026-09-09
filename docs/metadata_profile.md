# Acoustic Component Research-Object Metadata Profile

**Status:** prototype use-case profile. It is not a universal acoustic metadata standard.

Requirement levels are: **prototype required**, **conditionally required**, **recommended**, **optional**, and **not currently supported**. Values are never invented to satisfy a requirement.

## A. Package identification

| Field | Definition / type / cardinality | Source | Level | Example / validation | FAIR / stewardship mapping |
|---|---|---|---|---|---|
| `package_id` | Local application identity; string; 1 | application | prototype required | `ACP-12AB34CD56`; unique in local catalog | F: local indexing |
| `identifier` | Optional external/repository PID; URI/string; 0..1 | user/repository | recommended | distinguish DOI/HTTP/URN/prototype/local; do not fabricate | F1/F2 |
| `title` | Human-readable object title; string; 1 | user | prototype required | non-empty | F, R |
| `description` | Scope/abstract; string; 0..1 | user | recommended | non-empty if supplied | F, R |
| `version` | Research-object version; string; 1 | user/workflow | prototype required | non-empty; distinct from source versions | F, R, lifecycle |
| `created` | Creation timestamp; datetime; 1 | application | prototype required | ISO-8601 | provenance |
| `modified` | Last intentional modification; datetime; 0..1 | workflow | recommended | ISO-8601 | provenance/lifecycle |
| `creator` | Responsible creator; person/text; 0..n | user/source | recommended | no default author | R |
| `contributors` | Other contributors; list; 0..n | user/source | optional | preserve names/IDs | R |
| `publisher` | Publisher/repository if applicable; text/URI; 0..1 | user/repository | optional | not inferred | F/A/R |
| `keywords` | Discovery terms; list; 0..n | user | recommended | explicit user terms | F |
| `citation` | Preferred citation; string; 0..1 | user/repository | recommended | no fabricated DOI | R |

## B. IFC component identification

| Field | Definition / type / cardinality | Source | Level | Example / validation | FAIR / stewardship mapping |
|---|---|---|---|---|---|
| `geometry_reference` | Packaged IFC path or reference; string; 1 | builder | prototype required | safe relative path or URI | A/I |
| `source_geometry_filename` | Original filename; string; 1 for packaged source | upload | prototype required | preserved separately from archive path | R |
| `geometry_ifc_schema` | IFC schema reported by parser; string; 0..1 | IfcOpenShell | recommended | `IFC4`; not guessed | I / trigger |
| `ifc_global_id` | Selected component GlobalId; string; 1 where IFC component is selected | IfcOpenShell | prototype required | must resolve to selected component | F/I / lifecycle |
| `geometry_ifc_class` | IFC entity type; string; 1 | IfcOpenShell | prototype required | `IfcWall`; parser-derived | I / lifecycle |
| `geometry_name` | IFC Name; string; 0..1 | IFC | recommended | may legitimately be empty | F |
| `geometry_description` | IFC Description; string; 0..1 | IFC | optional | preserve if present | F/R |
| `geometry_component_type` | Assigned IFC type/object type; string; 0..1 | IFC | recommended | parser-derived | I / trigger |
| `geometry_component_type_global_id` | Type object GlobalId where present; string; 0..1 | IFC | optional | verify in source | I / trigger |
| `geometry_materials` | Material summary; list; 0..n | IFC | recommended | only values actually extracted | I / evidence |
| `geometry_material_layers` | Layer name/thickness summary; structured list; 0..n | IFC | conditionally required for layer matching | no inferred layers | I / trigger/evidence |
| `geometry_total_thickness_m` | Derived/extracted thickness; decimal metres; 0..1 | IFC | conditionally required | record only when extraction is defensible | evidence / trigger |
| `geometry_spatial_context` | Containing storey/space/building context; object; 0..1 | IFC | optional | parser-derived | F/evidence |
| `model_version` | Source IFC model version label; string; 0..1 | filename/user/repository | recommended | not the package version | R / trigger |
| `source_ifc_sha256` | Source checksum; SHA-256; 1 when packaged | builder | prototype required | recompute and compare | R / trigger |
| `ids_specification_reference` | Optional IDS specification URI/path; 0..1 | user | optional | never fabricated | IFC information requirements |
| `ids_validation_result` | Result of an actual IDS check; object/string; 0..1 | validator | optional | only if executed | IFC QA, not FAIR replacement |
| `bsdd_concept_uri` | Genuine bSDD concept URI; URI; 0..n | user/integration | optional | URI syntax + manual/external verification | I |
| `bsdd_property_uri` | Genuine bSDD property URI; URI; 0..n | user/integration | optional | do not synthesize | I |
| `vocabulary_mapping_status` | Mapping verification state; enum; 0..1 | workflow | optional | `NOT_VERIFIED`, `VERIFIED`, etc. | I |

The full IFC geometry remains authoritative in IFC. Metadata only identifies and summarizes the selected component.

## C. Acoustic dataset identification

| Field | Definition / type / cardinality | Source | Level | Example / validation | FAIR / stewardship mapping |
|---|---|---|---|---|---|
| `measurement_identifier` | Dataset/record ID; string; 1 | source/user | prototype required | distinct from package ID | F/I |
| `measurement_reference` | Packaged path; string; 1 for packaged primary data | builder | prototype required | safe path; asset must exist | A |
| `dataset_uri` | External landing/access URI; URI; 0..1 | repository/user | optional/conditional | syntax check; reachability separate | A |
| `measurement_media_type` | Media type; string; 1 | filename/inspection | prototype required | e.g. `application/xml` | I |
| `data_structure` | File/schema/structural description; object/string; 0..1 | safe inspector | recommended | parsed structure only | I |
| `origin_classification` | raw/processed/derived/reference/manufacturer/predicted/simulation/unknown; enum; 1 | user/source | prototype required | unknown remains unknown | R / relationship semantics |
| `measurement_version` | Source dataset version; string; 0..1 | source/user | recommended | independent of package version | R / trigger |
| `dataset_created` | Dataset creation date; date; 0..1 | source | optional | do not infer from upload | R |
| `dataset_modified` | Dataset modification date; date; 0..1 | source | optional | source/repository evidence | R / trigger |
| `measured_quantity` | Quantity represented; string/URI; 0..n | source/user | recommended | e.g. sound reduction index | I/R |
| `unit` / `units` | Units for numeric quantities; string/URI; 0..n | source/user | conditionally required | never infer if ambiguous | I/R |
| `frequency_range` | Frequency domain/range; structured/string; 0..1 | source/user | conditionally required | when frequency-dependent | R |
| `related_report` | Test/report reference; URI/string; 0..n | source/user | recommended | traceable reference | F/R/evidence |
| `measurement_checksum` | SHA-256 when packaged; string; 1 | builder | prototype required | recompute | R / trigger |

## D. Measurement context

| Field | Definition / type / cardinality | Source | Level | Example / validation | FAIR / stewardship mapping |
|---|---|---|---|---|---|
| `measurement_method` | Measurement/processing method; string/URI; 0..1 | source/user | conditionally required | physical measurements require context | R |
| `applicable_standard` | Applicable standard/protocol; string/URI; 0..n | source/user | recommended | record only when actually applicable | I/R |
| `instrument` | Instrument/system; string/entity; 0..n | source/user | conditionally required | physical measurement | R |
| `instrument_configuration` | Configuration/settings; object/string; 0..1 | source/user | recommended | preserve settings | R |
| `calibration_reference` | Calibration/QA reference; string/URI; 0..1 | source/user | recommended | traceable source | R |
| `operator` | Measurement operator; person/text; 0..n | source/user | optional | no default | provenance |
| `institution` | Lab/institution; organization/text; 0..1 | source/user | recommended | no default | provenance/R |
| `measurement_date` | Activity date; datetime; 0..1 | source | recommended | do not use package creation date | provenance |
| `environmental_conditions` | temperature/humidity/room conditions; object/string; 0..1 | source/user | conditionally required | use-case dependent | R |
| `boundary_conditions` | Test/model boundary conditions; object/string; 0..1 | source/user | conditionally required | required when interpretation depends on them | R |
| `excitation_method` | Source/excitation; string/object; 0..1 | source/user | conditionally required | test-specific | R |
| `sampling_information` | sample rate/averages/window/etc.; object/string; 0..1 | source/user | conditionally required | signal-data use cases | R |
| `measurement_points` | Measurement grid/points; structured/URI; 0..n | source/user | optional/conditional | preserve coordinates/reference | I/R |
| `reference_frame` | Coordinate/local reference frame; string/object; 0..1 | source/user | conditionally required | spatial measurements | I/R |
| `processing_software` | Processing software/version; entity/string; 0..n | source/user | recommended | actual version if known | provenance/R |
| `processing_steps` | Derivation/processing history; list; 0..n | source/user | recommended for processed/derived data | ordered description | provenance/R |
| `uncertainty` | Measurement uncertainty; value/string; 0..n | source/user | recommended | do not calculate without method | R |
| `quality_notes` | QA/completeness notes; text; 0..n | source/user | recommended | distinguish metadata QA from scientific validity | R |
| `limitations` | Known validity/use limitations; text; 0..n | user/source | recommended | explicit | R |

## E. Provenance

`original_source`, `creator`, `generating_activity`, `derivation_activity`, `processing_history`, `software_version`, `source_record_version`, `previous_package_version`, and `responsible_agent` are **recommended** when applicable. They use source metadata, user input, or generated activity records. Validation checks presence and referential integrity; it does not invent missing provenance. These fields support R and lifecycle change interpretation.

## F. Access and rights

`access_url`, `landing_page`, `access_rights`, `authentication_requirements`, `access_conditions`, `license`, `rights_holder`, `restrictions`, and `embargo_until` are optional-to-conditionally-required depending on whether an asset is packaged, external, open, restricted, or embargoed. URI syntax and declared status are machine-checkable; reachability must be explicitly tested and timestamped rather than inferred from URI presence.

## G. Relationship stewardship

| Field | Definition / type / cardinality | Level | Validation / relevance |
|---|---|---|---|
| `relationship_id` | Stable relationship identity; string; 1 | prototype required | unique; F/I/lifecycle |
| `subject_ifc_global_id` | Selected component; string; 1 | prototype required | must match package component |
| `object_measurement_id` | Target dataset; string; 1 | prototype required | must match known dataset |
| `relationship_type` | controlled relationship semantics; enum; 1 | prototype required | `measuredOn`, `characterizes`, etc. |
| `rationale` | Human-readable justification; text; 1 | prototype required | non-empty; R/lifecycle |
| `evidence` | Structured EvidenceItems; list; 1..n | prototype required | source references resolve; R/lifecycle |
| `source_component_version` | IFC/model evidence version; string; 0..1 | recommended | trigger comparison |
| `source_measurement_version` | dataset evidence version; string; 0..1 | recommended | trigger comparison |
| `review_status` | lifecycle/review state; enum; 1 | prototype required | independent of FAIR support |
| `review_date` / `reviewer` | review provenance; datetime/agent; 0..1 | recommended | manual review traceability |
| `trigger_history` | reassessment triggers; list; 0..n | generated | category/severity/old/new/action |
| `decision_history` | stewardship decisions; list; 0..n | generated | immutable/review history |

## Simulation and research reproducibility extension

Simulation studies may additionally record numerical method (FEM/BEM/FDTD/SEA/TMM/etc.), solver/software/version, physics module, mesh/discretization, model size, frequency/time settings, boundary/excitation conditions, receiver locations, damping/material models, assumptions, computational environment, convergence/mesh independence, preprocessing, validation/calibration method, sensitivity/uncertainty analysis, code repository/commit, random seed, and reproduction workflow. These fields document provenance/reproducibility; the prototype does not evaluate whether a numerical method is scientifically correct.
