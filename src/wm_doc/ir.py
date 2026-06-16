from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class FindingStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNKNOWN = "UNKNOWN"
    MALFORMED = "MALFORMED"
    UNRESOLVED = "UNRESOLVED"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class FactBasis(StrEnum):
    CONFIRMED = "CONFIRMED"
    RECONSTRUCTED = "RECONSTRUCTED"
    INFERRED = "INFERRED"
    UNRESOLVED = "UNRESOLVED"


class Confidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ServiceType(StrEnum):
    FLOW = "FLOW"
    JAVA = "JAVA"
    SPECIFICATION = "SPECIFICATION"
    UNKNOWN = "UNKNOWN"


class CallType(StrEnum):
    INVOKE = "INVOKE"
    MAPINVOKE = "MAPINVOKE"


class DependencyKind(StrEnum):
    INVOKES = "INVOKES"
    USES_TRANSFORMER = "USES_TRANSFORMER"


class FlowNodeType(StrEnum):
    FLOW = "FLOW"
    SEQUENCE = "SEQUENCE"
    BRANCH = "BRANCH"
    BRANCH_CASE = "BRANCH_CASE"
    LOOP = "LOOP"
    MAP = "MAP"
    INVOKE = "INVOKE"
    MAPINVOKE = "MAPINVOKE"
    EXIT = "EXIT"


class InterpretationConfidence(StrEnum):
    CONFIRMED = "CONFIRMED"
    PARTIALLY_INTERPRETED = "PARTIALLY_INTERPRETED"
    RAW_ONLY = "RAW_ONLY"


class MappingOperationType(StrEnum):
    COPY = "COPY"
    SET = "SET"
    DELETE = "DELETE"


class TransformerBindingDirection(StrEnum):
    INTO_TRANSFORMER = "INTO_TRANSFORMER"
    FROM_TRANSFORMER = "FROM_TRANSFORMER"


class LiteralDisclosure(StrEnum):
    REDACTED = "REDACTED"
    INCLUDED = "INCLUDED"
    OMITTED = "OMITTED"
    BLOCKED_SECRET = "BLOCKED_SECRET"
    NOT_PRESENT = "NOT_PRESENT"


class TextDisclosure(StrEnum):
    REDACTED = "REDACTED"
    INCLUDED = "INCLUDED"
    OMITTED = "OMITTED"
    BLOCKED_SECRET = "BLOCKED_SECRET"


class AttributeClassification(StrEnum):
    TECHNICAL_VALUE = "TECHNICAL_VALUE"
    FREE_TEXT = "FREE_TEXT"
    SECRET_SENSITIVE_TEXT = "SECRET_SENSITIVE_TEXT"
    STRUCTURAL_IDENTIFIER = "STRUCTURAL_IDENTIFIER"
    UNKNOWN = "UNKNOWN"


class Importance(StrEnum):
    IMPORTANT = "IMPORTANT"
    NORMAL = "NORMAL"
    LOW = "LOW"


class Layer(StrEnum):
    CHANNEL = "CHANNEL"
    CORE = "CORE"
    ADAPTER = "ADAPTER"
    UTILITY = "UTILITY"
    UNKNOWN = "UNKNOWN"


class SourceReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    artifact_type: str | None = None
    xml_path: str | None = None
    source_node: str | None = None
    line: int | None = None


class AnalysisFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: FindingStatus
    code: str
    message: str
    source: SourceReference
    occurrence_count: int = 1
    sample_source_references: list[SourceReference] = Field(default_factory=list)


class ClassificationMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    field: str
    pattern: str
    value: str
    explanation: str


class ClassificationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    importance: Importance
    layer: str
    importance_match: ClassificationMatch | None = None
    layer_match: ClassificationMatch | None = None


class ServiceIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    package: str
    namespace: str
    name: str
    full_name: str
    basis: FactBasis
    source: SourceReference


