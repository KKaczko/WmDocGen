"""Project an analysis and its facts into the explorer data contract.

Pure: no file access. One pass over the services. Everything the app shows comes from facts
the tool already established; nothing here resolves names or infers anything new.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from wm_doc import __version__
from wm_doc.adapters import SERVICE_TYPE as ADAPTER_SERVICE_TYPE
from wm_doc.builtins import builtin_effect
from wm_doc.call_targets import (
    JAVA_TARGET_FINDING_CODES,
    TargetStatus,
    classify_finding,
    classify_java_invocation,
    classify_target,
    placeholder_target,
)
from wm_doc.effects import DataEffect, ServiceFacts
from wm_doc.explorer.contract import (
    AdapterInfo,
    AnalysisInfo,
    AnalysisLevel,
    Call,
    Counts,
    Dataset,
    DatasetKind,
    Description,
    DescriptionSection,
    DescriptionsShown,
    DescriptionState,
    Disclosure,
    DocumentRef,
    DocumentUse,
    Effect,
    EntryPoint,
    Finding,
    Generator,
    Manifest,
    PackageRef,
    PathStep,
    Relation,
    SearchIndex,
    SearchPackage,
    SearchService,
    ServiceDetail,
    ServiceKind,
    ServiceLink,
    Severity,
    Signature,
    SignatureField,
    SourceRef,
)
from wm_doc.explorer.ids import IdRegistry, package_id, service_id
from wm_doc.explorer.text import TextGuard, narrative_blocks
from wm_doc.external_systems import EMPTY_CATALOG, ExternalSystemCatalog, system_label
from wm_doc.ir import (
    AdapterDetails,
    AdapterRole,
    AnalysisFinding,
    AnalysisResult,
    DependencyKind,
    FindingSeverity,
    FindingStatus,
    FlowService,
    ServiceAnalysisStatus,
    ServiceDocumentUsageRole,
    ServiceType,
    SignatureOrigin,
    SourceReference,
)
from wm_doc.ir import SignatureField as IrSignatureField
from wm_doc.service_docs import DETAIL_KEY, DocState, ServiceDoc

MAX_LIST_ITEMS = 500
MAX_FINDINGS = 100
MAX_EVIDENCE = 3
MAX_SIGNATURE_FIELDS = 300
MAX_SIGNATURE_DEPTH = 6
MAX_UNVERIFIED_NAMES = 50
# In an effect known from a literal, a code span not preceded by "from " is the literal value
# itself (see effects._input_values); mapped pipeline paths read "from `path`".
_LITERAL_SPAN_RE = re.compile(r"(?<!from )`[^`]*`")
LITERAL_PLACEHOLDER = "(literal, not exported)"
_ROLE: dict[ServiceDocumentUsageRole, Literal["input", "output", "input-output"]] = {
    ServiceDocumentUsageRole.INPUT: "input",
    ServiceDocumentUsageRole.OUTPUT: "output",
    ServiceDocumentUsageRole.INPUT_OUTPUT: "input-output",
}
ShownState = Literal["approved", "stale", "draft", "edited"]

_ANALYSIS: dict[ServiceAnalysisStatus, AnalysisLevel] = {
    ServiceAnalysisStatus.FULL: "full",
    ServiceAnalysisStatus.PARTIAL: "partial",
    ServiceAnalysisStatus.OPAQUE: "opaque",
}
_RELATION: dict[DependencyKind, Relation] = {
    DependencyKind.INVOKES: "invokes",
    DependencyKind.USES_TRANSFORMER: "transformer",
}
_STATE: dict[DocState, DescriptionState] = {
    DocState.APPROVED: "approved",
    DocState.STALE: "stale",
    DocState.DRAFT: "draft",
    DocState.EDITED: "edited",
    DocState.MISSING: "none",
}
_SHOWN: dict[DescriptionsShown, frozenset[DescriptionState]] = {
    "approved": frozenset({"approved", "stale"}),
    "all": frozenset({"approved", "stale", "draft", "edited"}),
    "none": frozenset(),
}


@dataclass(frozen=True)
class ExplorerOptions:
    dataset_kind: DatasetKind = "private"
    dataset_label: str | None = None
    descriptions: DescriptionsShown = "approved"


@dataclass(frozen=True)
class ExplorerInputs:
    """What `build_bundle` reads; the CLI computes the description states like `status`."""

    analysis: AnalysisResult
    facts: Mapping[str, ServiceFacts]
    service_docs: Mapping[str, ServiceDoc] = field(default_factory=dict)
    service_states: Mapping[str, DocState] = field(default_factory=dict)
    overview_docs: Mapping[str, ServiceDoc] = field(default_factory=dict)
    overview_states: Mapping[str, DocState] = field(default_factory=dict)
    external_systems: ExternalSystemCatalog = EMPTY_CATALOG


@dataclass(frozen=True)
class ExplorerBundle:
    manifest: Manifest  # digest is filled in by the writer
    search: SearchIndex
    services: dict[str, ServiceDetail]


def service_kind(service: FlowService) -> ServiceKind:
    if service.service_type is ServiceType.FLOW:
        return "flow"
    if service.service_type is ServiceType.JAVA:
        return "java"
    if service.adapter is not None or service.source_service_type == ADAPTER_SERVICE_TYPE:
        return "adapter"
    return "opaque"


def build_bundle(inputs: ExplorerInputs, options: ExplorerOptions) -> ExplorerBundle:
    analysis = inputs.analysis
    guard = TextGuard()
    registry = IdRegistry()
    services = [service for package in analysis.packages for service in package.services]
    ids: dict[str, list[tuple[str, FlowService]]] = defaultdict(list)
    for service in services:
        name = service.identity.full_name
        identifier = registry.claim(
            service_id(service.identity.package, name), f"{service.identity.package}:{name}"
        )
        ids[name].append((identifier, service))
    package_ids = {
        package.name: registry.claim(package_id(package.name), f"package {package.name}")
        for package in analysis.packages
    }
    document_names = {
        document.identity.full_name
        for package in analysis.packages
        for document in package.document_types
    }
    shown = _SHOWN[options.descriptions]
    # Only a name that belongs to exactly one analysed service is linked.
    refs = {name: entries[0][0] for name, entries in ids.items() if len(entries) == 1}
    connections = {
        artifact.full_name: artifact.adapter
        for artifact in analysis.namespace_artifacts
        if artifact.adapter is not None and artifact.adapter.role is AdapterRole.CONNECTION
    }

    def description_state(name: str) -> DescriptionState:
        state = _STATE[inputs.service_states.get(name, DocState.MISSING)]
        return state if state in shown else "none"

    details: dict[str, ServiceDetail] = {}
    search_services: list[SearchService] = []
    call_count = 0
    for service in sorted(services, key=_service_key):
        name = service.identity.full_name
        identifier = service_id(service.identity.package, name)
        state = description_state(name)
        doc = inputs.service_docs.get(name)
        purpose = None
        if doc is not None and state != "none":
            purpose = guard.free_text((doc.purpose_line() or "").replace("`", ""), 400)
        search_services.append(
            SearchService(
                id=identifier,
                name=guard.name(name),
                package=guard.name(service.identity.package),
                kind=service_kind(service),
                analysis=_ANALYSIS[service.analysis_status],
                description=state,
                purpose=purpose,
            )
        )
        calls = _calls(service, ids, inputs.external_systems, guard)
        call_count += len(calls)
        facts = inputs.facts.get(name)
        callers = sorted(
            (
                ServiceLink(id=caller_id, name=guard.name(caller))
                for caller in (facts.callers if facts is not None else ())
                for caller_id, _ in ids.get(caller, [])
            ),
            key=lambda link: (link.name.casefold(), link.name, link.id),
        )
        signature_budget = _Budget(MAX_SIGNATURE_FIELDS)
        entry_points = list(facts.entry_points) if facts is not None else []
        effects = list(facts.effects) if facts is not None else []
        hidden_effects = facts.hidden_effects if facts is not None else 0
        details[identifier] = ServiceDetail(
            id=identifier,
            name=guard.name(name),
            namespace=guard.name(service.identity.namespace),
            short_name=guard.name(service.identity.name),
            package=PackageRef(
                id=package_ids[service.identity.package],
                name=guard.name(service.identity.package),
            ),
            kind=service_kind(service),
            analysis=AnalysisInfo(
                status=_ANALYSIS[service.analysis_status],
                disabled_steps=service.disabled_steps,
                findings=[_finding(item, guard) for item in _sorted_findings(service.findings)][
                    :MAX_FINDINGS
                ],
                findings_total=len(service.findings),
            ),
            source=_source(service.source, guard),
            signature=Signature(
                origin=(
                    "specification"
                    if service.signature_origin is SignatureOrigin.SPECIFICATION
                    else "service"
                ),
                specification=(
                    guard.name(service.specification) if service.specification else None
                ),
                inputs=_fields(service.signature.inputs, document_names, guard, signature_budget),
                outputs=_fields(service.signature.outputs, document_names, guard, signature_budget),
                truncated=signature_budget.exhausted,
            ),
            calls=calls[:MAX_LIST_ITEMS],
            calls_total=len(calls),
            callers=callers[:MAX_LIST_ITEMS],
            callers_total=len(callers),
            entry_points=[
                EntryPoint(
                    kind=guard.name(entry.kind),
                    name=guard.segments(entry.name, refs, prose=False, limit=600),
                    path=_path(entry.path, refs, guard),
                )
                for entry in entry_points[:MAX_LIST_ITEMS]
            ],
            entry_points_total=len(entry_points),
            effects=[_effect(item, refs, guard) for item in effects[:MAX_LIST_ITEMS]],
            effects_hidden=hidden_effects + max(0, len(effects) - MAX_LIST_ITEMS),
            documents=_documents(service, guard),
            adapter=_adapter(service.adapter, connections, guard),
            description=(
                _description(doc, state, refs, guard)
                if doc is not None and state != "none"
                else None
            ),
        )

    search_packages = []
    for package in sorted(analysis.packages, key=lambda item: (item.name.casefold(), item.name)):
        overview_state = _STATE[
            inputs.overview_states.get(f"package:{package.name}", DocState.MISSING)
        ]
        overview_state = overview_state if overview_state in shown else "none"
        overview = inputs.overview_docs.get(package.name)
        search_packages.append(
            SearchPackage(
                id=package_ids[package.name],
                name=guard.name(package.name),
                services=len(package.services),
                overview=overview_state,
                purpose=(
                    guard.free_text(overview.purpose_line(), 400)
                    if overview is not None and overview_state != "none"
                    else None
                ),
            )
        )

    approved = sum(1 for item in search_services if item.description == "approved")
    manifest = Manifest(
        generator=Generator(
            tool="wm-doc", version=__version__, analysis_schema=analysis.schema_version
        ),
        dataset=Dataset(
            kind=options.dataset_kind,
            label=guard.free_text(options.dataset_label, 120)
            or ("Synthetic demo data" if options.dataset_kind == "synthetic" else "Internal data"),
        ),
        disclosure=Disclosure(descriptions=options.descriptions, withheld_strings=0),
        counts=Counts(
            packages=len(analysis.packages),
            services=len(services),
            document_types=len(document_names),
            calls=call_count,
            approved_descriptions=approved,
        ),
    )
    manifest = manifest.model_copy(
        update={
            "disclosure": manifest.disclosure.model_copy(
                update={"withheld_strings": guard.withheld}
            )
        }
    )
    return ExplorerBundle(
        manifest=manifest,
        search=SearchIndex(services=search_services, packages=search_packages),
        services=details,
    )


def _path(names: Iterable[str], refs: Mapping[str, str], guard: TextGuard) -> list[PathStep]:
    return [PathStep(name=guard.name(name), id=refs.get(name)) for name in names]


def _effect(effect: DataEffect, refs: Mapping[str, str], guard: TextGuard) -> Effect:
    target, where = effect.object, effect.where
    if "literal" in effect.known_from:
        target = _LITERAL_SPAN_RE.sub(LITERAL_PLACEHOLDER, target)
        where = _LITERAL_SPAN_RE.sub(LITERAL_PLACEHOLDER, where)
    return Effect(
        action=guard.name(effect.action.replace("`", "")),
        object=guard.segments(target, refs, prose=False, limit=600),
        where=guard.segments(where, refs, prose=False, limit=600),
        known_from=guard.name(effect.known_from),
        via=_path(effect.via, refs, guard),
    )


def _documents(service: FlowService, guard: TextGuard) -> list[DocumentUse]:
    seen: dict[tuple[str, str], DocumentUse] = {}
    for dependency in service.service_document_dependencies:
        role = _ROLE[dependency.usage_role]
        name = guard.name(dependency.target_document)
        seen.setdefault(
            (name, role), DocumentUse(name=name, role=role, resolved=dependency.resolved)
        )
    order = {"input": 0, "input-output": 1, "output": 2}
    return sorted(
        seen.values(), key=lambda item: (order[item.role], item.name.casefold(), item.name)
    )[:MAX_LIST_ITEMS]


def _adapter(
    details: AdapterDetails | None,
    connections: Mapping[str, AdapterDetails],
    guard: TextGuard,
) -> AdapterInfo | None:
    if details is None:
        return None
    connection = connections.get(details.connection or "")

    def clean(value: str | None) -> str | None:
        return guard.name(value) if value else None

    return AdapterInfo(
        adapter_type=clean(details.adapter_type),
        operation=clean(details.operation),
        template=clean(details.template),
        connection=clean(details.connection),
        tables=[guard.name(table) for table in details.tables][:MAX_LIST_ITEMS],
        database_product=clean(connection.database_product) if connection else None,
        database_name=clean(connection.database_name) if connection else None,
        transaction_type=clean(connection.transaction_type) if connection else None,
    )


def _description(
    doc: ServiceDoc, state: ShownState, refs: Mapping[str, str], guard: TextGuard
) -> Description:
    detail = doc.extra_front_matter.get(DETAIL_KEY)
    return Description(
        state=state,
        model=guard.name(doc.model)[:120],
        detail=guard.name(detail)[:40] if isinstance(detail, str) else None,
        unverified_names=[guard.name(name) for name in doc.unverified_names][
            :MAX_UNVERIFIED_NAMES
        ],
        sections=[
            DescriptionSection(
                key=key,
                paragraphs=[guard.segments(text, refs, prose=True) for text in paragraphs],
                items=[guard.segments(text, refs, prose=True) for text in items],
            )
            for key, paragraphs, items in narrative_blocks(doc.narrative)
        ],
    )


def _calls(
    service: FlowService,
    ids: Mapping[str, list[tuple[str, FlowService]]],
    external_systems: ExternalSystemCatalog,
    guard: TextGuard,
) -> list[Call]:
    first_order = {occurrence.id: occurrence.order for occurrence in service.call_occurrences}
    calls: list[Call] = []
    for dependency in service.unique_dependencies:
        target = dependency.target_service
        status = classify_target(target, dependency.resolved)
        targets = ids.get(target, []) if status is TargetStatus.RESOLVED else []
        target_service = targets[0][1] if len(targets) == 1 else None
        orders = [first_order[item] for item in dependency.occurrence_ids if item in first_order]
        calls.append(
            Call(
                target=guard.name(target),
                target_id=targets[0][0] if len(targets) == 1 else None,
                status=status.value,
                target_kind=service_kind(target_service) if target_service else None,
                target_analysis=(
                    _ANALYSIS[target_service.analysis_status] if target_service else None
                ),
                relation=_RELATION[dependency.dependency_kind],
                count=dependency.occurrence_count,
                first_order=min(orders) if orders else None,
                note=_note(target, status, external_systems, guard),
                evidence=[_source(item, guard) for item in dependency.source_samples][
                    :MAX_EVIDENCE
                ],
            )
        )
    java_invocations = service.java_analysis is not None
    for finding in service.findings:
        boundary = classify_finding(finding)
        if boundary is None or (java_invocations and finding.code in JAVA_TARGET_FINDING_CODES):
            continue
        calls.append(
            Call(
                target=placeholder_target(boundary),
                status=boundary.value,
                relation="call-like",
                count=finding.occurrence_count,
                note=guard.free_text(finding.code, 120),
                evidence=[
                    _source(item, guard)
                    for item in [finding.source, *finding.sample_source_references]
                ][:MAX_EVIDENCE],
            )
        )
    if service.java_analysis is not None:
        for invocation in service.java_analysis.invocation_occurrences:
            boundary = classify_java_invocation(invocation)
            if boundary is None:
                continue
            calls.append(
                Call(
                    target=placeholder_target(boundary),
                    status=boundary.value,
                    relation="java-invoke",
                    count=1,
                    note=guard.free_text(invocation.api_form, 120),
                    evidence=[_source(invocation.source.primary, guard)],
                )
            )
    calls.sort(
        key=lambda call: (
            call.first_order is None,
            call.first_order or 0,
            call.target.casefold(),
            call.target,
            call.relation,
            call.status,
        )
    )
    return calls


def _note(
    target: str,
    status: TargetStatus,
    external_systems: ExternalSystemCatalog,
    guard: TextGuard,
) -> str | None:
    if status is TargetStatus.PLATFORM:
        effect = builtin_effect(target)
        return guard.free_text(effect.label, 200) if effect is not None else None
    if status is TargetStatus.OUTSIDE:
        system = external_systems.match(target)
        return guard.free_text(system_label(system), 200) if system is not None else None
    return None


class _Budget:
    def __init__(self, limit: int) -> None:
        self.left = limit
        self.exhausted = False

    def take(self) -> bool:
        if self.left <= 0:
            self.exhausted = True
            return False
        self.left -= 1
        return True


def _fields(
    fields: Iterable[IrSignatureField],
    documents: set[str],
    guard: TextGuard,
    budget: _Budget,
    depth: int = 0,
) -> list[SignatureField]:
    result: list[SignatureField] = []
    for item in fields:
        if not budget.take():
            break
        children: list[SignatureField] = []
        if item.children:
            if depth + 1 < MAX_SIGNATURE_DEPTH:
                children = _fields(item.children, documents, guard, budget, depth + 1)
            else:
                budget.exhausted = True
        result.append(
            SignatureField(
                name=guard.name(item.name),
                type=guard.name(item.data_type) if item.data_type else None,
                dimension=item.dimensions or 0,
                optional=item.optional,
                document=(
                    DocumentRef(
                        name=guard.name(item.document_reference),
                        resolved=item.document_reference in documents,
                    )
                    if item.document_reference
                    else None
                ),
                children=children,
            )
        )
    return result


def _finding(finding: AnalysisFinding, guard: TextGuard) -> Finding:
    return Finding(
        code=guard.name(finding.code),
        severity=_severity(finding),
        count=finding.occurrence_count,
        message=guard.free_text(finding.message, 600) or "",
        source=_source(finding.source, guard),
    )


def _severity(finding: AnalysisFinding) -> Severity:
    if finding.severity is FindingSeverity.ERROR:
        return "error"
    if finding.severity is FindingSeverity.WARNING:
        return "warning"
    if finding.severity is FindingSeverity.INFO:
        return "info"
    unsure = finding.status in (FindingStatus.MALFORMED, FindingStatus.UNRESOLVED)
    return "warning" if unsure else "info"


def _sorted_findings(findings: Iterable[AnalysisFinding]) -> list[AnalysisFinding]:
    rank = {"error": 0, "warning": 1, "info": 2}
    return sorted(
        findings,
        key=lambda item: (rank[_severity(item)], item.code, item.source.path),
    )


def _source(source: SourceReference, guard: TextGuard) -> SourceRef:
    return SourceRef(
        path=guard.path(source.path),
        xml_path=guard.name(source.xml_path) if source.xml_path else None,
    )


def _service_key(service: FlowService) -> tuple[str, str, str]:
    name = service.identity.full_name
    return (name.casefold(), name, service.identity.package)
