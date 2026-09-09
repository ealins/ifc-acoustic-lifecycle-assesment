# Metadata-Centered Migration Matrix

This matrix records how existing repository responsibilities are preserved and repositioned for the metadata-centered thesis artifact.

| Existing module / area | Existing responsibility | Preserve | Revised responsibility | Main modification | Compatibility concern |
|---|---|---|---|---|---|
| `app.py` | canonical Streamlit entrypoint | yes | metadata/package workflow entrypoint | keeps `research_enhanced_app` | deployment path remains `app.py` |
| `dashboard/ui/research_enhanced_app.py` | research-object UI | yes | nine metadata-centered workspaces | metadata profile/completeness/library pages | existing package state retained |
| `dashboard/ui/research_builder.py` | IFC + acoustic package builder | yes | 10-step metadata-centered creation workflow | conditional metadata, external refs, relationship evidence | does not fabricate missing metadata |
| `dashboard/backend/ifc_parser.py` | IfcOpenShell extraction | yes | IFC identity/context source | real component selection, schema/GlobalId/material/dimension evidence | full IFC remains authoritative |
| `fair_platform/models.py` | package storage model | yes | central acoustic component research object | independent completeness/FAIR/lifecycle/scientific states | legacy `FairAcousticPackage` retained |
| `fair_platform/metadata_profile.py` | new | — | executable prototype acoustic metadata profile | field definitions + requirement levels | exported snapshot generated from code |
| `fair_platform/completeness.py` | new | — | metadata completeness evaluator | conditional applicability and precise field states | independent from legacy FAIR assessment |
| `fair_platform/measurement.py` | structural data inspection | yes | safe source inspection | explicit origin remains user/source classification | no raw-measurement inference |
| `fair_platform/research_object.py` | qualified relationship/evidence | yes | supporting component-dataset relationship model | catalog origin + type restrictions + source checksums/reviews | internal names retained where safe |
| root `engine.py` / `models.py` | lifecycle engine / MappingSeries / MappingAssertion | yes | supporting relationship stewardship | no FAIR replacement | lifecycle semantics remain authoritative |
| `fair_platform/stewardship.py` | bridge to lifecycle engine | yes | run relationship lifecycle after package creation | triggers/history attached | legacy lifecycle states preserved |
| `fair_platform/triggers.py` | reassessment triggers | yes | metadata/relationship change evidence | access/profile/candidate/editorial distinctions | editorial changes do not imply stale relationship |
| `fair_platform/fair_support.py` | selected FAIR criteria | yes | secondary evaluation lens | independent from completeness | no certification claim |
| legacy `fair_platform/assessment.py` | compatibility FAIR booleans/status | yes | backward-compatibility only | not used as thesis primary outcome | old callers/tests remain readable |
| `fair_platform/metadata.py` | RDF/Turtle | yes | domain RDF/provenance/assessment graph | adds metadata profile/completeness entities | no full IFC-to-RDF conversion |
| `fair_platform/ro_crate.py` | RO-Crate-style JSON-LD | yes | principal portable research-object representation | profile/completeness/provenance links | not claimed as invented community profile |
| `fair_platform/manifest.py` | application asset manifest | yes | derived compatibility/index view | adds independent outcomes/profile | historical fields retained |
| `fair_platform/export.py` | ZIP export | yes | synchronized package/report generator | profile snapshot + separate reports/evidence/checksums | legacy report aliases retained |
| `fair_platform/validation.py` | package validation | yes | field-aware integrity and consistency validation | external-asset semantics + report identity | strict export remains available |
| `fair_platform/catalog.py` | local RDF catalog | yes | prototype acoustic component library | completeness/origin/type/status filters | not a certified repository |
| SHACL shapes | RDF constraints | yes | graph-level validation | complements, does not duplicate, conditional field registry | pySHACL retained |
| tests | lifecycle/FAIR/package regression | yes | controlled metadata and lifecycle evaluation | eight scenarios + export/integrity/library tests | old tests preserved |
| docs | research-object/lifecycle documentation | yes | metadata-centered thesis documentation | revised positioning/profile/evaluation docs | older docs may remain as implementation history |

## Preserved architectural boundary

The pivot is additive: lifecycle and relationship evidence remain functional, but the **primary research artifact is the acoustic metadata profile plus package model/workflow**. Metadata completeness, selected FAIR indicators, package integrity and controlled lifecycle scenarios evaluate that artifact from different perspectives.
