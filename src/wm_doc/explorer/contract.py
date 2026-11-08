"""The explorer data contract `wm-doc-explorer.v1`.

These models describe every JSON file the explorer app reads. They are a projection of the
analysis made for a browser, not a copy of `analysis.json`: the vocabulary is lowercase and
owned here, so renaming an analysis enum never reaches the app.

Versioning: optional fields may be added within v1; removing or renaming anything is v2.
`docs/contracts/explorer.v1.schema.json` is generated from these models (`contract_schema`).
"""

from __future__ import annotations

import json
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
ConditionValues = Literal["included", "excluded"]
Certainty = Literal["observed", "derived", "possible", "unknown"]
OriginBasis = Literal[
    "flow-xml", "is-rule", "callee-signature", "service-signature", "caller-pipeline", "limit"
]
FlowStepKind = Literal[
    "sequence",
    "try",
    "catch",
    "finally",
    "branch",
    "case",
    "loop",
    "repeat",
    "map",
    "call",
    "transformer",
    "exit",
]
CallReach = Literal["normal", "conditional", "failure-path", "unreachable"]
Feasibility = Literal["possible", "conditional", "unresolved"]


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
    # Case labels (branch condition values) in flows/: shown unless the build excludes them.
    condition_values: ConditionValues = "included"


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
    # A FLOW service with decisions, EXITs or TRY/CATCH: its conditional flow is in
    # flows/<id>.json, loaded when the reader opens it.
    flow: FlowRef | None = None


class FlowRef(ContractModel):
    decisions: int
    calls: int
    exits: int


# --- flows/<id>.json --------------------------------------------------------------------------
# The conditional flow of one FLOW service. Python derives every fact and writes every text
# (the same wording as the service pages); the app only shows them. Ids: D1 decisions, D1.c2
# cases, C3 calls, E1 EXIT steps, in the order they appear in the FLOW.


class FlowStep(ContractModel):
    """One step of the FLOW outline."""

    kind: FlowStepKind
    ref: str | None = None
    text: list[Segment]
    target_id: str | None = None  # a call to an analysed service
    never: bool = False  # the step never runs
    children: list[FlowStep] = Field(default_factory=list)


class FlowCase(ContractModel):
    id: str
    condition: list[Segment]
    calls: list[Segment]
    ends: list[Segment]
    notes: list[Segment]
    never: bool


class FlowOrigin(ContractModel):
    """One way a decision field may have got its value, as a chip: what, how sure, why."""

    text: list[Segment]
    certainty: Certainty
    basis: OriginBasis
    # The unconfirmed rules it rests on, as `flow_semantics.assumption_label` names them.
    assumptions: str | None = None
    evidence: SourceRef | None = None
    # 0 for an origin of the field; 1.. for where a copied field comes from, under `copied`.
    depth: int = 0
    copied: str | None = None


class FlowField(ContractModel):
    """Where one field a decision tests may come from."""

    path: str
    summary: list[Segment]
    origins: list[FlowOrigin]
    origins_hidden: int
    notes: list[list[Segment]]


class FlowDecision(ContractModel):
    id: str
    heading: list[Segment]
    evaluated_when: list[Segment] | None = None
    in_loop: bool
    notes: list[list[Segment]]
    cases: list[FlowCase]
    cases_hidden: int
    no_match: list[Segment] | None = None
    fields: list[FlowField]
    fields_hidden: int
    unfollowed: list[list[Segment]]


class FlowCall(ContractModel):
    id: str
    target: str
    target_id: str | None = None
    how: Literal["step", "transformer"]
    runs_when: list[Segment]
    certainty: Certainty
    assumptions: str | None = None
    reach: CallReach


class FlowScenarioRow(ContractModel):
    id: str
    conditions: list[Segment]
    calls: list[Segment]
    ends: list[Segment]
    depends_on: list[Segment]
    feasibility: Feasibility
    assumptions: str | None = None


class FlowScenarioTable(ContractModel):
    decisions: list[str]
    rows: list[FlowScenarioRow]
    # Cut short, decisions left out, outcomes ruled out (never with a literal value).
    notes: list[list[Segment]]


class FlowView(ContractModel):
    contract: ContractVersion = CONTRACT
    service_id: str
    outline: list[FlowStep]
    outline_hidden: int
    decisions: list[FlowDecision]
    decisions_hidden: int
    calls: list[FlowCall]
    calls_hidden: int
    exits: list[list[Segment]]
    exits_hidden: int
    never_run: list[list[Segment]]
    never_run_hidden: int
    scenarios: list[FlowScenarioTable]
    scenario_notes: list[list[Segment]]
    limits: list[list[Segment]]


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
            (FlowView, "serialization"),
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


def dump_json(model: BaseModel) -> bytes:
    """A contract file as written: compact JSON with sorted keys and a final newline."""
    payload = model.model_dump(mode="json", by_alias=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def render_contract_schema() -> str:
    return json.dumps(contract_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    # Regenerate the committed schema: `uv run python -m wm_doc.explorer.contract`
    from pathlib import Path

    Path(SCHEMA_PATH).write_text(render_contract_schema(), encoding="utf-8", newline="\n")