class SignatureField(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    data_type: str | None = None
    dimensions: int | None = None
    optional: bool | None = None
    document_reference: str | None = None
    wrapper_type: str | None = None
    children: list[SignatureField] = Field(default_factory=list)
    source: SourceReference


class ServiceSignature(BaseModel):
    model_config = ConfigDict(frozen=True)

    inputs: list[SignatureField] = Field(default_factory=list)
    outputs: list[SignatureField] = Field(default_factory=list)
    source: SourceReference


class SecretGuardSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    strategy_version: str = "secret-guard.v1"


class ExtractionPolicySnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    literal_mode: str = "redact"
    free_text_mode: str = "include"
    secret_guard: SecretGuardSnapshot = Field(default_factory=SecretGuardSnapshot)


class TextValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    role: str
    disclosure: TextDisclosure
    length: int | None = None
    marker: str | None = None
    value: str | None = None
    source: SourceReference | None = None


class AttributeValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    classification: AttributeClassification
    present: bool = True
    value: str | None = None
    text: TextValue | None = None
    source: SourceReference


class PipelinePath(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_path: str
    segments: list[str] = Field(default_factory=list)
    is_absolute: bool
    contains_index: bool
    contains_wildcard: bool
    contains_document_ref: bool


class MappingEndpoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_path: str
    path: PipelinePath
    source: SourceReference


class LiteralValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    declared_type: str | None = None
    declared_field_name: str | None = None
    length: int | None = None
    is_empty: bool | None = None
    is_null_like: bool | None = None
    disclosure: LiteralDisclosure = LiteralDisclosure.NOT_PRESENT
    marker: str | None = None
    value: str | None = None
    source: SourceReference | None = None


class MapSchemaMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    field_count: int | None = None
    confidence: InterpretationConfidence = InterpretationConfidence.PARTIALLY_INTERPRETED
    source: SourceReference


class MappingOperation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    service: str
    flow_map_id: str
    operation_type: MappingOperationType
    order: int
    map_operation_order: int
    document_traversal_order: int | None = None
    structural_path: str
    confidence: InterpretationConfidence
    source: SourceReference
    raw_attrs: dict[str, str] = Field(default_factory=dict)
    technical_attrs: dict[str, str] = Field(default_factory=dict)
    text_attrs: dict[str, TextValue] = Field(default_factory=dict)
    unknown_attrs: list[AttributeValue] = Field(default_factory=list)
    source_endpoint: MappingEndpoint | None = None
    target_endpoint: MappingEndpoint | None = None
    delete_endpoint: MappingEndpoint | None = None
    literal: LiteralValue | None = None
    transformer_binding_ids: list[str] = Field(default_factory=list)


class TransformerBinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    service: str
    transformer_service: str
    call_occurrence_id: str
    flow_map_id: str
    mapping_operation_id: str
    direction: TransformerBindingDirection
    order: int
    structural_path: str
    transformer_endpoint: MappingEndpoint | None = None
    pipeline_endpoint: MappingEndpoint | None = None
    literal: LiteralValue | None = None
    source: SourceReference


class FlowMap(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    service: str
    mode: str | None = None
    order: int
    structural_path: str
    parent_flow_path: list[str] = Field(default_factory=list)
    parent_call_occurrence_id: str | None = None
    confidence: InterpretationConfidence = InterpretationConfidence.CONFIRMED
    source_schema: MapSchemaMetadata | None = None
    target_schema: MapSchemaMetadata | None = None
    operation_ids: list[str] = Field(default_factory=list)
    raw_attrs: dict[str, str] = Field(default_factory=dict)
    technical_attrs: dict[str, str] = Field(default_factory=dict)
    text_attrs: dict[str, TextValue] = Field(default_factory=dict)
    unknown_attrs: list[AttributeValue] = Field(default_factory=list)
    source: SourceReference


class FlowNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: FlowNodeType
    structural_path: str
    source: SourceReference
    label: TextValue | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
    text_attributes: dict[str, TextValue] = Field(default_factory=dict)
    unknown_attributes: list[AttributeValue] = Field(default_factory=list)
    parent_id: str | None = None
    children: list[FlowNode] = Field(default_factory=list)
    exit_on: str | None = None
    form: str | None = None
    switch: str | None = None
    evaluate_labels: bool | None = None
    is_default_case: bool | None = None
    in_array: str | None = None
    out_array: str | None = None
    exit_from: str | None = None
    signal: str | None = None
    failure_message: str | None = None
    target: str | None = None
    call_occurrence_id: str | None = None


class CallOccurrence(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    caller: str
    target: str
    call_type: CallType
    dependency_kind: DependencyKind
    order: int
    parent_flow_path: list[str] = Field(default_factory=list)
    structural_path: str
    resolved: bool
    target_type: ServiceType | None = None
    target_classification: ClassificationResult
    source: SourceReference


class UniqueDependency(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_service: str
    target_service: str
    dependency_kind: DependencyKind
    resolved: bool
    target_type: ServiceType | None = None
    target_classification: ClassificationResult
    occurrence_count: int
    occurrence_ids: list[str] = Field(default_factory=list)
    source_samples: list[SourceReference] = Field(default_factory=list)


class AnalysisMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    call_occurrence_count: int = 0
    unique_dependency_count: int = 0
    resolved_call_occurrence_count: int = 0
    unresolved_call_occurrence_count: int = 0
    resolved_unique_dependency_count: int = 0
    unresolved_unique_dependency_count: int = 0
    call_type_counts: dict[str, int] = Field(default_factory=dict)
    unique_dependency_kind_counts: dict[str, int] = Field(default_factory=dict)
    flow_node_counts: dict[str, int] = Field(default_factory=dict)
    flow_map_count: int = 0
    mapping_operation_count: int = 0
    mapping_operation_type_counts: dict[str, int] = Field(default_factory=dict)
    transformer_binding_count: int = 0
    transformer_binding_direction_counts: dict[str, int] = Field(default_factory=dict)
    partially_interpreted_mapping_count: int = 0


class ServiceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: ServiceIdentity
    service_type: ServiceType
    source: SourceReference


class FlowService(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: ServiceIdentity
    service_type: ServiceType = ServiceType.FLOW
    description: TextValue | None = None
    signature: ServiceSignature
    classification: ClassificationResult
    flow_tree: FlowNode | None = None
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    call_occurrences: list[CallOccurrence] = Field(default_factory=list)
    unique_dependencies: list[UniqueDependency] = Field(default_factory=list)
    flow_maps: list[FlowMap] = Field(default_factory=list)
    mapping_operations: list[MappingOperation] = Field(default_factory=list)
    transformer_bindings: list[TransformerBinding] = Field(default_factory=list)
    extraction_policy: ExtractionPolicySnapshot = Field(default_factory=ExtractionPolicySnapshot)
    findings: list[AnalysisFinding] = Field(default_factory=list)
    source: SourceReference


class AnalyzedPackage(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    root: str
    services: list[FlowService] = Field(default_factory=list)
    service_index: list[ServiceSummary] = Field(default_factory=list)
    findings: list[AnalysisFinding] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "analysis.v4"
    tool_version: str
    packages: list[AnalyzedPackage] = Field(default_factory=list)
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    extraction_policy: ExtractionPolicySnapshot = Field(default_factory=ExtractionPolicySnapshot)
    call_occurrences: list[CallOccurrence] = Field(default_factory=list)
    unique_dependencies: list[UniqueDependency] = Field(default_factory=list)
    flow_maps: list[FlowMap] = Field(default_factory=list)
    mapping_operations: list[MappingOperation] = Field(default_factory=list)
    transformer_bindings: list[TransformerBinding] = Field(default_factory=list)
    findings: list[AnalysisFinding] = Field(default_factory=list)


class ArtifactFile(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    role: str
    active: bool
    size_bytes: int


class ArtifactIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    namespace: str | None = None
    name: str | None = None
    full_name: str | None = None
    basis: FactBasis = FactBasis.UNRESOLVED


class ArtifactCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    relative_path: str
    probable_type: str
    files: list[ArtifactFile] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: Confidence
    parser_responsibility: str
    status: FindingStatus
    identity: ArtifactIdentity | None = None
    source: SourceReference


class PackageInventory(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    root: str
    evidence: list[str] = Field(default_factory=list)
    manifest: dict[str, str | list[str] | None] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    artifacts: list[ArtifactCandidate] = Field(default_factory=list)
    findings: list[AnalysisFinding] = Field(default_factory=list)


class FileSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    extension: str
    count: int


class InventoryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "inventory.v0"
    tool_version: str
    scan_root: str
    packages: list[PackageInventory] = Field(default_factory=list)
    file_summary: list[FileSummary] = Field(default_factory=list)
    findings: list[AnalysisFinding] = Field(default_factory=list)


def source_for(path: Path, scan_root: Path, artifact_type: str | None = None) -> SourceReference:
    return SourceReference(path=stable_relative_path(path, scan_root), artifact_type=artifact_type)


def stable_relative_path(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()
