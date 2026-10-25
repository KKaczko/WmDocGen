"""The explorer data contract `wm-doc-explorer.v1`.

These models describe every JSON file the explorer app reads. They are a projection of the
analysis made for a browser, not a copy of `analysis.v11`: the vocabulary is lowercase and
owned here, so renaming an analysis enum never reaches the app.

Versioning: optional fields may be added within v1; removing or renaming anything is v2.
`docs/contracts/explorer.v1.schema.json` is generated from these models (`contract_schema`).
"""

from __future__ import annotations

from typing import Any, Literal

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


def contract_schema() -> dict[str, Any]:
    """JSON Schema of every explorer file, generated from the models above."""
    _, schema = models_json_schema(
        [
            (Manifest, "serialization"),
            (SearchIndex, "serialization"),
            (ServiceDetail, "serialization"),
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
