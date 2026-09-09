from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


PROFILE_ID = "https://example.org/fair-acoustic/profile/acoustic-component-metadata/0.2"
PROFILE_LABEL = "Prototype FAIR-Oriented Acoustic Component Metadata Profile"
PROFILE_VERSION = "0.2"
PROFILE_SCOPE = (
    "IFC-based building components and selected acoustic component datasets in the "
    "prototype IFC/VaBDat-oriented research-object workflow. This is not a universal "
    "acoustic metadata standard."
)


class RequirementLevel(str, Enum):
    PROTOTYPE_REQUIRED = "PROTOTYPE_REQUIRED"
    CONDITIONALLY_REQUIRED = "CONDITIONALLY_REQUIRED"
    RECOMMENDED = "RECOMMENDED"
    OPTIONAL = "OPTIONAL"
    NOT_CURRENTLY_SUPPORTED = "NOT_CURRENTLY_SUPPORTED"


class MetadataCategory(str, Enum):
    PACKAGE_IDENTIFICATION = "package_identification"
    IFC_COMPONENT = "ifc_component"
    ACOUSTIC_DATASET = "acoustic_dataset"
    MEASUREMENT_CONTEXT = "measurement_context"
    PROVENANCE = "provenance"
    ACCESS_RIGHTS = "access_and_rights"
    QUALITY_REUSE = "quality_and_reuse"
    RELATIONSHIP = "relationship"


@dataclass(frozen=True)
class MetadataFieldDefinition:
    field_name: str
    label: str
    category: MetadataCategory
    definition: str
    purpose: str
    data_type: str
    permitted_value_type: str
    cardinality: str
    requirement_level: RequirementLevel
    conditional_requirement: str
    source_of_value: str
    acquisition: str
    validation_rule: str
    example: str
    fair_dimension: str
    rdm_role: str
    relationship_assessment_role: str
    mapped_vocabulary: str
    limitation: str
    path: str
    condition_code: str = ""
    interpretation_critical: bool = False
    reuse_critical: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["category"] = self.category.value
        payload["requirement_level"] = self.requirement_level.value
        return payload


def _f(
    name: str,
    label: str,
    category: MetadataCategory,
    definition: str,
    path: str,
    *,
    requirement: RequirementLevel = RequirementLevel.OPTIONAL,
    condition: str = "",
    condition_code: str = "",
    source: str = "user or source metadata",
    acquisition: str = "manual",
    validation: str = "Non-empty when applicable.",
    example: str = "",
    fair: str = "",
    rdm: str = "description",
    relationship: str = "context only",
    vocabulary: str = "",
    limitation: str = "Not automatically verified unless stated.",
    data_type: str = "string",
    value_type: str = "literal",
    cardinality: str = "0..1",
    purpose: str = "Support interpretation and reuse of the package.",
    interpretation_critical: bool = False,
    reuse_critical: bool = False,
) -> MetadataFieldDefinition:
    return MetadataFieldDefinition(
        field_name=name,
        label=label,
        category=category,
        definition=definition,
        purpose=purpose,
        data_type=data_type,
        permitted_value_type=value_type,
        cardinality=cardinality,
        requirement_level=requirement,
        conditional_requirement=condition,
        source_of_value=source,
        acquisition=acquisition,
        validation_rule=validation,
        example=example,
        fair_dimension=fair,
        rdm_role=rdm,
        relationship_assessment_role=relationship,
        mapped_vocabulary=vocabulary,
        limitation=limitation,
        path=path,
        condition_code=condition_code,
        interpretation_critical=interpretation_critical,
        reuse_critical=reuse_critical,
    )


P = MetadataCategory.PACKAGE_IDENTIFICATION
I = MetadataCategory.IFC_COMPONENT
D = MetadataCategory.ACOUSTIC_DATASET
M = MetadataCategory.MEASUREMENT_CONTEXT
V = MetadataCategory.PROVENANCE
A = MetadataCategory.ACCESS_RIGHTS
Q = MetadataCategory.QUALITY_REUSE
R = MetadataCategory.RELATIONSHIP
REQ = RequirementLevel.PROTOTYPE_REQUIRED
COND = RequirementLevel.CONDITIONALLY_REQUIRED
REC = RequirementLevel.RECOMMENDED
OPT = RequirementLevel.OPTIONAL
NS = RequirementLevel.NOT_CURRENTLY_SUPPORTED


