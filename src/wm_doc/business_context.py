from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from wm_doc import __version__
from wm_doc.business_context_schema import (
    BusinessContext,
    BusinessContextErrorCode,
    BusinessContextEvidence,
    BusinessContextKind,
    BusinessContextStatus,
    BusinessContextStatusReason,
    BusinessEvidenceOrigin,
    BusinessEvidenceType,
    BusinessServiceGroup,
)
from wm_doc.ir import (
    AnalysisFinding,
    AnalysisResult,
    DocumentDependency,
    DocumentField,
    DocumentType,
    FlowService,
    JavaInvocationOccurrence,
    JavaInvocationTargetStatus,
    LiteralDisclosure,
    MappingEndpoint,
    ProcessDefinition,
    ProcessDependencyEdge,
    ProcessDocumentRelationship,
    ProcessEntrypoint,
    ProcessEntrypointStatus,
    ProcessServiceMembership,
    ProcessUnresolvedCall,
    ServiceDocumentDependency,
    SourceReference,
    TextDisclosure,
    TextValue,
    UniqueDependency,
)
from wm_doc.scope_analysis import (
    ScopeBoundary,
    ScopeBoundaryStatus,
    ScopeDependencyEdge,
    ScopeDocumentBoundary,
    ScopeDocumentDependencyEdge,
    ScopeProcessProjection,
    ScopeResult,
    ScopeSelectorType,
    ScopeServiceMembership,
)

CONTEXT_SCHEMA_VERSION = "business-context.v1"
CONTEXT_PROFILE = "standard"
MAX_CONTEXT_JSON_BYTES = 750 * 1024
MAX_SERVICES = 80
MAX_PRIMARY_SERVICES = 20
MAX_SUPPORTING_SERVICES = 40
MAX_DEPENDENCIES = 150
MAX_DOCUMENTS = 25
MAX_FIELDS_PER_DOCUMENT = 50
MAX_MAPPINGS = 150
MAX_BOUNDARIES = 100
MAX_EVIDENCE_RECORDS = 500
MAX_APPROVED_DESCRIPTION_CHARS = 2000
MAX_SOURCE_DESCRIPTION_CHARS = 500
MAX_FINDING_MESSAGE_CHARS = 300
MAX_SOURCE_SAMPLES = 3
MAX_STAGE_SERVICE_SAMPLES = 25

SECRET_KEY_VALUE_RE = re.compile(
    r"(?P<key_quote>['\"]?)"
    r"(?P<key>[A-Za-z0-9_.-]*(?:password|passwd|pwd|passphrase|token|api[-_]?key|"
    r"client[-_]?secret)[A-Za-z0-9_.-]*)"
    r"(?P=key_quote)\s*(?P<separator>[:=]\s*)"
    r"(?P<value>['\"]?)[^\s,|}\]]+",
    re.IGNORECASE,
)
AUTHORIZATION_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)[^\s,|}\]]+")
BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s,|}\]]+")
JDBC_RE = re.compile(r"(?i)\bjdbc:[^\s,|}\]]+")
WINDOWS_ABSOLUTE_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s|}\]]+")
POSIX_ABSOLUTE_RE = re.compile(r"(?<![\w.])/(?:Users|home|tmp|var|etc|mnt|opt)/[^\s|}\]]*")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
REDACTED = "<redacted:secret>"


@dataclass(frozen=True)
class BusinessContextInputs:
    analysis: AnalysisResult
    scope: ScopeResult
    analysis_bytes: bytes
    scope_bytes: bytes


@dataclass(frozen=True)
class BusinessContextBuild:
    context: BusinessContext
    analysis_sha256: str
    scope_sha256: str


@dataclass(frozen=True)
class _Indexes:
    services: dict[str, FlowService]
    service_counts: dict[str, int]
    dependencies: dict[str, UniqueDependency]
    java_invocations: dict[str, JavaInvocationOccurrence]
    documents: dict[str, DocumentType]
    document_counts: dict[str, int]
    document_dependencies: dict[str, DocumentDependency]
    service_document_dependencies: dict[str, ServiceDocumentDependency]
    processes: dict[str, ProcessDefinition]
    process_counts: dict[str, int]
    process_memberships: dict[str, ProcessServiceMembership]
    process_edges: dict[str, ProcessDependencyEdge]
    process_document_relationships: dict[str, ProcessDocumentRelationship]
    process_unresolved_calls: dict[str, ProcessUnresolvedCall]
    entrypoints_by_process: dict[str, list[ProcessEntrypoint]]
    incoming_dependencies: dict[str, list[UniqueDependency]]
    outgoing_dependencies: dict[str, list[UniqueDependency]]


@dataclass
class _ContextState:
    evidence: list[BusinessContextEvidence] = field(default_factory=list)
    evidence_ids: set[str] = field(default_factory=set)
    omissions: dict[str, dict[str, Any]] = field(default_factory=dict)
    status_reasons: set[str] = field(default_factory=set)
    disclosure_redaction_count: int = 0
    evidence_omitted_count: int = 0


