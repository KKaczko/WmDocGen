"""The explorer data contract `wm-doc-explorer.v1`.

These models describe every JSON file the explorer app reads. They are a projection of the
analysis made for a browser, not a copy of `analysis.v11`: the vocabulary is lowercase and
owned here, so renaming an analysis enum never reaches the app.

Versioning: optional fields may be added within v1; removing or renaming anything is v2.
`docs/contracts/explorer.v1.schema.json` is generated from these models (`contract_schema`).
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel
from pydantic.json_schema import models_json_schema

ContractVersion = Literal["wm-doc-explorer.v1"]
CONTRACT: ContractVersion = "wm-doc-explorer.v1"

ServiceKind = Literal["flow", "java", "adapter", "opaque"]
AnalysisLevel = Literal["full", "partial", "opaque"]
CallStatus = Literal["resolved", "platform", "outside", "unresolved", "dynamic", "unsupported"]
Relation = Literal["invokes", "transformer", "java-invoke", "call-like"]
DescriptionState = Literal["approved", "stale", "draft", "edited", "none"]
DescriptionsShown = Literal["approved", "all", "none"]
DatasetKind = Literal["synthetic", "private"]
Severity = Literal["info", "warning", "error"]


class ContractModel(BaseModel):
    # Every field is always written, so the schema marks fields with defaults as required.
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
        json_schema_serialization_defaults_required=True,
    )


# --- manifest.json ---------------------------------------------------------------------------


class Generator(ContractModel):
    tool: str
    version: str
    analysis_schema: str


class Dataset(ContractModel):
    kind: DatasetKind
    label: str


class Disclosure(ContractModel):
    literals: Literal["excluded"] = "excluded"
    designer_comments: Literal["excluded"] = "excluded"
    notes: Literal["excluded"] = "excluded"
    descriptions: DescriptionsShown
    withheld_strings: int


class Counts(ContractModel):
    packages: int
    services: int
    document_types: int
    calls: int
    approved_descriptions: int


class Manifest(ContractModel):
    contract: ContractVersion = CONTRACT
    generator: Generator
    dataset: Dataset
    disclosure: Disclosure
    counts: Counts
    # sha256 over "<path> <sha256>" lines of every other data file, sorted by path.
    digest: str = ""


# --- search.json -----------------------------------------------------------------------------


class SearchService(ContractModel):
    id: str
    name: str
    package: str
    kind: ServiceKind
    analysis: AnalysisLevel
    description: DescriptionState
    purpose: str | None = None


class SearchPackage(ContractModel):
    id: str
    name: str
    services: int
    overview: DescriptionState
    purpose: str | None = None


class SearchIndex(ContractModel):
    contract: ContractVersion = CONTRACT
    services: list[SearchService]
    packages: list[SearchPackage]


# --- services/<id>.json ----------------------------------------------------------------------


class SourceRef(ContractModel):
    path: str
    xml_path: str | None = None


class Finding(ContractModel):
    code: str
    severity: Severity
    count: int
    message: str
    source: SourceRef | None = None


class AnalysisInfo(ContractModel):
    status: AnalysisLevel
    disabled_steps: int
    findings: list[Finding]
    findings_total: int


class DocumentRef(ContractModel):
    name: str
    resolved: bool


class SignatureField(ContractModel):
    name: str
    type: str | None = None
    dimension: int
    optional: bool | None = None
    document: DocumentRef | None = None
    children: list[SignatureField] = Field(default_factory=list)


class Signature(ContractModel):
    origin: Literal["service", "specification"]
    specification: str | None = None
    inputs: list[SignatureField]
    outputs: list[SignatureField]
    truncated: bool


class Call(ContractModel):
    target: str
    target_id: str | None = None
    status: CallStatus
    target_kind: ServiceKind | None = None
    target_analysis: AnalysisLevel | None = None
    relation: Relation
    count: int
    first_order: int | None = None
    # Platform description, external system name, or nothing.
    note: str | None = None
    evidence: list[SourceRef]


class ServiceLink(ContractModel):
    id: str
    name: str


class PackageRef(ContractModel):
    id: str
    name: str


# --- text -------------------------------------------------------------------------------------
# Text is never HTML or Markdown: it is a list of plain segments. A code segment names
# something exactly; `ref` is the ID of the analysed service it names, when it names one.


class TextSegment(ContractModel):
    kind: Literal["text"] = "text"
    text: str


class CodeSegment(ContractModel):
    kind: Literal["code"] = "code"
    code: str
    ref: str | None = None


Segment = Annotated[TextSegment | CodeSegment, Field(discriminator="kind")]


class PathStep(ContractModel):
    """A service on a call chain; `id` is set when it is an analysed service."""

    name: str
    id: str | None = None


class EntryPoint(ContractModel):
    kind: str
    name: list[Segment]
    # From the entry service down to this service, both included.
    path: list[PathStep]


class Effect(ContractModel):
    action: str
    object: list[Segment]
    where: list[Segment]
    known_from: str
    # Callees through which this service reaches the data; empty when it is the service itself.
    via: list[PathStep]


class DocumentUse(ContractModel):
    name: str
    role: Literal["input", "output", "input-output"]
    resolved: bool


class AdapterInfo(ContractModel):
    """Allow-listed JDBC adapter configuration (see wm_doc.adapters); never credentials."""

    adapter_type: str | None = None
    operation: str | None = None
    template: str | None = None
    connection: str | None = None
    tables: list[str] = Field(default_factory=list)
    database_product: str | None = None
    database_name: str | None = None
    transaction_type: str | None = None


SectionKey = Literal[
    # service descriptions
    "purpose",
    "usage",
    "dataEffects",
    "mainSteps",
    "detailedFlow",
    "errorHandling",
    # package and server overviews
    "capabilities",
    "areas",
    "entryPoints",
    "systemsAndData",
]


class DescriptionSection(ContractModel):
    key: SectionKey
    paragraphs: list[list[Segment]] = Field(default_factory=list)
    items: list[list[Segment]] = Field(default_factory=list)


class Description(ContractModel):
    """A reviewed or drafted description file: model-written, never a fact."""

    state: Literal["approved", "stale", "draft", "edited"]
    model: str
    detail: str | None = None
    # Names the model used that the facts do not contain (`describe --keep-unverified`).
    unverified_names: list[str] = Field(default_factory=list)
    sections: list[DescriptionSection] = Field(default_factory=list)


class ServiceDetail(ContractModel):
    contract: ContractVersion = CONTRACT
    id: str
    name: str
    namespace: str
    short_name: str
    package: PackageRef
    kind: ServiceKind
    analysis: AnalysisInfo
    source: SourceRef
    signature: Signature
    calls: list[Call]
    calls_total: int
    callers: list[ServiceLink]
    callers_total: int
    entry_points: list[EntryPoint] = Field(default_factory=list)
    entry_points_total: int = 0
    effects: list[Effect] = Field(default_factory=list)
    # Effects the facts left out beyond their own limit, plus any capped here.
    effects_hidden: int = 0
    documents: list[DocumentUse] = Field(default_factory=list)
    adapter: AdapterInfo | None = None
    description: Description | None = None


# --- packages/<id>.json and overview.json ----------------------------------------------------


class PackageService(ContractModel):
    id: str
    name: str
    kind: ServiceKind
    analysis: AnalysisLevel
    description: DescriptionState


class PackageEntryPoint(ContractModel):
    """A service that work reaches from outside its package, and from where."""

    service: PathStep
    reached_from: list[list[Segment]]


class PackageEffect(ContractModel):
    """Data or a system the package's own services touch (not through other packages)."""

    action: str
    object: list[Segment]
    where: list[Segment]
    known_from: list[str]
    services: list[PathStep]
    services_total: int