PROFILE_FIELDS: tuple[MetadataFieldDefinition, ...] = (
    # Package identification
    _f("package_identifier", "Package identifier", P, "Identifier for the research object/package.", "identifier", requirement=REQ, source="repository/user", validation="Non-empty. Local UUIDs/IDs must not be described as repository-issued PIDs.", example="urn:uuid:...", fair="Findable", rdm="identity", interpretation_critical=True),
    _f("package_title", "Package title", P, "Human-readable title of the acoustic component research object.", "metadata.title", requirement=REQ, source="user", validation="Non-empty user-supplied title; fallback package IDs do not satisfy this field.", example="Airborne sound insulation record for wall specimen A", fair="Findable", rdm="discovery", reuse_critical=True),
    _f("package_description", "Package description", P, "Description of the package scope and contents.", "metadata.description", requirement=REC, source="user", example="IFC-linked laboratory record...", fair="Findable/Reusable", rdm="discovery"),
    _f("package_version", "Package version", P, "Version of the package representation.", "version", requirement=REQ, source="user/workflow", validation="Non-empty version string.", example="1.0.0", fair="Findable/Reusable", rdm="versioning", reuse_critical=True),
    _f("creation_date", "Creation date", P, "Date/time when the package was created.", "created", requirement=REQ, source="workflow", acquisition="automatic", validation="ISO-8601 timestamp.", fair="Reusable", rdm="audit trail", data_type="datetime"),
    _f("modification_date", "Modification date", P, "Date/time of the most recent package modification.", "modified", requirement=REC, source="workflow", acquisition="automatic", validation="ISO-8601 when present.", fair="Reusable", rdm="audit trail", data_type="datetime"),
    _f("creators", "Creators", P, "Person(s) or agent(s) responsible for creating the research data/package.", "creator", requirement=REQ, source="user/source record", example="Researcher name", fair="Reusable", rdm="responsibility", vocabulary="schema:creator / dct:creator", reuse_critical=True),
    _f("contributors", "Contributors", P, "Additional contributors to the research object.", "research_context.contributors", requirement=OPT, source="user/source record", cardinality="0..n", data_type="array", value_type="string or entity reference", fair="Reusable", rdm="attribution"),
    _f("keywords", "Keywords", P, "Search terms describing the package.", "metadata.keywords", requirement=REC, source="user", cardinality="0..n", data_type="array", fair="Findable", rdm="discovery"),
    _f("language", "Language", P, "Language of descriptive metadata and human-readable documentation.", "metadata.language", requirement=REC, source="user", example="en", fair="Reusable", rdm="interpretation"),
    _f("citation", "Citation information", P, "Preferred citation for reuse of the package.", "research_context.preferred_citation", requirement=REC, source="user/publication", fair="Reusable", rdm="citation"),
    _f("metadata_profile_version", "Metadata profile version", P, "Version of this prototype acoustic metadata profile used for evaluation.", "metadata.metadata_profile_version", requirement=REQ, source="software profile", acquisition="automatic", validation=f"Must equal the active profile version ({PROFILE_VERSION}) for newly created packages.", example=PROFILE_VERSION, fair="Interoperable/Reusable", rdm="schema governance"),
    _f("metadata_language", "Metadata language", P, "Language used for human-readable metadata values.", "metadata.metadata_language", requirement=REC, source="user/workflow", example="en", fair="Reusable", rdm="interpretation"),

    # IFC component
    _f("ifc_asset_identifier", "IFC asset identifier", I, "Package-level identifier for the source IFC asset.", "metadata.ifc_asset_id", requirement=REQ, source="workflow", acquisition="automatic", validation="Must resolve to a packaged or referenced IFC asset.", fair="Findable/Interoperable", rdm="asset identity", relationship="relationship source asset", interpretation_critical=True),
    _f("source_ifc_filename", "Source IFC filename", I, "Original filename of the IFC model.", "metadata.source_geometry_filename", requirement=REQ, source="uploaded IFC", acquisition="automatic", fair="Reusable", rdm="source traceability"),
    _f("ifc_media_type", "IFC media type", I, "Media type of the IFC source.", "metadata.geometry_media_type", requirement=REQ, source="workflow", acquisition="automatic", validation="Expected IFC/STEP media type or documented application type.", example="application/x-step", fair="Interoperable"),
    _f("ifc_schema", "IFC schema", I, "IFC schema identifier extracted from the source model.", "metadata.geometry_ifc_schema", requirement=REQ, source="IFC", acquisition="automatic", example="IFC4", fair="Interoperable", rdm="technical context", relationship="component interpretation", interpretation_critical=True),
    _f("ifc_source_checksum", "IFC source checksum", I, "SHA-256 checksum of the preserved IFC source file.", "metadata.source_ifc_sha256", requirement=REQ, source="IFC bytes", acquisition="automatic", validation="Must match the packaged IFC bytes.", fair="Reusable", rdm="integrity/versioning", relationship="reassessment trigger", interpretation_critical=True),
    _f("ifc_source_version", "IFC source version", I, "Version label of the source IFC model when known.", "metadata.model_version", requirement=REC, source="IFC/source filename/user", acquisition="mixed", fair="Reusable", rdm="versioning", relationship="reassessment baseline"),
    _f("ifc_global_id", "Selected IFC GlobalId", I, "IFC GlobalId of the selected component.", "ifc_global_id", requirement=REQ, source="IFC", acquisition="automatic", validation="Must resolve to the selected component in the IFC source.", example="2qL6OSUnz6ZAzEOn1HxeD2", fair="Findable/Interoperable", rdm="entity identity", relationship="relationship subject", interpretation_critical=True),
    _f("ifc_entity_type", "IFC entity type", I, "IFC class of the selected component.", "metadata.geometry_ifc_class", requirement=REQ, source="IFC", acquisition="automatic", example="IfcWall", fair="Interoperable", rdm="semantic context", relationship="candidate/evidence context", interpretation_critical=True),
    _f("component_name", "Component name", I, "Name of the selected IFC component where supplied.", "metadata.geometry_name", requirement=REC, source="IFC", acquisition="automatic", fair="Findable/Reusable"),
    _f("ifc_type_assignment", "IFC type assignment", I, "Assigned IFC type object or equivalent type label where available.", "metadata.geometry_type_assignment", requirement=REC, source="IFC", acquisition="automatic", fair="Interoperable", relationship="type correspondence evidence"),
    _f("component_classification", "Component classification", I, "Classification or semantic class of the component where available.", "metadata.geometry_semantic_classification", requirement=REC, source="IFC/bSDD when supplied", acquisition="mixed", fair="Interoperable", relationship="semantic comparison"),
    _f("material_summary", "Material summary", I, "Materials associated with the selected component.", "metadata.geometry_materials", requirement=REC, source="IFC", acquisition="automatic", cardinality="0..n", data_type="array", fair="Reusable", relationship="material evidence"),
    _f("layer_summary", "Layer summary", I, "Ordered or summarized material-layer information where extractable.", "metadata.geometry_material_layers", requirement=REC, source="IFC", acquisition="automatic", cardinality="0..n", data_type="array", fair="Reusable", relationship="layer correspondence evidence"),
    _f("reliable_dimensions", "Reliably extracted dimensions", I, "Dimensions extracted with documented reliability from the selected IFC component.", "metadata.geometry_total_thickness_m", requirement=REC, source="IFC", acquisition="automatic", example="0.24", fair="Reusable", relationship="dimension/thickness evidence", data_type="number"),
    _f("spatial_context", "Spatial context", I, "Project/building/storey/space context for the selected component where available.", "metadata.geometry_spatial_context", requirement=REC, source="IFC", acquisition="automatic", data_type="object", fair="Reusable", relationship="project/location evidence"),
    _f("geometry_reference", "Geometry reference", I, "Relative package path or reference to the authoritative IFC source.", "geometry_reference", requirement=REQ, source="workflow", acquisition="automatic", validation="Must resolve to a packaged or declared external asset.", fair="Accessible/Interoperable", rdm="asset linkage", interpretation_critical=True),

    # Acoustic dataset
    _f("dataset_identifier", "Dataset identifier", D, "Identifier for the primary acoustic dataset/record.", "metadata.measurement_identifier", requirement=REQ, source="source record/user", validation="Non-empty and distinct in the package context.", example="M01", fair="Findable", rdm="dataset identity", relationship="relationship object", interpretation_critical=True),
    _f("dataset_original_filename", "Original filename", D, "Original acoustic source filename.", "metadata.source_measurement_filename", requirement=REQ, source="uploaded dataset", acquisition="automatic", fair="Reusable", rdm="source traceability"),
    _f("dataset_package_path", "Relative package path", D, "Relative path to the packaged primary acoustic dataset.", "measurement_reference", requirement=REQ, source="workflow", acquisition="automatic", validation="Safe relative path resolving to a package asset.", fair="Accessible/Interoperable", interpretation_critical=True),
    _f("dataset_external_uri", "External URI", D, "External source/landing URI for the dataset where applicable.", "dataset_uri", requirement=COND, condition="Required for metadata-only or externally referenced acoustic datasets.", condition_code="external_dataset", source="user/repository", validation="Valid URI syntax; URI presence alone does not prove reachability.", fair="Accessible", rdm="access"),
    _f("dataset_media_type", "Dataset media type", D, "Media type of the acoustic dataset.", "metadata.measurement_media_type", requirement=REQ, source="filename/workflow", acquisition="automatic", fair="Interoperable", interpretation_critical=True),
    _f("dataset_checksum", "Dataset checksum", D, "SHA-256 checksum of the packaged primary acoustic dataset.", "checksums.__measurement__", requirement=REQ, source="dataset bytes", acquisition="automatic", validation="Must match the packaged dataset; not generated for external resources that were not retrieved.", fair="Reusable", rdm="integrity/versioning", relationship="reassessment trigger", interpretation_critical=True),
    _f("dataset_byte_size", "Dataset byte size", D, "Byte size of the packaged acoustic dataset.", "asset_records.__measurement__.size_bytes", requirement=REQ, source="dataset bytes", acquisition="automatic", data_type="integer", fair="Reusable", rdm="technical description"),
    _f("dataset_version", "Dataset version", D, "Version of the acoustic source record when known.", "measurement_context.measurement_version", requirement=REQ, source="source record/user", fair="Findable/Reusable", rdm="versioning", relationship="reassessment baseline", reuse_critical=True),
    _f("dataset_creation_date", "Dataset creation date", D, "Creation date of the acoustic source where known.", "measurement_context.dataset_creation_date", requirement=REC, source="source record/user", data_type="date", fair="Reusable"),
    _f("dataset_modification_date", "Dataset modification date", D, "Modification date of the acoustic source where known.", "measurement_context.dataset_modification_date", requirement=OPT, source="source record/user", data_type="date", fair="Reusable"),
    _f("dataset_origin", "Dataset-origin classification", D, "Controlled classification of how the acoustic data originated.", "measurement_context.origin_classification", requirement=REQ, source="user verified against source", acquisition="manual/verified", validation="Must be a controlled MeasurementOrigin value and not unknown for complete prototype records.", fair="Reusable", rdm="interpretation", relationship="relationship-type restriction", interpretation_critical=True, reuse_critical=True),
    _f("acoustic_record_type", "Acoustic record type", D, "Declared type of acoustic measurement/record/result.", "measurement_context.measurement_type", requirement=REQ, source="user/source schema", fair="Findable/Reusable", rdm="domain description", interpretation_critical=True),
    _f("reported_quantity", "Measured or reported quantity", D, "Acoustic or vibration quantity represented by the dataset.", "measurement_context.measured_quantity", requirement=REQ, source="source/user", example="sound reduction index", fair="Interoperable/Reusable", interpretation_critical=True),
    _f("units", "Units", D, "Unit(s) for reported numeric quantities.", "measurement_context.unit", requirement=COND, condition="Required when the dataset reports numeric acoustic quantities for which units are meaningful.", condition_code="numeric_quantity", source="source/user", fair="Interoperable/Reusable", interpretation_critical=True),
    _f("frequency_range", "Frequency range", D, "Frequency range/resolution where applicable.", "measurement_context.frequency_range", requirement=COND, condition="Required when the declared acoustic record is frequency-dependent and the source provides or requires frequency context.", condition_code="frequency_dependent", source="source/user", fair="Reusable"),
    _f("data_schema", "Data schema/structure", D, "Schema or structural description of the acoustic data.", "measurement_context.data_structure", requirement=REC, source="source inspection/user", acquisition="mixed", fair="Interoperable"),
    _f("source_report", "Source report", D, "Report/document from which the acoustic record originates, where applicable.", "measurement_context.related_report", requirement=REC, source="source/user", fair="Reusable", rdm="source traceability"),
    _f("source_record_identifier", "Source record identifier", D, "Identifier of the original catalog, report, database, or record entry.", "measurement_context.source_record_identifier", requirement=REC, source="source/user", fair="Findable/Reusable", rdm="source traceability"),

    # Measurement / generation context
    _f("measurement_method", "Measurement method", M, "Method used to acquire direct or processed measurement data.", "measurement_context.measurement_method", requirement=COND, condition="Required for RAW_MEASUREMENT and PROCESSED_MEASUREMENT origins.", condition_code="measurement_origin", source="source/user", fair="Reusable", rdm="methodology", interpretation_critical=True, reuse_critical=True),
    _f("applicable_standard", "Applicable standard", M, "Measurement or reporting standard used where applicable.", "measurement_context.applicable_standard", requirement=REC, source="source/user", fair="Reusable"),
    _f("instrument", "Instrument", M, "Instrument or acquisition system used for a direct/processed measurement.", "measurement_context.instrument", requirement=COND, condition="Required for RAW_MEASUREMENT and PROCESSED_MEASUREMENT unless the source explicitly documents a non-instrument method.", condition_code="measurement_origin", source="source/user", fair="Reusable", rdm="instrument traceability", interpretation_critical=True),
    _f("instrument_manufacturer", "Instrument manufacturer", M, "Manufacturer of the measurement instrument where known.", "measurement_context.instrument_manufacturer", requirement=REC, condition="Recommended for measurement origins.", source="source/user", fair="Reusable"),
    _f("instrument_model", "Instrument model", M, "Model identifier of the instrument where known.", "measurement_context.instrument_model", requirement=REC, source="source/user", fair="Reusable"),
    _f("instrument_configuration", "Instrument configuration", M, "Configuration/settings relevant to interpretation of the measurement.", "measurement_context.instrument_configuration", requirement=REC, source="source/user", fair="Reusable"),
    _f("calibration_reference", "Calibration reference", M, "Calibration record/reference where available.", "measurement_context.calibration_reference", requirement=REC, condition="Recommended for direct measurements.", source="source/user", fair="Reusable"),
    _f("operator", "Operator", M, "Person/operator responsible for data acquisition where supplied.", "measurement_context.operator", requirement=REC, source="source/user", fair="Reusable", rdm="responsibility"),
    _f("institution", "Institution or laboratory", M, "Institution/laboratory responsible for measurement or generation activity.", "provenance.institution", requirement=REC, source="source/user", fair="Reusable", rdm="responsibility"),
    _f("measurement_date", "Measurement date", M, "Date of the measurement activity where applicable.", "measurement_context.measurement_date", requirement=COND, condition="Required for direct measurement origins when known/available in the source workflow.", condition_code="measurement_origin", source="source/user", fair="Reusable"),
    _f("measurement_location", "Measurement location", M, "Location/laboratory/site associated with acquisition.", "measurement_context.location", requirement=REC, source="source/user", fair="Reusable"),
    _f("environmental_conditions", "Environmental conditions", M, "Relevant environmental conditions during acquisition.", "measurement_context.environmental_conditions", requirement=REC, source="source/user", fair="Reusable"),
    _f("boundary_conditions", "Boundary conditions", M, "Boundary/support/test conditions relevant to interpretation.", "measurement_context.boundary_conditions", requirement=REC, source="source/user", fair="Reusable", relationship="comparability context"),
    _f("excitation_method", "Excitation method", M, "Excitation/source method where applicable.", "measurement_context.excitation_method", requirement=REC, source="source/user", fair="Reusable"),
    _f("sampling_information", "Sampling information", M, "Sampling rate, resolution, duration, or analogous acquisition settings.", "measurement_context.sampling_information", requirement=REC, source="source/user", fair="Reusable"),
    _f("measurement_points", "Measurement points or grid", M, "Measurement locations/grid definition where relevant.", "measurement_context.measurement_points", requirement=REC, source="source/user", fair="Reusable"),
    _f("reference_frame", "Coordinate/local reference frame", M, "Reference frame needed to interpret spatial measurements.", "measurement_context.local_reference_frame", requirement=REC, source="source/user", fair="Interoperable/Reusable"),
    _f("source_receiver_configuration", "Source-receiver configuration", M, "Source/receiver arrangement where relevant to the acoustic method.", "measurement_context.source_receiver_configuration", requirement=REC, source="source/user", fair="Reusable"),
    _f("processing_software", "Processing software", M, "Software used to process raw data into the supplied record.", "measurement_context.processing_software", requirement=COND, condition="Required for PROCESSED_MEASUREMENT or DERIVED_RESULT when processing/derivation was software-assisted and known.", condition_code="processed_or_derived", source="source/user", fair="Reusable", rdm="provenance", reuse_critical=True),
    _f("processing_steps", "Processing steps", M, "Human-readable description of processing/derivation steps.", "measurement_context.processing_steps", requirement=COND, condition="Required for PROCESSED_MEASUREMENT and DERIVED_RESULT.", condition_code="processed_or_derived", source="source/user", fair="Reusable", rdm="provenance", interpretation_critical=True, reuse_critical=True),
    _f("simulation_software", "Simulation/prediction software", M, "Software used to generate a simulation/prediction result.", "simulation_context.software", requirement=COND, condition="Required for SIMULATION_RESULT or PREDICTED_VALUE origins.", condition_code="simulation_origin", source="source/user", fair="Reusable", rdm="generation provenance", interpretation_critical=True, reuse_critical=True),
    _f("simulation_software_version", "Simulation/prediction software version", M, "Version of the software used to generate a simulation/prediction result.", "simulation_context.software_version", requirement=COND, condition="Required for SIMULATION_RESULT or PREDICTED_VALUE origins when known.", condition_code="simulation_origin", source="source/user", fair="Reusable", rdm="reproducibility"),
    _f("manufacturer", "Manufacturer", M, "Manufacturer responsible for a manufacturer-supplied value.", "measurement_context.manufacturer", requirement=COND, condition="Required for MANUFACTURER_VALUE origins.", condition_code="manufacturer_origin", source="source/user", fair="Reusable", interpretation_critical=True),
    _f("uncertainty", "Uncertainty", M, "Uncertainty information supplied with the acoustic result.", "quality_information.uncertainty", requirement=REC, source="source/user", fair="Reusable", rdm="quality/limitations", limitation="Absence does not prove the data are invalid; presence is not independently verified."),
    _f("accuracy_statement", "Accuracy statement", M, "Accuracy statement associated with the source record where supplied.", "quality_information.accuracy_statement", requirement=OPT, source="source/user", fair="Reusable"),
    _f("quality_information", "Quality information", M, "Quality notes supplied by the source or researcher.", "quality_information.quality_notes", requirement=REC, source="source/user", fair="Reusable"),
    _f("limitations", "Limitations", M, "Known limitations relevant to interpretation and reuse.", "quality_information.limitations", requirement=REQ, source="source/user", fair="Reusable", rdm="reuse boundary", reuse_critical=True, limitation="May explicitly state that limitations are not known; the software does not infer scientific suitability."),

    # Provenance
    _f("original_source", "Original source", V, "Source from which the acoustic data were obtained.", "provenance.original_source", requirement=REQ, source="source/user", fair="Reusable", rdm="provenance", reuse_critical=True),
    _f("provenance_creator", "Provenance creator", V, "Creator/responsible agent recorded in provenance metadata.", "provenance.creator", requirement=REQ, source="source/user", fair="Reusable", vocabulary="prov:wasAttributedTo / dct:creator", reuse_critical=True),
    _f("generating_activity", "Generating activity", V, "Activity that generated or assembled the dataset/package.", "provenance.generating_activity", requirement=REQ, source="source/workflow", fair="Reusable", vocabulary="prov:Activity", reuse_critical=True),
    _f("responsible_agent", "Responsible agent", V, "Person or organization responsible for the relevant generation/processing activity.", "provenance.responsible_agent", requirement=REC, source="source/user", fair="Reusable", vocabulary="prov:Agent"),
    _f("source_record", "Source record", V, "Reference to the original record or database entry.", "provenance.source_record", requirement=REC, source="source/user", fair="Reusable"),
    _f("source_record_version", "Source record version", V, "Version of the original source record.", "provenance.source_record_version", requirement=REC, source="source/user", fair="Reusable"),
    _f("processing_activity", "Processing activity", V, "Activity that transformed the source into the supplied dataset.", "provenance.processing_activity", requirement=COND, condition="Required for processed/derived data when such an activity occurred.", condition_code="processed_or_derived", source="source/user", fair="Reusable", vocabulary="prov:Activity"),
    _f("derivation_activity", "Derivation activity", V, "Derivation activity linking the supplied result to prior data.", "provenance.derivation_activity", requirement=COND, condition="Required for DERIVED_RESULT when derivation is claimed.", condition_code="derived_origin", source="source/user", fair="Reusable", vocabulary="prov:wasDerivedFrom"),
    _f("previous_package_version", "Previous package version", V, "Prior package version from which this package supersedes/derives.", "provenance.previous_package_version", requirement=OPT, source="workflow/user", fair="Reusable", rdm="version lineage"),
    _f("previous_dataset_version", "Previous dataset version", V, "Prior dataset version when version lineage is known.", "provenance.previous_dataset_version", requirement=OPT, source="source/user", fair="Reusable", rdm="version lineage"),
    _f("provenance_notes", "Provenance notes", V, "Additional provenance explanation not represented in structured fields.", "provenance.notes", requirement=OPT, source="user", fair="Reusable"),

    # Access and rights
    _f("access_url", "Access URL", A, "URL used to retrieve or request the dataset/package where externally hosted.", "access_context.access_url", requirement=COND, condition="Required for externally referenced data when a retrieval endpoint is known.", condition_code="external_dataset", source="user/repository", validation="Valid URI syntax.", fair="Accessible"),
    _f("landing_page", "Landing page", A, "Human-facing landing page for the dataset/package where available.", "access_context.landing_page", requirement=REC, source="user/repository", fair="Findable/Accessible"),
    _f("repository_identifier", "Repository identifier", A, "Identifier/name of the repository or service providing access.", "access_context.repository_identifier", requirement=REC, source="user/repository", fair="Accessible"),
    _f("access_protocol", "Access protocol", A, "Protocol/mechanism used to obtain data.", "access_context.access_protocol", requirement=REC, source="user/repository", example="HTTPS", fair="Accessible"),
    _f("access_rights", "Access rights", A, "Access category such as open, restricted, embargoed, or metadata-only.", "access_context.access_rights", requirement=REQ, source="user/repository", fair="Accessible/Reusable", reuse_critical=True),
    _f("authentication_requirement", "Authentication requirement", A, "Authentication requirement where access is controlled.", "access_context.authentication_requirements", requirement=COND, condition="Required when access rights indicate restricted/authenticated access.", condition_code="restricted_access", source="user/repository", fair="Accessible"),
    _f("licence", "Licence", A, "Licence or reuse-rights statement applying to the acoustic dataset/package.", "license", requirement=REQ, source="source/user/repository", validation="URI syntax when represented as URI, otherwise explicit reuse statement.", fair="Reusable", rdm="rights", reuse_critical=True),
    _f("rights_holder", "Rights holder", A, "Rights holder where supplied.", "access_context.rights_holder", requirement=REC, source="source/user", fair="Reusable"),
    _f("reuse_conditions", "Reuse conditions", A, "Additional reuse conditions or restrictions beyond the licence.", "access_context.reuse_conditions", requirement=REC, source="source/user", fair="Reusable"),
    _f("restrictions", "Restrictions", A, "Known legal/access/reuse restrictions.", "access_context.restrictions", requirement=REC, source="source/user", fair="Accessible/Reusable"),
    _f("embargo_information", "Embargo information", A, "Embargo date/conditions where supplied.", "access_context.embargo_until", requirement=COND, condition="Required when access rights indicate embargoed data.", condition_code="embargoed_access", source="user/repository", fair="Accessible"),
    _f("access_status", "Access status check", A, "Reachability/access status for an external resource.", "access_context.external_uri_status", requirement=COND, condition="Required for external references during an access evaluation.", condition_code="external_dataset", source="access check/user", validation="REACHABLE, UNREACHABLE, ACCESS_CONTROLLED, NOT_TESTED, or UNKNOWN; URI syntax alone is not reachability evidence.", fair="Accessible", rdm="access evidence"),
    _f("access_status_timestamp", "Access status timestamp", A, "Timestamp for a reachability/access check.", "access_context.external_uri_checked_at", requirement=COND, condition="Required when external_uri_status records a performed check.", condition_code="access_checked", source="access check", acquisition="automatic/manual", fair="Accessible"),

    # Quality and reuse
    _f("intended_use", "Intended use", Q, "Intended reuse scenario(s) for the acoustic component record.", "research_context.intended_reuse", requirement=REQ, source="user/source", fair="Reusable", rdm="reuse scope", reuse_critical=True),
    _f("known_limitations", "Known limitations", Q, "Known limitations or explicit statement that none are documented.", "quality_information.limitations", requirement=REQ, source="source/user", fair="Reusable", rdm="reuse boundary", reuse_critical=True),
    _f("validation_status", "Validation status", Q, "Source-provided or expert-reviewed validation status when available.", "quality_information.validation_status", requirement=REC, source="source/expert", fair="Reusable", limitation="The prototype does not invent or infer scientific validation."),
    _f("supported_reuse", "Supported reuse scenarios", Q, "Reuse scenarios explicitly supported by the package author/source.", "quality_information.supported_reuse_scenarios", requirement=REC, source="user/source", cardinality="0..n", data_type="array", fair="Reusable"),
    _f("unsupported_uses", "Unsupported uses", Q, "Uses explicitly outside the package scope.", "quality_information.unsupported_uses", requirement=REC, source="user/source", cardinality="0..n", data_type="array", fair="Reusable"),
    _f("related_publications", "Related publications", Q, "Publication identifiers or references related to the data.", "research_context.related_publication", requirement=OPT, source="user/publication", fair="Findable/Reusable"),
    _f("domain_review_status", "Domain review status", Q, "Whether an acoustic-domain expert has reviewed the package metadata or relationship.", "quality_information.domain_review_status", requirement=REC, source="expert/workflow", fair="Reusable", limitation="Must remain NOT_REVIEWED/unknown unless an actual review occurred."),

    # Relationship metadata
    _f("relationship_identifier", "Relationship identifier", R, "Identifier of the qualified component-dataset relationship.", "relationships.0.relationship_id", requirement=REQ, source="workflow", acquisition="automatic", fair="Findable/Interoperable", rdm="relationship identity", relationship="primary relationship identity", interpretation_critical=True),
    _f("relationship_component_identifier", "IFC component identifier", R, "Relationship subject component identifier.", "relationships.0.subject_component_id", requirement=REQ, source="workflow/IFC", acquisition="automatic", fair="Interoperable", relationship="subject", interpretation_critical=True),
    _f("relationship_global_id", "Relationship IFC GlobalId", R, "GlobalId used by the relationship claim.", "relationships.0.subject_ifc_global_id", requirement=REQ, source="IFC/workflow", acquisition="automatic", validation="Must match the selected IFC GlobalId.", fair="Interoperable", relationship="subject consistency", interpretation_critical=True),
    _f("relationship_dataset_identifier", "Relationship dataset identifier", R, "Dataset identifier used by the relationship claim.", "relationships.0.object_measurement_id", requirement=REQ, source="workflow/dataset", acquisition="automatic", validation="Must match a dataset in the package.", fair="Interoperable", relationship="object consistency", interpretation_critical=True),
    _f("relationship_type", "Relationship type", R, "Controlled semantic type of the component-dataset connection.", "relationships.0.relationship_type", requirement=REQ, source="user/workflow", validation="Controlled RelationshipType; MEASURED_ON is restricted to measurement-origin data with direct measurement evidence.", fair="Interoperable/Reusable", relationship="decision semantics", interpretation_critical=True, reuse_critical=True),
    _f("relationship_scope", "Relationship scope", R, "Scope at which the relationship applies (component, specimen, equivalent assembly, etc.).", "relationships.0.scope", requirement=REQ, source="user", fair="Reusable", relationship="scope", interpretation_critical=True),
    _f("relationship_rationale", "Relationship rationale", R, "Human-readable explanation of why the dataset is linked to the selected component.", "relationships.0.rationale", requirement=REQ, source="user/expert/source", fair="Reusable", relationship="decision rationale", interpretation_critical=True, reuse_critical=True),
    _f("relationship_evidence", "Relationship evidence", R, "Structured evidence items supporting/contradicting the relationship claim.", "relationships.0.evidence", requirement=REQ, source="source/user/expert/algorithm", acquisition="mixed", cardinality="1..n", data_type="array", fair="Reusable", relationship="evidence basis", interpretation_critical=True, reuse_critical=True),
    _f("relationship_creator", "Relationship creator", R, "Agent who created the relationship claim when supplied.", "relationships.0.created_by", requirement=REC, source="user/workflow", fair="Reusable", relationship="responsibility"),
    _f("relationship_reviewer", "Relationship reviewer", R, "Agent who reviewed the relationship when an actual review occurred.", "relationships.0.last_reviewed_by", requirement=REC, source="expert/workflow", fair="Reusable", relationship="review responsibility"),
    _f("relationship_review_date", "Relationship review date", R, "Date/time of the latest relationship review when performed.", "relationships.0.last_reviewed_at", requirement=REC, source="workflow", fair="Reusable", relationship="review currency"),
    _f("relationship_source_ifc_version", "Relationship source IFC version", R, "IFC source version against which the relationship was assessed.", "relationships.0.source_component_version", requirement=REC, source="workflow/IFC", fair="Reusable", relationship="reassessment baseline"),
    _f("relationship_source_dataset_version", "Relationship source dataset version", R, "Dataset version against which the relationship was assessed.", "relationships.0.source_measurement_version", requirement=REQ, source="workflow/dataset", fair="Reusable", relationship="reassessment baseline", reuse_critical=True),
    _f("relationship_version", "Relationship version", R, "Version of the relationship assertion/stewardship record.", "relationships.0.relationship_version", requirement=REQ, source="workflow/user", fair="Reusable", relationship="versioning"),
    _f("approval_status", "Approval status", R, "Approval/review status of the relationship.", "relationships.0.approved_at", requirement=REC, source="workflow/expert", fair="Reusable", relationship="approval evidence", limitation="Absence means not approved; no approval is fabricated."),
    _f("lifecycle_status", "Lifecycle assessment status", R, "Current lifecycle stewardship status of the relationship.", "lifecycle_status", requirement=REC, source="lifecycle engine", acquisition="automatic", fair="Reusable", relationship="lifecycle outcome"),
    _f("recommended_action", "Recommended action", R, "Recommended action following lifecycle or evidence review.", "relationships.0.decision_history.0.recommended_action", requirement=OPT, source="lifecycle assessment/workflow", fair="Reusable", relationship="stewardship action"),
)


FIELD_BY_NAME = {field.field_name: field for field in PROFILE_FIELDS}


def profile_as_dict() -> dict[str, Any]:
    return {
        "profile_id": PROFILE_ID,
        "label": PROFILE_LABEL,
        "version": PROFILE_VERSION,
        "scope": PROFILE_SCOPE,
        "authority": "fair_platform.metadata_profile.PROFILE_FIELDS",
        "synchronization_note": (
            "The Python profile is the executable authority. Package profile snapshots and UI tables "
            "are generated from this definition; SHACL remains focused on RDF graph constraints."
        ),
        "requirement_levels": [item.value for item in RequirementLevel],
        "categories": [item.value for item in MetadataCategory],
        "fields": [field.to_dict() for field in PROFILE_FIELDS],
    }