class BusinessContextError(Exception):
    def __init__(self, code: BusinessContextErrorCode, safe_message: str) -> None:
        super().__init__(f"{code.value}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


def load_business_context_inputs(analysis_path: Path, scope_path: Path) -> BusinessContextInputs:
    analysis_bytes = _read_required_file(analysis_path, "analysis.json")
    scope_bytes = _read_required_file(scope_path, "scope.json")
    analysis_payload = _load_json_payload(analysis_bytes, "analysis.json")
    scope_payload = _load_json_payload(scope_bytes, "scope.json")
    _require_schema(
        analysis_payload,
        "analysis.json",
        expected="analysis.v8",
        code=BusinessContextErrorCode.SCHEMA_UNSUPPORTED,
    )
    _require_schema(
        scope_payload,
        "scope.json",
        expected="scope.v1",
        code=BusinessContextErrorCode.SCHEMA_UNSUPPORTED,
    )
    try:
        analysis = AnalysisResult.model_validate(analysis_payload)
    except ValidationError as exc:
        raise BusinessContextError(
            BusinessContextErrorCode.INPUT_INVALID,
            "analysis.json does not match the supported analysis.v8 structure.",
        ) from exc
    try:
        scope = ScopeResult.model_validate(scope_payload)
    except ValidationError as exc:
        raise BusinessContextError(
            BusinessContextErrorCode.INPUT_INVALID,
            "scope.json does not match the supported scope.v1 structure.",
        ) from exc
    return BusinessContextInputs(analysis, scope, analysis_bytes, scope_bytes)


def build_business_context(inputs: BusinessContextInputs) -> BusinessContextBuild:
    indexes = _build_indexes(inputs.analysis)
    _validate_scope_references(inputs.scope, indexes, inputs.analysis)
    analysis_hash = hashlib.sha256(inputs.analysis_bytes).hexdigest()
    scope_hash = hashlib.sha256(inputs.scope_bytes).hexdigest()
    builder = _BusinessContextBuilder(inputs.analysis, inputs.scope, indexes)
    context = builder.build(analysis_hash=analysis_hash, scope_hash=scope_hash)
    return BusinessContextBuild(
        context=context,
        analysis_sha256=analysis_hash,
        scope_sha256=scope_hash,
    )


def assert_business_context_text_safe(text: str) -> None:
    unsafe = _unsafe_disclosure_label(text)
    if unsafe is not None:
        raise BusinessContextError(
            BusinessContextErrorCode.OUTPUT_FAILED,
            f"Generated business context failed disclosure scan: {unsafe}.",
        )


class _BusinessContextBuilder:
    def __init__(
        self,
        analysis: AnalysisResult,
        scope: ScopeResult,
        indexes: _Indexes,
    ) -> None:
        self.analysis = analysis
        self.scope = scope
        self.indexes = indexes
        self.state = _ContextState()

    def build(self, *, analysis_hash: str, scope_hash: str) -> BusinessContext:
        context_kind = _context_kind(self.scope.selector.selector_type)
        included_services = {membership.service for membership in self.scope.service_memberships}
        process = self._selected_process()
        subject = self._subject(context_kind, process)
        approved_metadata = self._approved_metadata(context_kind, process)
        services = self._services(included_services)
        technical_stages = self._technical_stages()
        dependencies = self._dependencies()
        documents = self._documents()
        mappings = self._mappings(included_services)
        boundaries = self._boundaries()
        unknowns = self._unknowns(boundaries)
        limitations = self._limitations(boundaries)
        self._apply_scope_findings(limitations)
        self._apply_omission_limitations(limitations)
        self._apply_disclosure_limitations(limitations)
        source = {
            "analysis_schema": self.analysis.schema_version,
            "scope_schema": self.scope.schema_version,
            "analysis_sha256": analysis_hash,
            "scope_sha256": scope_hash,
            "builder_version": __version__,
            "context_profile": CONTEXT_PROFILE,
            "extraction_policy": self.analysis.extraction_policy.model_dump(mode="json"),
        }
        scope_summary = {
            "selector_type": self.scope.selector.selector_type.value,
            "selector_value": self.scope.selector.value,
            "dependency_depth": self.scope.selector.dependency_depth,
            "root_services": list(self.scope.root_services),
            "metrics": self.scope.metrics.model_dump(mode="json"),
        }
        technical_summary = {
            "full_snapshot": {
                "service_count": sum(len(package.services) for package in self.analysis.packages),
                "document_type_count": self.analysis.metrics.document_type_count,
                "unique_dependency_count": self.analysis.metrics.total_unique_dependency_count,
                "process_definition_count": self.analysis.metrics.process_definition_count,
            },
            "published_scope": {
                "service_count": len(self.scope.service_memberships),
                "dependency_count": len(self.scope.dependencies),
                "document_count": len(self.scope.document_memberships),
                "boundary_count": len(self.scope.boundaries) + len(self.scope.document_boundaries),
                "process_projection_count": len(self.scope.process_projections),
            },
            "service_groups": dict(
                sorted(Counter(service["group"] for service in services).items())
            ),
        }
        context_id = _stable_id(
            "business_context",
            context_kind.value,
            self.scope.selector.id,
            *self.scope.root_services,
        )
        status = (
            BusinessContextStatus.PARTIAL
            if _partial_status_reasons(self.state.status_reasons)
            else BusinessContextStatus.COMPLETE
        )
        return BusinessContext(
            context_id=context_id,
            context_kind=context_kind,
            status=status,
            status_reasons=sorted(self.state.status_reasons),
            source=source,
            subject=subject,
            approved_metadata=approved_metadata,
            scope_summary=scope_summary,
            technical_summary=technical_summary,
            services=services,
            technical_stages=technical_stages,
            documents=documents,
            dependencies=dependencies,
            mappings=mappings,
            boundaries=boundaries,
            unknowns=unknowns,
            limitations=limitations,
            evidence=sorted(self.state.evidence, key=lambda item: item.evidence_id),
            omissions=dict(sorted(self.state.omissions.items())),
            generation={
                "mode": "deterministic_context_builder",
                "profile": CONTEXT_PROFILE,
                "limits": _limits_payload(),
                "llm": "not_used",
                "generated_business_claims": False,
            },
        )

    def _selected_process(self) -> ProcessDefinition | None:
        if self.scope.selected_process_id is None:
            return None
        return self.indexes.processes.get(self.scope.selected_process_id)

    def _subject(
        self,
        context_kind: BusinessContextKind,
        process: ProcessDefinition | None,
    ) -> dict[str, Any]:
        subject: dict[str, Any] = {
            "context_kind": context_kind.value,
            "selector": self.scope.selector.model_dump(mode="json"),
            "root_services": list(self.scope.root_services),
        }
        if self.scope.selector.selector_type == ScopeSelectorType.SERVICE:
            subject["service"] = self.scope.root_services[0] if self.scope.root_services else None
        if process is not None:
            process_evidence = self._add_evidence(
                BusinessEvidenceType.PROCESS,
                BusinessEvidenceOrigin.APPROVED_HUMAN_METADATA,
                process.id,
                {"process_id": process.process_id, "name": process.name},
                [process.source],
            )
            subject["process"] = {
                "process_id": process.process_id,
                "name": process.name,
                "evidence_ids": _present([process_evidence]),
            }
        return subject

    def _approved_metadata(
        self,
        context_kind: BusinessContextKind,
        process: ProcessDefinition | None,
    ) -> dict[str, Any]:
        if context_kind != BusinessContextKind.PROCESS or process is None:
            return {}
        name_evidence = self._add_evidence(
            BusinessEvidenceType.APPROVED_METADATA,
            BusinessEvidenceOrigin.APPROVED_HUMAN_METADATA,
            f"{process.id}:name",
            {"field": "name", "value": process.name},
            [process.name_source],
        )
        description = self._safe_text(
            process.description,
            MAX_APPROVED_DESCRIPTION_CHARS,
            section="approved_process_description",
        )
        description_evidence = None
        if process.description_source is not None:
            description_evidence = self._add_evidence(
                BusinessEvidenceType.APPROVED_METADATA,
                BusinessEvidenceOrigin.APPROVED_HUMAN_METADATA,
                f"{process.id}:description",
                {
                    "field": "description",
                    "description_status": process.description_status.value,
                },
                [process.description_source],
            )
        if description is None:
            self.state.status_reasons.add(
                BusinessContextStatusReason.APPROVED_METADATA_MISSING.value
            )
        return {
            "process": {
                "process_id": process.process_id,
                "name": process.name,
                "description": description,
                "description_status": process.description_status.value,
                "evidence_ids": _present([name_evidence, description_evidence]),
            }
        }

    def _services(self, included_services: set[str]) -> list[dict[str, Any]]:
        raw_records = [
            self._service_record(self.indexes.services[membership.service], membership)
            for membership in self.scope.service_memberships
        ]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in sorted(raw_records, key=_service_record_key):
            grouped[record["group"]].append(record)

        selected: list[dict[str, Any]] = []
        primary = grouped.get(BusinessServiceGroup.PRIMARY.value, [])
        supporting = grouped.get(BusinessServiceGroup.SUPPORTING.value, [])
        utility = grouped.get(BusinessServiceGroup.TECHNICAL_UTILITY.value, [])
        selected.extend(
            self._take_with_omission(
                primary,
                MAX_PRIMARY_SERVICES,
                "primary_services",
                "group, minimum depth, importance, dependency counts, service name",
            )
        )
        selected.extend(
            self._take_with_omission(
                supporting,
                MAX_SUPPORTING_SERVICES,
                "supporting_services",
                "group, minimum depth, importance, dependency counts, service name",
            )
        )
        remaining = max(0, MAX_SERVICES - len(selected))
        selected.extend(
            self._take_with_omission(
                utility,
                remaining,
                "technical_utility_services",
                "group, minimum depth, importance, dependency counts, service name",
            )
        )
        if len(selected) < min(len(raw_records), MAX_SERVICES):
            already = {record["service"] for record in selected}
            extras = [record for record in raw_records if record["service"] not in already]
            selected.extend(extras[: MAX_SERVICES - len(selected)])
        if len(raw_records) > len(selected):
            self._record_omission(
                "services",
                included=len(selected),
                total=len(raw_records),
                ranking_policy="group limits then deterministic service ranking",
            )
        return sorted(selected, key=_service_record_key)

    def _service_record(self, service: FlowService, membership: Any) -> dict[str, Any]:
        group = _service_group(service, membership)
        service_evidence = self._add_evidence(
            BusinessEvidenceType.SERVICE,
            BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
            service.identity.full_name,
            {
                "service": service.identity.full_name,
                "service_type": service.service_type.value,
                "analysis_status": service.analysis_status.value,
            },
            [service.source],
        )
        membership_evidence = self._add_evidence(
            BusinessEvidenceType.SCOPE_MEMBERSHIP,
            BusinessEvidenceOrigin.DETERMINISTIC_DERIVATION,
            membership.id,
            {
                "service": membership.service,
                "minimum_depth": membership.minimum_depth,
                "inclusion_reasons": [reason.value for reason in membership.inclusion_reasons],
            },
            [],
        )
        signature_evidence = self._add_evidence(
            BusinessEvidenceType.SERVICE_SIGNATURE,
            BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
            f"{service.identity.full_name}:signature",
            {
                "inputs": len(service.signature.inputs),
                "outputs": len(service.signature.outputs),
            },
            [service.signature.source],
        )
        incoming = self.indexes.incoming_dependencies.get(service.identity.full_name, [])
        outgoing = self.indexes.outgoing_dependencies.get(service.identity.full_name, [])
        return {
            "service": service.identity.full_name,
            "package": service.identity.package,
            "namespace": service.identity.namespace,
            "name": service.identity.name,
            "service_type": service.service_type.value,
            "source_service_type": service.source_service_type,
            "analysis_status": service.analysis_status.value,
            "description_status": service.description_status.value,
            "description": self._safe_text(
                service.description,
                MAX_SOURCE_DESCRIPTION_CHARS,
                section=f"service_description:{service.identity.full_name}",
            ),
            "group": group.value,
            "classification": service.classification.model_dump(mode="json"),
            "minimum_depth": membership.minimum_depth,
            "is_root": membership.is_root,
            "inclusion_reasons": [reason.value for reason in membership.inclusion_reasons],
            "reaching_root_count": membership.reaching_root_count,
            "reaching_root_samples": list(membership.reaching_root_samples),
            "incoming_dependency_count": len(incoming),
            "outgoing_dependency_count": len(outgoing),
            "signature": {
                "input_count": len(service.signature.inputs),
                "output_count": len(service.signature.outputs),
            },
            "evidence_ids": _present(
                [service_evidence, membership_evidence, signature_evidence]
            ),
        }

    def _technical_stages(self) -> list[dict[str, Any]]:
        stages: list[dict[str, Any]] = []
        by_depth: dict[int, list[str]] = defaultdict(list)
        for membership in self.scope.service_memberships:
            by_depth[membership.minimum_depth].append(membership.service)
        for depth, services in sorted(by_depth.items()):
            ordered = sorted(services, key=str.casefold)
            evidence = self._add_evidence(
                BusinessEvidenceType.DETERMINISTIC_SUMMARY,
                BusinessEvidenceOrigin.DETERMINISTIC_DERIVATION,
                f"technical_stage:{depth}:{self.scope.selector.id}",
                {"minimum_depth": depth, "service_count": len(ordered)},
                [],
            )
            stages.append(
                {
                    "stage": depth,
                    "label": f"Technical stage {depth}",
                    "meaning": (
                        "minimum resolved dependency depth from selected roots; "
                        "not runtime order"
                    ),
                    "service_count": len(ordered),
                    "services": ordered[:MAX_STAGE_SERVICE_SAMPLES],
                    "services_omitted": max(0, len(ordered) - MAX_STAGE_SERVICE_SAMPLES),
                    "evidence_ids": _present([evidence]),
                }
            )
        return stages

    def _dependencies(self) -> list[dict[str, Any]]:
        dependencies = sorted(
            self.scope.dependencies,
            key=lambda item: (
                item.source_service.casefold(),
                item.target_service.casefold(),
                item.dependency_kind.value,
                item.id,
            ),
        )
        selected = self._take_with_omission(
            dependencies,
            MAX_DEPENDENCIES,
            "dependencies",
            "source service, target service, dependency kind, id",
        )
        records: list[dict[str, Any]] = []
        for dependency in selected:
            canonical = self.indexes.dependencies[dependency.dependency_id]
            evidence = self._add_evidence(
                BusinessEvidenceType.DEPENDENCY,
                BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
                canonical.id,
                {
                    "source_service": canonical.source_service,
                    "target_service": canonical.target_service,
                    "kind": canonical.dependency_kind.value,
                    "occurrence_count": canonical.occurrence_count,
                },
                canonical.source_samples,
            )
            records.append(
                {
                    "dependency_id": canonical.id,
                    "source_service": canonical.source_service,
                    "target_service": canonical.target_service,
                    "dependency_kind": canonical.dependency_kind.value,
                    "occurrence_count": canonical.occurrence_count,
                    "target_analysis_status": (
                        canonical.target_analysis_status.value
                        if canonical.target_analysis_status is not None
                        else None
                    ),
                    "evidence_ids": _present([evidence]),
                }
            )
        return records

    def _documents(self) -> list[dict[str, Any]]:
        memberships = sorted(
            self.scope.document_memberships,
            key=lambda item: (
                item.minimum_document_depth,
                item.document.casefold(),
                item.id,
            ),
        )
        selected = self._take_with_omission(
            memberships,
            MAX_DOCUMENTS,
            "documents",
            "direct documents, document depth, document name",
        )
        records: list[dict[str, Any]] = []
        for membership in selected:
            document = self.indexes.documents[membership.document]
            document_evidence = self._add_evidence(
                BusinessEvidenceType.DOCUMENT,
                BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
                document.id,
                {
                    "document": document.identity.full_name,
                    "field_count": _field_count(document.fields),
                },
                [document.source],
            )
            fields, omitted_fields = self._document_fields(document)
            if omitted_fields:
                self._record_omission(
                    f"document_fields:{document.identity.full_name}",
                    included=len(fields),
                    total=len(fields) + omitted_fields,
                    ranking_policy="declared order and structural path",
                )
            records.append(
                {
                    "document": document.identity.full_name,
                    "package": document.identity.package,
                    "namespace": document.identity.namespace,
                    "name": document.identity.name,
                    "direct": membership.direct,
                    "inclusion_reasons": [
                        reason.value for reason in membership.inclusion_reasons
                    ],
                    "minimum_document_depth": membership.minimum_document_depth,
                    "source_services": list(membership.source_services),
                    "source_processes": list(membership.source_processes),
                    "field_count": _field_count(document.fields),
                    "fields": fields,
                    "document_references": self._document_reference_records(document),
                    "evidence_ids": _present([document_evidence]),
                }
            )
        return records

    def _document_fields(self, document: DocumentType) -> tuple[list[dict[str, Any]], int]:
        output: list[dict[str, Any]] = []
        total = _field_count(document.fields)

        def visit(field: DocumentField) -> None:
            if len(output) >= MAX_FIELDS_PER_DOCUMENT:
                return
            evidence = self._add_evidence(
                BusinessEvidenceType.DOCUMENT_FIELD,
                BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
                field.id,
                {
                    "document": document.identity.full_name,
                    "field_path": field.field_path,
                    "field_type": field.field_type.value,
                },
                [field.source],
            )
            output.append(
                {
                    "field_id": field.id,
                    "name": field.name,
                    "field_path": field.field_path,
                    "field_type": field.field_type.value,
                    "dimension": field.dimension.value,
                    "optional": field.optional,
                    "document_reference": field.document_reference,
                    "evidence_ids": _present([evidence]),
                }
            )
            for child in sorted(
                field.children, key=lambda item: (item.declared_order, item.field_path.casefold())
            ):
                visit(child)

        for document_field in sorted(
            document.fields, key=lambda item: (item.declared_order, item.field_path.casefold())
        ):
            visit(document_field)
        return output, max(0, total - len(output))

    def _document_reference_records(self, document: DocumentType) -> list[dict[str, Any]]:
        references = [
            reference
            for reference in self.analysis.document_reference_occurrences
            if reference.owner_name == document.identity.full_name
        ]
        records: list[dict[str, Any]] = []
        for reference in sorted(references, key=lambda item: (item.source_field_path, item.id)):
            evidence = self._add_evidence(
                BusinessEvidenceType.DOCUMENT_REFERENCE,
                BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
                reference.id,
                {
                    "owner_name": reference.owner_name,
                    "source_field_path": reference.source_field_path,
                    "declared_target": reference.declared_target,
                    "resolved": reference.resolved,
                },
                [reference.source],
            )
            records.append(
                {
                    "source_field_path": reference.source_field_path,
                    "declared_target": reference.declared_target,
                    "canonical_target": reference.canonical_target,
                    "resolved": reference.resolved,
                    "evidence_ids": _present([evidence]),
                }
            )
        return records

    def _mappings(self, included_services: set[str]) -> list[dict[str, Any]]:
        operations = [
            operation
            for operation in self.analysis.mapping_operations
            if operation.service in included_services
        ]
        operations = sorted(
            operations,
            key=lambda item: (item.service.casefold(), item.order, item.id),
        )
        selected = self._take_with_omission(
            operations,
            MAX_MAPPINGS,
            "mappings",
            "service, operation order, operation id",
        )
        binding_by_id = {binding.id: binding for binding in self.analysis.transformer_bindings}
        records: list[dict[str, Any]] = []
        for operation in selected:
            operation_evidence = self._add_evidence(
                BusinessEvidenceType.MAPPING_OPERATION,
                BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
                operation.id,
                {
                    "service": operation.service,
                    "operation_type": operation.operation_type.value,
                    "structural_path": operation.structural_path,
                },
                [operation.source],
            )
            transformer_services = []
            transformer_evidence = []
            for binding_id in operation.transformer_binding_ids:
                binding = binding_by_id.get(binding_id)
                if binding is None:
                    continue
                transformer_services.append(binding.transformer_service)
                transformer_evidence.append(
                    self._add_evidence(
                        BusinessEvidenceType.TRANSFORMER_BINDING,
                        BusinessEvidenceOrigin.CANONICAL_TECHNICAL,
                        binding.id,
                        {
                            "service": binding.service,
                            "transformer_service": binding.transformer_service,
                            "direction": binding.direction.value,
                        },
                        [binding.source],
                    )
                )
            literal_assignment = bool(operation.literal and operation.literal.present)
            records.append(
                {
                    "mapping_operation_id": operation.id,
                    "service": operation.service,
                    "operation_type": operation.operation_type.value,
                    "confidence": operation.confidence.value,
                    "source_path": _endpoint_path(operation.source_endpoint),
                    "target_path": _endpoint_path(operation.target_endpoint),
                    "delete_path": _endpoint_path(operation.delete_endpoint),
                    "literal_assignment": literal_assignment,
                    "literal_disclosure": (
                        operation.literal.disclosure.value
                        if operation.literal is not None
                        else LiteralDisclosure.NOT_PRESENT.value
                    ),
                    "literal_value": "<withheld>" if literal_assignment else None,
                    "transformer_services": sorted(set(transformer_services), key=str.casefold),
                    "evidence_ids": _present([operation_evidence, *transformer_evidence]),
                }
            )
        return records

    def _boundaries(self) -> list[dict[str, Any]]:
        boundary_items: list[ScopeBoundary | ScopeDocumentBoundary] = [
            *self.scope.boundaries,
            *self.scope.document_boundaries,
        ]
        boundary_items = sorted(boundary_items, key=_boundary_key)
        selected = self._take_with_omission(
            boundary_items,
            MAX_BOUNDARIES,
            "boundaries",
            "status, source, target, id",
        )
        records: list[dict[str, Any]] = []
        for boundary in selected:
            if isinstance(boundary, ScopeBoundary):
                evidence = self._add_evidence(
                    BusinessEvidenceType.SCOPE_BOUNDARY,
                    BusinessEvidenceOrigin.LIMITATION,
                    boundary.id,
                    {
                        "source_service": boundary.source_service,
                        "target": boundary.target,
                        "status": boundary.status.value,
                        "kind": boundary.dependency_or_call_kind,
                    },
                    boundary.source_samples,
                )
                source = boundary.source_service
                target = boundary.target
                target_category = boundary.target_category
                kind = boundary.dependency_or_call_kind
                status = boundary.status.value
                occurrence_count = boundary.occurrence_count
            else:
                evidence = self._add_evidence(
                    BusinessEvidenceType.SCOPE_BOUNDARY,
                    BusinessEvidenceOrigin.LIMITATION,
                    boundary.id,
                    {
                        "source": boundary.source,
                        "target_document": boundary.target_document,
                        "status": boundary.status.value,
                    },
                    boundary.source_samples,
                )
                source = boundary.source
                target = boundary.target_document
                target_category = "document_target"
                kind = "DOCUMENT_REFERENCE"
                status = boundary.status.value
                occurrence_count = boundary.occurrence_count
            if status in _partial_boundary_statuses():
                self.state.status_reasons.add(
                    BusinessContextStatusReason.UNKNOWN_BOUNDARY.value
                )
            records.append(
                {
                    "boundary_id": boundary.id,
                    "source": source,
                    "target": target,
                    "target_category": target_category,
                    "kind": kind,
                    "status": status,
                    "occurrence_count": occurrence_count,
                    "completeness_effect": _boundary_effect(status),
                    "evidence_ids": _present([evidence]),
                }
            )
        return records

    def _unknowns(self, boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unknowns: list[dict[str, Any]] = []
        for boundary in boundaries:
            status = boundary["status"]
            if status == ScopeBoundaryStatus.EXTERNAL_BUILTIN.value:
                continue
            unknowns.append(
                {
                    "code": f"UNKNOWN_{status}",
                    "subject": boundary["source"],
                    "summary": _unknown_summary(status),
                    "evidence_ids": boundary["evidence_ids"],
                }
            )
        return sorted(unknowns, key=lambda item: (item["code"], item["subject"]))

    def _limitations(self, boundaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        limitations: list[dict[str, Any]] = []
        for boundary in boundaries:
            limitations.append(
                {
                    "code": f"LIMITATION_{boundary['status']}",
                    "summary": _limitation_summary(boundary["status"]),
                    "subject": boundary["source"],
                    "evidence_ids": boundary["evidence_ids"],
                }
            )
        return sorted(limitations, key=lambda item: (item["code"], item["subject"]))

    def _apply_scope_findings(self, limitations: list[dict[str, Any]]) -> None:
        for finding in sorted(self.scope.findings, key=_finding_key):
            finding_evidence = self._add_evidence(
                BusinessEvidenceType.FINDING,
                BusinessEvidenceOrigin.LIMITATION,
                _finding_reference_id(finding),
                {
                    "code": finding.code,
                    "status": finding.status.value,
                    "severity": finding.severity.value if finding.severity else None,
                    "message": self._sanitize_text(
                        finding.message,
                        MAX_FINDING_MESSAGE_CHARS,
                        section=f"finding:{finding.code}",
                    ),
                },
                [finding.source, *finding.sample_source_references],
            )
            limitations.append(
                {
                    "code": finding.code,
                    "summary": self._sanitize_text(
                        finding.message,
                        MAX_FINDING_MESSAGE_CHARS,
                        section=f"finding:{finding.code}",
                    ),
                    "subject": "focused publication scope",
                    "evidence_ids": _present([finding_evidence]),
                }
            )
            if finding.code in {
                "SCOPE_PROCESS_ENTRYPOINT_UNRESOLVED",
                "SCOPE_DEPTH_LIMIT_REACHED",
            }:
                self.state.status_reasons.add(BusinessContextStatusReason.PARTIAL_SCOPE.value)
            if finding.code == "SCOPE_BOUNDARY_UNRESOLVED" and self._has_partial_boundary():
                self.state.status_reasons.add(BusinessContextStatusReason.PARTIAL_SCOPE.value)

    def _has_partial_boundary(self) -> bool:
        boundaries: list[ScopeBoundary | ScopeDocumentBoundary] = [
            *self.scope.boundaries,
            *self.scope.document_boundaries,
        ]
        return any(
            boundary.status.value in _partial_boundary_statuses()
            for boundary in boundaries
        )

    def _apply_omission_limitations(self, limitations: list[dict[str, Any]]) -> None:
        if not self.state.omissions:
            return
        self.state.status_reasons.add(BusinessContextStatusReason.LIMIT_REACHED.value)
        for section, omission in sorted(self.state.omissions.items()):
            limitations.append(
                {
                    "code": BusinessContextStatusReason.LIMIT_REACHED.value,
                    "summary": f"Section {section} was truncated by deterministic limits.",
                    "subject": section,
                    "included": omission["included"],
                    "total": omission["total"],
                    "omitted": omission["omitted"],
                    "evidence_ids": [],
                }
            )

    def _apply_disclosure_limitations(self, limitations: list[dict[str, Any]]) -> None:
        if self.state.disclosure_redaction_count <= 0:
            return
        limitations.append(
            {
                "code": BusinessContextStatusReason.DISCLOSURE_REDACTED.value,
                "summary": (
                    "Some retained free text was already redacted upstream or "
                    "redacted by the context builder."
                ),
                "subject": "free-text disclosure",
                "redaction_count": self.state.disclosure_redaction_count,
                "evidence_ids": [],
            }
        )

    def _take_with_omission[T](
        self,
        items: list[T],
        limit: int,
        section: str,
        ranking_policy: str,
    ) -> list[T]:
        selected = items[: max(0, limit)]
        if len(items) > len(selected):
            self._record_omission(
                section,
                included=len(selected),
                total=len(items),
                ranking_policy=ranking_policy,
            )
        return selected

    def _record_omission(
        self,
        section: str,
        *,
        included: int,
        total: int,
        ranking_policy: str,
    ) -> None:
        if total <= included:
            return
        self.state.omissions[section] = {
            "included": included,
            "total": total,
            "omitted": total - included,
            "ranking_policy": ranking_policy,
        }

    def _safe_text(self, text: TextValue | None, limit: int, *, section: str) -> str | None:
        if text is None:
            return None
        if _text_value_is_redacted(text):
            self.state.disclosure_redaction_count += 1
            self.state.status_reasons.add(
                BusinessContextStatusReason.DISCLOSURE_REDACTED.value
            )
        value = text.value if text.value is not None else text.marker
        if value is None:
            return None
        return self._sanitize_text(value, limit, section=section)

    def _sanitize_text(self, value: str, limit: int, *, section: str) -> str:
        cleaned = CONTROL_RE.sub(" ", value)
        cleaned = " ".join(cleaned.split())
        redacted = _redact_sensitive_text(cleaned)
        if redacted != cleaned:
            self.state.disclosure_redaction_count += 1
            self.state.status_reasons.add(
                BusinessContextStatusReason.DISCLOSURE_REDACTED.value
            )
        if len(redacted) > limit:
            self._record_omission(
                f"text:{section}",
                included=limit,
                total=len(redacted),
                ranking_policy="leading characters after disclosure sanitization",
            )
            return redacted[:limit] + "..."
        return redacted

    def _add_evidence(
        self,
        evidence_type: BusinessEvidenceType,
        origin: BusinessEvidenceOrigin,
        canonical_reference_id: str | None,
        summary: dict[str, Any],
        source_samples: list[SourceReference],
    ) -> str | None:
        evidence_id = _stable_id(
            "evidence",
            evidence_type.value,
            origin.value,
            canonical_reference_id or json.dumps(summary, sort_keys=True, default=str),
        )
        if evidence_id in self.state.evidence_ids:
            return evidence_id
        if len(self.state.evidence) >= MAX_EVIDENCE_RECORDS:
            self.state.evidence_omitted_count += 1
            self._record_omission(
                "evidence",
                included=MAX_EVIDENCE_RECORDS,
                total=MAX_EVIDENCE_RECORDS + self.state.evidence_omitted_count,
                ranking_policy="first deterministic evidence references encountered",
            )
            return None
        self.state.evidence_ids.add(evidence_id)
        self.state.evidence.append(
            BusinessContextEvidence(
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                origin=origin,
                canonical_reference_id=canonical_reference_id,
                summary=_json_safe_summary(summary),
                source_samples=_bounded_sources(source_samples),
            )
        )
        return evidence_id


def _read_required_file(path: Path, label: str) -> bytes:
    if not path.exists() or path.is_dir():
        raise BusinessContextError(
            BusinessContextErrorCode.INPUT_MISSING,
            f"Required {label} input is missing.",
        )
    try:
        return path.read_bytes()
    except OSError as exc:
        raise BusinessContextError(
            BusinessContextErrorCode.INPUT_INVALID,
            f"Could not read {label}.",
        ) from exc


def _load_json_payload(raw: bytes, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BusinessContextError(
            BusinessContextErrorCode.INPUT_INVALID,
            f"{label} is not valid UTF-8 JSON.",
        ) from exc
    if not isinstance(payload, dict):
        raise BusinessContextError(
            BusinessContextErrorCode.INPUT_INVALID,
            f"{label} root must be a JSON object.",
        )
    return payload


def _require_schema(
    payload: dict[str, Any],
    label: str,
    *,
    expected: str,
    code: BusinessContextErrorCode,
) -> None:
    schema = payload.get("schema_version")
    if schema != expected:
        raise BusinessContextError(
            code,
            f"{label} uses unsupported schema {schema!r}; expected {expected}.",
        )


def _build_indexes(analysis: AnalysisResult) -> _Indexes:
    services, service_counts = _index_with_counts(
        [service for package in analysis.packages for service in package.services],
        lambda service: service.identity.full_name,
    )
    dependencies = _unique_index(analysis.unique_dependencies, lambda item: item.id, "dependency")
    java_invocations = _unique_index(
        analysis.java_invocation_occurrences,
        lambda item: item.id,
        "Java invocation occurrence",
    )
    documents, document_counts = _index_with_counts(
        analysis.document_types,
        lambda item: item.identity.full_name,
    )
    document_dependencies = _unique_index(
        analysis.document_dependencies,
        lambda item: item.id,
        "document dependency",
    )
    service_document_dependencies = _unique_index(
        analysis.service_document_dependencies,
        lambda item: item.id,
        "service document dependency",
    )
    processes, process_counts = _index_with_counts(
        analysis.processes,
        lambda item: item.process_id,
    )
    process_memberships = _unique_index(
        analysis.process_service_memberships,
        lambda item: item.id,
        "process service membership",
    )
    process_edges = _unique_index(
        analysis.process_dependency_edges,
        lambda item: item.id,
        "process dependency edge",
    )
    process_document_relationships = _unique_index(
        analysis.process_document_relationships,
        lambda item: item.id,
        "process document relationship",
    )
    process_unresolved_calls = _unique_index(
        analysis.process_unresolved_calls,
        lambda item: item.id,
        "process unresolved call",
    )
    entrypoints_by_process: dict[str, list[ProcessEntrypoint]] = defaultdict(list)
    for entrypoint in analysis.process_entrypoints:
        entrypoints_by_process[entrypoint.process_id].append(entrypoint)
    incoming: dict[str, list[UniqueDependency]] = defaultdict(list)
    outgoing: dict[str, list[UniqueDependency]] = defaultdict(list)
    for dependency in analysis.unique_dependencies:
        outgoing[dependency.source_service].append(dependency)
        incoming[dependency.target_service].append(dependency)
    return _Indexes(
        services=services,
        service_counts=service_counts,
        dependencies=dependencies,
        java_invocations=java_invocations,
        documents=documents,
        document_counts=document_counts,
        document_dependencies=document_dependencies,
        service_document_dependencies=service_document_dependencies,
        processes=processes,
        process_counts=process_counts,
        process_memberships=process_memberships,
        process_edges=process_edges,
        process_document_relationships=process_document_relationships,
        process_unresolved_calls=process_unresolved_calls,
        entrypoints_by_process={
            key: sorted(value, key=lambda item: (item.declared_target.casefold(), item.id))
            for key, value in entrypoints_by_process.items()
        },
        incoming_dependencies={
            key: sorted(value, key=_dependency_key) for key, value in incoming.items()
        },
        outgoing_dependencies={
            key: sorted(value, key=_dependency_key) for key, value in outgoing.items()
        },
    )


def _unique_index[T](items: list[T], key_fn: Callable[[T], str], label: str) -> dict[str, T]:
    output: dict[str, T] = {}
    counts: Counter[str] = Counter()
    for item in items:
        counts[key_fn(item)] += 1
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise BusinessContextError(
            BusinessContextErrorCode.REFERENCE_AMBIGUOUS,
            f"Canonical {label} identity is ambiguous: {duplicates[0]!r}.",
        )
    for item in items:
        output[key_fn(item)] = item
    return output


def _validate_scope_references(
    scope: ScopeResult,
    indexes: _Indexes,
    analysis: AnalysisResult,
) -> None:
    scope_services = {membership.service for membership in scope.service_memberships}
    scope_documents = {membership.document for membership in scope.document_memberships}
    if len(scope_services) != len(scope.service_memberships):
        _scope_mismatch("scope.json contains duplicate service membership identities.")
    if len(scope_documents) != len(scope.document_memberships):
        _scope_mismatch("scope.json contains duplicate document membership identities.")

    for service_membership in scope.service_memberships:
        service = _require_unique_reference(
            indexes.services,
            indexes.service_counts,
            service_membership.service,
            "service",
        )
        _validate_service_membership(service_membership, service)
    for root_service in scope.root_services:
        _require_unique_reference(indexes.services, indexes.service_counts, root_service, "service")
        if root_service not in scope_services:
            _scope_mismatch("scope root service is not present in scoped memberships.")
    for scope_dependency in scope.dependencies:
        dependency = _require_reference(
            indexes.dependencies,
            scope_dependency.dependency_id,
            "dependency",
        )
        _validate_scope_dependency(scope_dependency, dependency, scope_services)
    for document_membership in scope.document_memberships:
        _require_unique_reference(
            indexes.documents,
            indexes.document_counts,
            document_membership.document,
            "document",
        )
        for service_name in document_membership.source_services:
            if service_name not in scope_services:
                _scope_mismatch("scoped document membership references an outside-scope service.")
        for process_id in document_membership.source_processes:
            _require_unique_reference(
                indexes.processes,
                indexes.process_counts,
                process_id,
                "process",
            )
    for document_dependency in scope.document_dependencies:
        canonical = _require_reference(
            indexes.document_dependencies,
            document_dependency.dependency_id,
            "document dependency",
        )
        _validate_scope_document_dependency(document_dependency, canonical, scope_documents)
    for projection in scope.process_projections:
        process = _require_unique_reference(
            indexes.processes,
            indexes.process_counts,
            projection.process_id,
            "process",
        )
        _validate_process_projection(projection, process, scope, analysis, scope_services)

    known_ids = _known_reference_ids(analysis, scope)
    boundaries: list[ScopeBoundary | ScopeDocumentBoundary] = [
        *scope.boundaries,
        *scope.document_boundaries,
    ]
    for boundary in boundaries:
        for evidence_id in boundary.evidence_ids:
            if evidence_id in known_ids or evidence_id.isupper():
                continue
            raise BusinessContextError(
                BusinessContextErrorCode.REFERENCE_MISSING,
                f"Scope boundary references unknown evidence id {evidence_id!r}.",
            )
    for boundary in scope.boundaries:
        _validate_service_boundary(boundary, indexes, scope_services)
    for boundary in scope.document_boundaries:
        _validate_document_boundary(boundary, indexes, scope_services, scope_documents, scope)


def _validate_service_membership(
    membership: ScopeServiceMembership,
    service: FlowService,
) -> None:
    if membership.service_id != _stable_id("service", membership.service):
        _scope_mismatch("scoped service membership has an invalid stable service id.")
    if membership.service_type != service.service_type:
        _scope_mismatch("scoped service membership service type does not match analysis.")
    if membership.analysis_status != service.analysis_status:
        _scope_mismatch("scoped service membership analysis status does not match analysis.")


def _validate_scope_dependency(
    edge: ScopeDependencyEdge,
    dependency: UniqueDependency,
    scope_services: set[str],
) -> None:
    if not dependency.resolved:
        _scope_mismatch("scoped dependency references an unresolved canonical dependency.")
    _require_scope_value(edge.source_service, dependency.source_service, "dependency source")
    _require_scope_value(edge.target_service, dependency.target_service, "dependency target")
    _require_scope_value(edge.dependency_kind, dependency.dependency_kind, "dependency kind")
    _require_scope_value(
        edge.occurrence_count,
        dependency.occurrence_count,
        "dependency occurrence count",
    )
    if edge.source_service not in scope_services or edge.target_service not in scope_services:
        _scope_mismatch("scoped dependency endpoint is not included in service memberships.")


def _validate_scope_document_dependency(
    edge: ScopeDocumentDependencyEdge,
    dependency: DocumentDependency,
    scope_documents: set[str],
) -> None:
    if not dependency.resolved:
        _scope_mismatch("scoped document dependency references an unresolved canonical dependency.")
    _require_scope_value(
        edge.source_document,
        dependency.source_document,
        "document dependency source",
    )
    _require_scope_value(
        edge.target_document,
        dependency.target_document,
        "document dependency target",
    )
    _require_scope_value(
        edge.occurrence_count,
        dependency.occurrence_count,
        "document dependency occurrence count",
    )
    if edge.source_document not in scope_documents or edge.target_document not in scope_documents:
        _scope_mismatch(
            "scoped document dependency endpoint is not included in document memberships."
        )


def _validate_process_projection(
    projection: ScopeProcessProjection,
    process: ProcessDefinition,
    scope: ScopeResult,
    analysis: AnalysisResult,
    scope_services: set[str],
) -> None:
    if scope.selected_process_id is None:
        _scope_mismatch("scope process projection exists without a selected process.")
    if projection.process_id != scope.selected_process_id:
        _scope_mismatch("scope process projection does not match the selected process.")
    if (
        scope.selector.selector_type == ScopeSelectorType.PROCESS
        and projection.process_id != scope.selector.value
    ):
        _scope_mismatch("scope process projection does not match the process selector.")
    _require_scope_value(projection.process_name, process.name, "process projection name")
    memberships = [
        membership
        for membership in analysis.process_service_memberships
        if membership.process_id == projection.process_id
    ]
    edges = [
        edge
        for edge in analysis.process_dependency_edges
        if edge.process_id == projection.process_id
    ]
    unresolved = [
        call
        for call in analysis.process_unresolved_calls
        if call.process_id == projection.process_id
    ]
    relationships = [
        relationship
        for relationship in analysis.process_document_relationships
        if relationship.process_id == projection.process_id
    ]
    entrypoints = [
        entrypoint
        for entrypoint in analysis.process_entrypoints
        if entrypoint.process_id == projection.process_id
    ]
    published_members = {membership.service for membership in memberships} & scope_services
    published_edges = [
        edge
        for edge in edges
        if edge.source_service in published_members and edge.target_service in published_members
    ]
    published_unresolved = [
        call for call in unresolved if call.source_service in published_members
    ]
    boundary_count = sum(
        1 for boundary in scope.boundaries if boundary.source_service in published_members
    )
    expected = {
        "full_member_count": len(memberships),
        "published_member_count": len(published_members),
        "full_edge_count": len(edges),
        "published_edge_count": len(published_edges),
        "boundary_dependency_count": boundary_count,
        "full_unresolved_call_count": len(unresolved),
        "published_unresolved_call_count": len(published_unresolved),
        "full_document_relationship_count": len(relationships),
        "published_document_count": len(scope.document_memberships),
        "entrypoint_count": len(entrypoints),
        "resolved_entrypoint_count": sum(
            1
            for entrypoint in entrypoints
            if entrypoint.status == ProcessEntrypointStatus.RESOLVED
        ),
    }
    for field_name, expected_value in expected.items():
        if getattr(projection, field_name) != expected_value:
            _scope_mismatch(f"scope process projection {field_name} does not match analysis.")


def _validate_service_boundary(
    boundary: ScopeBoundary,
    indexes: _Indexes,
    scope_services: set[str],
) -> None:
    service = indexes.services.get(boundary.source_service)
    if service is None or indexes.service_counts.get(boundary.source_service, 0) != 1:
        _scope_mismatch("scope boundary source service does not resolve uniquely in analysis.")
    assert service is not None
    if boundary.source_service not in scope_services:
        _scope_mismatch("scope boundary source service is not included in service memberships.")
    if not boundary.evidence_ids:
        _scope_mismatch("scope boundary has no evidence references.")
    expected_count = 0
    for evidence_id in boundary.evidence_ids:
        if evidence_id in indexes.dependencies:
            expected_count += _validate_dependency_boundary_evidence(
                boundary,
                indexes.dependencies[evidence_id],
                scope_services,
            )
        elif evidence_id in indexes.java_invocations:
            expected_count += _validate_java_boundary_evidence(
                boundary,
                indexes.java_invocations[evidence_id],
            )
        elif evidence_id.isupper():
            expected_count += _validate_finding_boundary_evidence(boundary, service, evidence_id)
        else:
            raise BusinessContextError(
                BusinessContextErrorCode.REFERENCE_MISSING,
                f"Scope boundary references unknown evidence id {evidence_id!r}.",
            )
    if expected_count != boundary.occurrence_count:
        _scope_mismatch("scope boundary occurrence count does not match evidence.")


def _validate_dependency_boundary_evidence(
    boundary: ScopeBoundary,
    dependency: UniqueDependency,
    scope_services: set[str],
) -> int:
    _require_scope_value(boundary.source_service, dependency.source_service, "boundary source")
    _require_scope_value(boundary.target, dependency.target_service, "boundary target")
    _require_scope_value(
        boundary.dependency_or_call_kind,
        dependency.dependency_kind.value,
        "boundary dependency kind",
    )
    if dependency.resolved:
        _require_scope_value(boundary.status, ScopeBoundaryStatus.DEPTH_LIMIT, "boundary status")
        _require_scope_value(boundary.target_category, "service", "boundary target category")
        if dependency.target_service in scope_services:
            _scope_mismatch("depth-limit boundary target is already included in scope.")
    else:
        expected_status = _expected_unresolved_boundary_status(dependency.target_service)
        _require_scope_value(boundary.status, expected_status, "boundary status")
        _require_scope_value(boundary.target_category, "service_target", "boundary target category")
    return dependency.occurrence_count


def _validate_java_boundary_evidence(
    boundary: ScopeBoundary,
    invocation: JavaInvocationOccurrence,
) -> int:
    status = (
        ScopeBoundaryStatus.UNRESOLVED
        if invocation.target_status == JavaInvocationTargetStatus.MALFORMED_TARGET
        else ScopeBoundaryStatus.DYNAMIC
    )
    target = (
        invocation.canonical_target
        or invocation.declared_target
        or "<dynamic-java-target>"
    )
    _require_scope_value(boundary.source_service, invocation.caller, "Java boundary source")
    _require_scope_value(boundary.target, target, "Java boundary target")
    _require_scope_value(boundary.target_category, "java_invocation", "Java boundary category")
    _require_scope_value(boundary.dependency_or_call_kind, "JAVA_INVOKE", "Java boundary kind")
    _require_scope_value(boundary.status, status, "Java boundary status")
    return 1


def _validate_finding_boundary_evidence(
    boundary: ScopeBoundary,
    service: FlowService,
    finding_code: str,
) -> int:
    matches = [
        finding
        for finding in service.findings
        if finding.code == finding_code
        and _finding_boundary_status(finding) == boundary.status
    ]
    if not matches:
        _scope_mismatch("scope boundary finding evidence does not match analysis.")
    expected_target = _finding_boundary_target(boundary.status)
    _require_scope_value(boundary.target, expected_target, "finding boundary target")
    _require_scope_value(boundary.target_category, "finding", "finding boundary category")
    _require_scope_value(
        boundary.dependency_or_call_kind,
        "CALL_LIKE_FINDING",
        "finding boundary kind",
    )
    return sum(finding.occurrence_count for finding in matches)


def _validate_document_boundary(
    boundary: ScopeDocumentBoundary,
    indexes: _Indexes,
    scope_services: set[str],
    scope_documents: set[str],
    scope: ScopeResult,
) -> None:
    if not boundary.evidence_ids:
        _scope_mismatch("scope document boundary has no evidence references.")
    expected_count = 0
    for evidence_id in boundary.evidence_ids:
        if evidence_id in indexes.service_document_dependencies:
            service_dependency = indexes.service_document_dependencies[evidence_id]
            if service_dependency.service not in scope_services:
                _scope_mismatch("document boundary service source is outside the selected scope.")
            _require_scope_value(
                boundary.source,
                service_dependency.service,
                "document boundary source",
            )
            _require_scope_value(
                boundary.target_document,
                service_dependency.target_document,
                "document boundary target",
            )
            _require_scope_value(
                boundary.status,
                ScopeBoundaryStatus.UNRESOLVED,
                "document boundary status",
            )
            expected_count += service_dependency.occurrence_count
        elif evidence_id in indexes.document_dependencies:
            document_dependency = indexes.document_dependencies[evidence_id]
            if document_dependency.source_document not in scope_documents:
                _scope_mismatch("document boundary source document is outside the selected scope.")
            _require_unique_reference(
                indexes.documents,
                indexes.document_counts,
                document_dependency.source_document,
                "document",
            )
            _require_scope_value(
                boundary.source,
                document_dependency.source_document,
                "document boundary source",
            )
            _require_scope_value(
                boundary.target_document,
                document_dependency.target_document,
                "document boundary target",
            )
            _require_scope_value(
                boundary.status,
                ScopeBoundaryStatus.UNRESOLVED,
                "document boundary status",
            )
            expected_count += document_dependency.occurrence_count
        elif evidence_id in indexes.process_document_relationships:
            relationship = indexes.process_document_relationships[evidence_id]
            if scope.selected_process_id != relationship.process_id:
                _scope_mismatch(
                    "document boundary process relationship is outside the selected process."
                )
            source = relationship.service or relationship.source_document or relationship.process_id
            if relationship.service is not None and relationship.service not in scope_services:
                _scope_mismatch(
                    "document boundary process service source is outside the selected scope."
                )
            if relationship.source_document is not None:
                _require_unique_reference(
                    indexes.documents,
                    indexes.document_counts,
                    relationship.source_document,
                    "document",
                )
                if relationship.source_document not in scope_documents:
                    _scope_mismatch(
                        "document boundary process document source is outside the selected scope."
                    )
            _require_scope_value(boundary.source, source, "document boundary source")
            _require_scope_value(
                boundary.target_document,
                relationship.target_document,
                "document boundary target",
            )
            _require_scope_value(
                boundary.status,
                ScopeBoundaryStatus.UNRESOLVED,
                "document boundary status",
            )
            expected_count += relationship.occurrence_count
        else:
            raise BusinessContextError(
                BusinessContextErrorCode.REFERENCE_MISSING,
                f"Scope document boundary references unknown evidence id {evidence_id!r}.",
            )
    if expected_count != boundary.occurrence_count:
        _scope_mismatch("scope document boundary occurrence count does not match evidence.")


def _require_scope_value(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        _scope_mismatch(f"scope {label} does not match canonical analysis.")


def _scope_mismatch(message: str) -> None:
    raise BusinessContextError(BusinessContextErrorCode.SCOPE_MISMATCH, message)


def _expected_unresolved_boundary_status(target: str) -> ScopeBoundaryStatus:
    folded = target.casefold()
    if folded.startswith("pub.") or folded.startswith("wm."):
        return ScopeBoundaryStatus.EXTERNAL_BUILTIN
    if _valid_service_full_name(target):
        return ScopeBoundaryStatus.OUTSIDE_SNAPSHOT
    return ScopeBoundaryStatus.UNRESOLVED


def _finding_boundary_status(finding: AnalysisFinding) -> ScopeBoundaryStatus | None:
    code = finding.code.upper()
    message = finding.message.upper()
    if "DYNAMIC" in code and ("SERVICE" in code or "INVOKE" in code or "CALL" in code):
        return ScopeBoundaryStatus.DYNAMIC
    if "UNSUPPORTED" in code and ("SERVICE" in code or "INVOKE" in code or "CALL" in code):
        return ScopeBoundaryStatus.UNSUPPORTED
    if "PARTIALLY_STATIC_SERVICE_TARGET" in code:
        return ScopeBoundaryStatus.DYNAMIC
    if "DYNAMIC" in message and ("SERVICE" in message or "INVOK" in message):
        return ScopeBoundaryStatus.DYNAMIC
    return None


def _finding_boundary_target(status: ScopeBoundaryStatus) -> str:
    if status == ScopeBoundaryStatus.DYNAMIC:
        return "<dynamic-target>"
    if status == ScopeBoundaryStatus.UNSUPPORTED:
        return "<unsupported-call-like-construct>"
    return "<unresolved-target>"


def _valid_service_full_name(value: str) -> bool:
    if CONTROL_RE.search(value) or value.count(":") != 1:
        return False
    namespace, service = value.split(":", 1)
    return _valid_namespace(namespace) and _valid_name_segment(service)


def _valid_namespace(value: str) -> bool:
    if not value or CONTROL_RE.search(value):
        return False
    if any(char in value for char in "/\\:"):
        return False
    return all(_valid_name_segment(segment) for segment in value.split("."))


def _valid_name_segment(value: str) -> bool:
    return bool(value) and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value) is not None


def _require_reference[T](index: dict[str, T], key: str, label: str) -> T:
    if key not in index:
        raise BusinessContextError(
            BusinessContextErrorCode.REFERENCE_MISSING,
            f"scope.json references missing {label} {key!r}.",
        )
    return index[key]


def _require_unique_reference[T](
    index: dict[str, T],
    counts: dict[str, int],
    key: str,
    label: str,
) -> T:
    item = _require_reference(index, key, label)
    if counts.get(key, 0) > 1:
        raise BusinessContextError(
            BusinessContextErrorCode.REFERENCE_AMBIGUOUS,
            f"scope.json references ambiguous {label} {key!r}.",
        )
    return item


def _index_with_counts[T](
    items: list[T], key_fn: Callable[[T], str]
) -> tuple[dict[str, T], dict[str, int]]:
    output: dict[str, T] = {}
    counts: Counter[str] = Counter()
    for item in items:
        key = key_fn(item)
        counts[key] += 1
        output.setdefault(key, item)
    return output, dict(counts)


def _known_reference_ids(analysis: AnalysisResult, scope: ScopeResult) -> set[str]:
    ids: set[str] = set()
    ids.update(dependency.id for dependency in analysis.unique_dependencies)
    ids.update(occurrence.id for occurrence in analysis.call_occurrences)
    ids.update(occurrence.id for occurrence in analysis.java_invocation_occurrences)
    ids.update(dependency.id for dependency in analysis.service_document_dependencies)
    ids.update(dependency.id for dependency in analysis.document_dependencies)
    ids.update(reference.id for reference in analysis.document_reference_occurrences)
    ids.update(operation.id for operation in analysis.mapping_operations)
    ids.update(binding.id for binding in analysis.transformer_bindings)
    ids.update(entrypoint.id for entrypoint in analysis.process_entrypoints)
    ids.update(relationship.id for relationship in analysis.process_document_relationships)
    ids.update(boundary.id for boundary in scope.boundaries)
    ids.update(boundary.id for boundary in scope.document_boundaries)
    return ids


def _partial_status_reasons(status_reasons: set[str]) -> set[str]:
    return {
        reason
        for reason in status_reasons
        if reason != BusinessContextStatusReason.DISCLOSURE_REDACTED.value
    }


def _text_value_is_redacted(text: TextValue) -> bool:
    if text.disclosure in {TextDisclosure.REDACTED, TextDisclosure.BLOCKED_SECRET}:
        return True
    value = text.value if text.value is not None else text.marker
    return isinstance(value, str) and value.startswith("<redacted:")


def _context_kind(selector_type: ScopeSelectorType) -> BusinessContextKind:
    if selector_type == ScopeSelectorType.PROCESS:
        return BusinessContextKind.PROCESS
    if selector_type == ScopeSelectorType.SERVICE:
        return BusinessContextKind.SERVICE
    return BusinessContextKind.SCOPE_SUMMARY


def _service_group(service: FlowService, membership: Any) -> BusinessServiceGroup:
    if membership.is_root or any(
        reason.value in {"ROOT_SERVICE", "ROOT_PROCESS_ENTRYPOINT"}
        for reason in membership.inclusion_reasons
    ):
        return BusinessServiceGroup.PRIMARY
    if (
        service.classification.importance.value == "LOW"
        or service.classification.layer == "UTILITY"
    ):
        return BusinessServiceGroup.TECHNICAL_UTILITY
    return BusinessServiceGroup.SUPPORTING


def _service_record_key(record: dict[str, Any]) -> tuple[int, int, int, int, str]:
    group_order = {
        BusinessServiceGroup.PRIMARY.value: 0,
        BusinessServiceGroup.SUPPORTING.value: 1,
        BusinessServiceGroup.TECHNICAL_UTILITY.value: 2,
        BusinessServiceGroup.BOUNDARY.value: 3,
    }
    importance_order = {"IMPORTANT": 0, "NORMAL": 1, "LOW": 2}
    classification = record.get("classification") or {}
    return (
        group_order.get(str(record.get("group")), 9),
        int(record.get("minimum_depth", 0)),
        importance_order.get(str(classification.get("importance")), 9),
        -int(record.get("outgoing_dependency_count", 0)),
        str(record.get("service", "")).casefold(),
    )


def _dependency_key(dependency: UniqueDependency) -> tuple[str, str, str, str]:
    return (
        dependency.source_service.casefold(),
        dependency.target_service.casefold(),
        dependency.dependency_kind.value,
        dependency.id,
    )


def _boundary_key(boundary: ScopeBoundary | ScopeDocumentBoundary) -> tuple[str, str, str, str]:
    if isinstance(boundary, ScopeBoundary):
        return (
            boundary.status.value,
            boundary.source_service.casefold(),
            boundary.target.casefold(),
            boundary.id,
        )
    return (
        boundary.status.value,
        boundary.source.casefold(),
        boundary.target_document.casefold(),
        boundary.id,
    )


def _finding_key(finding: AnalysisFinding) -> tuple[str, str, str]:
    return (finding.source.path.casefold(), finding.code, finding.message)


def _finding_reference_id(finding: AnalysisFinding) -> str:
    return _stable_id("finding", finding.code, finding.source.path, finding.message)


def _endpoint_path(endpoint: MappingEndpoint | None) -> str | None:
    if endpoint is None:
        return None
    return endpoint.raw_path


def _field_count(fields: list[DocumentField]) -> int:
    return sum(1 + _field_count(field.children) for field in fields)


def _partial_boundary_statuses() -> set[str]:
    return {
        ScopeBoundaryStatus.DEPTH_LIMIT.value,
        ScopeBoundaryStatus.OUTSIDE_SNAPSHOT.value,
        ScopeBoundaryStatus.UNRESOLVED.value,
        ScopeBoundaryStatus.DYNAMIC.value,
        ScopeBoundaryStatus.UNSUPPORTED.value,
    }


def _boundary_effect(status: str) -> str:
    if status == ScopeBoundaryStatus.DEPTH_LIMIT.value:
        return "publication depth stopped traversal beyond this dependency"
    if status == ScopeBoundaryStatus.EXTERNAL_BUILTIN.value:
        return "target is a known built-in or platform namespace outside local documentation"
    if status == ScopeBoundaryStatus.OUTSIDE_SNAPSHOT.value:
        return "target service is outside the analyzed snapshot"
    if status == ScopeBoundaryStatus.DYNAMIC.value:
        return "target cannot be determined statically"
    if status == ScopeBoundaryStatus.UNSUPPORTED.value:
        return "call-like construct is not interpreted by the current analyzer"
    return "target could not be resolved from available static evidence"


def _unknown_summary(status: str) -> str:
    if status == ScopeBoundaryStatus.DEPTH_LIMIT.value:
        return "Additional reachable services may exist beyond the selected publication depth."
    if status == ScopeBoundaryStatus.OUTSIDE_SNAPSHOT.value:
        return "A statically named target was not present in the analyzed snapshot."
    if status == ScopeBoundaryStatus.DYNAMIC.value:
        return "A dynamic invocation target cannot be determined statically."
    if status == ScopeBoundaryStatus.UNSUPPORTED.value:
        return "A call-like construct could not be interpreted by the current analyzer."
    return "A referenced target could not be resolved from available static evidence."


def _limitation_summary(status: str) -> str:
    if status == ScopeBoundaryStatus.EXTERNAL_BUILTIN.value:
        return "Built-in platform services are not expanded into business context."
    return _unknown_summary(status)


def _limits_payload() -> dict[str, int]:
    return {
        "max_context_json_bytes": MAX_CONTEXT_JSON_BYTES,
        "max_services": MAX_SERVICES,
        "max_primary_services": MAX_PRIMARY_SERVICES,
        "max_supporting_services": MAX_SUPPORTING_SERVICES,
        "max_dependencies": MAX_DEPENDENCIES,
        "max_documents": MAX_DOCUMENTS,
        "max_fields_per_document": MAX_FIELDS_PER_DOCUMENT,
        "max_mappings": MAX_MAPPINGS,
        "max_boundaries": MAX_BOUNDARIES,
        "max_evidence_records": MAX_EVIDENCE_RECORDS,
        "max_approved_description_chars": MAX_APPROVED_DESCRIPTION_CHARS,
        "max_source_description_chars": MAX_SOURCE_DESCRIPTION_CHARS,
        "max_finding_message_chars": MAX_FINDING_MESSAGE_CHARS,
        "max_source_samples": MAX_SOURCE_SAMPLES,
    }


def _bounded_sources(sources: list[SourceReference]) -> list[SourceReference]:
    seen: set[tuple[str, str | None, str | None, int | None]] = set()
    output: list[SourceReference] = []
    for source in sources:
        key = (
            source.path,
            source.artifact_type,
            source.source_node or source.xml_path,
            source.line,
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(source)
        if len(output) >= MAX_SOURCE_SAMPLES:
            break
    return output


def _present(values: list[str | None]) -> list[str]:
    return [value for value in values if value is not None]


def _json_safe_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(summary, sort_keys=True, default=str))


def _redact_sensitive_text(value: str) -> str:
    cleaned = SECRET_KEY_VALUE_RE.sub(
        lambda match: (
            f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}"
            f"{match.group('separator')}{REDACTED}"
        ),
        value,
    )
    cleaned = JDBC_RE.sub("<redacted:connection-string>", cleaned)
    cleaned = AUTHORIZATION_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", cleaned)
    cleaned = BEARER_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", cleaned)
    cleaned = WINDOWS_ABSOLUTE_RE.sub("<redacted:absolute-path>", cleaned)
    cleaned = POSIX_ABSOLUTE_RE.sub("<redacted:absolute-path>", cleaned)
    return cleaned


def _unsafe_disclosure_label(text: str) -> str | None:
    if SECRET_KEY_VALUE_RE.search(text):
        return "secret-like key/value"
    if AUTHORIZATION_RE.search(text) or BEARER_RE.search(text):
        return "authorization header or bearer value"
    if JDBC_RE.search(text):
        return "connection string"
    if WINDOWS_ABSOLUTE_RE.search(text) or POSIX_ABSOLUTE_RE.search(text):
        return "absolute path"
    if "Traceback (most recent call last)" in text:
        return "traceback"
    return None


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
