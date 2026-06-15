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


class FlowNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    type: FlowNodeType
    structural_path: str
    source: SourceReference
    label: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict)
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


class ServiceSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: ServiceIdentity
    service_type: ServiceType
    source: SourceReference


class FlowService(BaseModel):
    model_config = ConfigDict(frozen=True)

    identity: ServiceIdentity
    service_type: ServiceType = ServiceType.FLOW
    description: str | None = None
    signature: ServiceSignature
    classification: ClassificationResult
    flow_tree: FlowNode | None = None
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    call_occurrences: list[CallOccurrence] = Field(default_factory=list)
    unique_dependencies: list[UniqueDependency] = Field(default_factory=list)
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

    schema_version: str = "analysis.v2"
    tool_version: str
    packages: list[AnalyzedPackage] = Field(default_factory=list)
    metrics: AnalysisMetrics = Field(default_factory=AnalysisMetrics)
    call_occurrences: list[CallOccurrence] = Field(default_factory=list)
    unique_dependencies: list[UniqueDependency] = Field(default_factory=list)
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