class PackageLink(ContractModel):
    name: str
    id: str | None = None
    calls: int


class PackageDetail(ContractModel):
    contract: ContractVersion = CONTRACT
    id: str
    name: str
    document_types: int
    services: list[PackageService]
    services_total: int
    entry_points: list[PackageEntryPoint]
    entry_points_total: int
    effects: list[PackageEffect]
    effects_total: int
    # Calls between packages: how many service-to-service dependencies cross over.
    calls_into: list[PackageLink]
    called_from: list[PackageLink]
    overview: Description | None = None


class SkippedPackage(ContractModel):
    name: str
    reason: str


class ServerOverview(ContractModel):
    contract: ContractVersion = CONTRACT
    description: Description | None = None
    skipped_packages: list[SkippedPackage] = Field(default_factory=list)


# --- graph.json -------------------------------------------------------------------------------
# Every call the tool established, as one table, loaded once by the graph view. Node indexes:
# 0..S-1 are `services` (IDs, in search.json order), S.. are `targets`. Python owns every edge;
# the app only walks them within limits.


class GraphTarget(ContractModel):
    """A call target that is not an analysed service."""

    name: str
    status: CallStatus
    # Platform description or external system name.
    note: str | None = None


# [from node, to node, relation, number of call sites]
GraphEdge = tuple[int, int, Relation, int]


class GraphData(ContractModel):
    contract: ContractVersion = CONTRACT
    services: list[str]
    targets: list[GraphTarget]
    edges: list[GraphEdge]


def contract_schema() -> dict[str, Any]:
    """JSON Schema of every explorer file, generated from the models above."""
    _, schema = models_json_schema(
        [
            (Manifest, "serialization"),
            (SearchIndex, "serialization"),
            (ServiceDetail, "serialization"),
            (GraphData, "serialization"),
            (PackageDetail, "serialization"),
            (ServerOverview, "serialization"),
        ],
        by_alias=True,
        title="WmDocGen explorer data contract wm-doc-explorer.v1",
    )
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    return schema


SCHEMA_PATH = "docs/contracts/explorer.v1.schema.json"


def render_contract_schema() -> str:
    import json

    return json.dumps(contract_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    # Regenerate the committed schema: `uv run python -m wm_doc.explorer.contract`
    from pathlib import Path

    Path(SCHEMA_PATH).write_text(render_contract_schema(), encoding="utf-8", newline="\n")
