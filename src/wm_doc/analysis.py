from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from lxml import etree

from wm_doc import __version__
from wm_doc.config import AppConfig, ExtractionMode, classify_service
from wm_doc.discovery import scan_path
from wm_doc.ir import (
    AnalysisFinding,
    AnalysisMetrics,
    AnalysisResult,
    AnalyzedPackage,
    ArtifactCandidate,
    AttributeClassification,
    AttributeValue,
    CallOccurrence,
    CallType,
    ClassificationResult,
    DependencyKind,
    DocumentDependency,
    DocumentDependencyKind,
    DocumentDimensionKind,
    DocumentField,
    DocumentFieldType,
    DocumentIdentity,
    DocumentReferenceOccurrence,
    DocumentReferenceOwnerKind,
    DocumentType,
    ExtractionPolicySnapshot,
    FactBasis,
    FindingSeverity,
    FindingStatus,
    FlowMap,
    FlowNode,
    FlowNodeType,
    FlowService,
    InterpretationConfidence,
    JavaImport,
    JavaInvocationOccurrence,
    JavaInvocationTargetStatus,
    JavaPipelineAccess,
    JavaServiceAnalysis,
    JavaSourceStatus,
    JavaTypeReference,
    LiteralDisclosure,
    LiteralValue,
    MappingEndpoint,
    MappingOperation,
    MappingOperationType,
    MapSchemaMetadata,
    PackageInventory,
    PipelinePath,
    ProcessDefinition,
    ProcessDependencyEdge,
    ProcessDescriptionStatus,
    ProcessDocumentRelationship,
    ProcessEntrypoint,
    ProcessEntrypointStatus,
    ProcessServiceMembership,
    ProcessUnresolvedCall,
    ServiceAnalysisStatus,
    ServiceDescriptionStatus,
    ServiceDocumentDependency,
    ServiceDocumentUsageRole,
    ServiceIdentity,
    ServiceSignature,
    ServiceSummary,
    ServiceType,
    SignatureField,
    SourceReference,
    TechnicalEntrypointCandidate,
    TextDisclosure,
    TextValue,
    TransformerBinding,
    TransformerBindingDirection,
    UniqueDependency,
    stable_relative_path,
)
from wm_doc.java_analysis import analyze_java_service
from wm_doc.process_analysis import build_process_analysis
from wm_doc.process_catalog import ParsedProcessCatalog, load_process_catalog
from wm_doc.values import parse_values_file, scalar_value
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file

ANALYZABLE_FLOW_ARTIFACTS = {"flow_service", "flow_service_metadata_without_flow"}
SERVICE_INDEX_ARTIFACTS = {
    "flow_service",
    "flow_service_metadata_without_flow",
    "java_service",
    "opaque_service",
}
DOCUMENT_ARTIFACTS = {"document_type"}
CALL_TAGS = {"INVOKE": CallType.INVOKE, "MAPINVOKE": CallType.MAPINVOKE}
FLOW_NODE_TAGS = {
    "FLOW": FlowNodeType.FLOW,
    "SEQUENCE": FlowNodeType.SEQUENCE,
    "BRANCH": FlowNodeType.BRANCH,
    "LOOP": FlowNodeType.LOOP,
    "MAP": FlowNodeType.MAP,
    "EXIT": FlowNodeType.EXIT,
    "INVOKE": FlowNodeType.INVOKE,
    "MAPINVOKE": FlowNodeType.MAPINVOKE,
}
MAPPING_OPERATION_TAGS = {"MAPCOPY", "MAPSET", "MAPDELETE"}
MAP_METADATA_TAGS = {"MAPSOURCE", "MAPTARGET"}
MAPPING_INTERNAL_TAGS = MAPPING_OPERATION_TAGS | MAP_METADATA_TAGS | {"DATA"}
SUPPORTED_EXIT_ATTRIBUTES = {"FROM", "SIGNAL", "FAILURE-MESSAGE"}
UNRESOLVED_SOURCE_SAMPLE_LIMIT = 3
SOURCE_SAMPLE_LIMIT = 3
AGGREGATABLE_FINDINGS = {
    "AMBIGUOUS_TRANSFORMER_DIRECTION",
    "CYCLIC_DOCUMENT_REFERENCE",
    "ID_COLLISION_RESOLVED",
    "MALFORMED_NESTED_RECORD",
    "MISSING_LITERAL_DATA",
    "ORPHAN_MAPSOURCE",
    "ORPHAN_MAPTARGET",
    "PARTIAL_MAPPING_INTERPRETATION",
    "SECRET_LITERAL_REDACTED",
    "UNKNOWN_MAPPING_ATTRIBUTE",
    "UNKNOWN_MAPPING_CHILD",
    "UNSUPPORTED_LITERAL_ENCODING",
    "UNSUPPORTED_DOCUMENT_METADATA",
    "UNRESOLVED_DOCUMENT_REFERENCE",
    "DYNAMIC_PIPELINE_KEY",
    "DYNAMIC_SERVICE_TARGET",
    "JAVA_IMPORT_SOURCE_MISMATCH",
    "JAVA_SOURCE_FRAGMENT_MISMATCH",
    "JAVA_SOURCE_IDENTITY_MISMATCH",
    "JAVA_SOURCE_METHOD_AMBIGUOUS",
    "JAVA_SOURCE_METHOD_NOT_FOUND",
    "JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED",
    "JAVA_SOURCE_PARTIAL_PARSE",
    "PARTIALLY_STATIC_SERVICE_TARGET",
}
SECRET_TERMS = (
    "password",
    "secret",
    "credential",
    "private key",
    "private-key",
    "private_key",
    "privatekey",
    "passphrase",
    "token",
)
SECRET_GUARD_STRATEGY_VERSION = "secret-guard.v1"
FLOW_TECHNICAL_ATTRIBUTES: dict[str, set[str]] = {
    "FLOW": {"CLEANUP", "VERSION"},
    "SEQUENCE": {"EXIT-ON", "FORM", "TIMEOUT"},
    "BRANCH": {"LABELEXPRESSIONS", "SWITCH", "TIMEOUT"},
    "LOOP": {"IN-ARRAY", "OUT-ARRAY", "TIMEOUT"},
    "MAP": {"MODE", "TIMEOUT"},
    "INVOKE": {"INVOKE-ORDER", "SERVICE", "TIMEOUT", "VALIDATE-IN", "VALIDATE-OUT"},
    "MAPINVOKE": {"INVOKE-ORDER", "SERVICE", "TIMEOUT", "VALIDATE-IN", "VALIDATE-OUT"},
    "EXIT": SUPPORTED_EXIT_ATTRIBUTES,
}
FLOW_FREE_TEXT_ATTRIBUTES = {"NAME"}
MAPPING_TECHNICAL_ATTRIBUTES: dict[str, set[str]] = {
    "MAPCOPY": {"FROM", "TO"},
    "MAPSET": {"FIELD", "GLOBALVARIABLES", "OVERWRITE", "VARIABLES"},
    "MAPDELETE": {"FIELD"},
}
MAPPING_FREE_TEXT_ATTRIBUTES = {"NAME"}
DOCUMENT_TECHNICAL_METADATA = {
    "field_content_type",
    "field_options_count",
    "field_password",
    "field_usereditable",
    "field_largerEditor",
    "form_qualified",
    "is_global",
    "is_public",
    "is_soap_array_encoding_used",
    "modifiable",
    "nillable",
    "node_subtype",
    "node_type",
    "rec_closed",
}
DOCUMENT_FREE_TEXT_METADATA = {"node_comment"}
DOCUMENT_ROOT_KNOWN_METADATA = {
    "field_dim",
    "field_type",
    "node_comment",
    "node_hints",
    "node_nsName",
    "node_pkg",
    "rec_fields",
    "wrapper_type",
    *DOCUMENT_TECHNICAL_METADATA,
    *DOCUMENT_FREE_TEXT_METADATA,
}
DOCUMENT_FIELD_KNOWN_METADATA = {
    "field_dim",
    "field_name",
    "field_opt",
    "field_options",
    "field_type",
    "node_comment",
    "node_hints",
    "rec_fields",
    "rec_ref",
    "wrapper_type",
    *DOCUMENT_TECHNICAL_METADATA,
    *DOCUMENT_FREE_TEXT_METADATA,
}
FREE_TEXT_ATTRIBUTE_NAMES = {
    "COMMENT",
    "DESCRIPTION",
    "DISPLAY-LABEL",
    "DISPLAY-NAME",
    "LABEL",
    "NAME",
    "NOTE",
    "TEXT",
    "TITLE",
}


class StableIdFactory:
    def __init__(self) -> None:
        self._used: dict[str, tuple[str, ...]] = {}
        self.findings: list[AnalysisFinding] = []

    def make(
        self, prefix: str, source: SourceReference, *parts: str | int | None
    ) -> str:
        key = tuple("" if part is None else str(part) for part in parts)
        digest = hashlib.sha256("\0".join(key).encode()).hexdigest()[:16]
        base = f"{prefix}_{digest}"
        previous = self._used.get(base)
        if previous is None or previous == key:
            self._used[base] = key
            return base

        index = 2
        candidate = f"{base}_{index}"
        while candidate in self._used and self._used[candidate] != key:
            index += 1
            candidate = f"{base}_{index}"
        self._used[candidate] = key
        self.findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="ID_COLLISION_RESOLVED",
                message=f"Stable ID collision for {base} was resolved as {candidate}.",
                source=source,
            )
        )
        return candidate


def analyze_path(
    path: Path,
    config: AppConfig,
    processes_file: Path | None = None,
    *,
    processes_file_explicit: bool = False,
) -> AnalysisResult:
    scan_root = path.resolve()
    inventory = scan_path(scan_root)
    process_catalog_path = processes_file or scan_root / "processes.yml"
    process_catalog = load_process_catalog(
        process_catalog_path,
        scan_root,
        explicit=processes_file_explicit or processes_file is not None,
    )
    service_index = _build_service_index(inventory.packages)
    extraction_policy = _extraction_policy_snapshot(config)
    id_factory = StableIdFactory()
    service_classifications: dict[str, ClassificationResult] = {}
    package_services: dict[str, list[FlowService]] = {}
    package_documents: dict[str, list[DocumentType]] = {}
    pending_services: list[FlowService] = []
    all_document_reference_occurrences: list[DocumentReferenceOccurrence] = []
    service_reference_inputs: list[tuple[str, ArtifactCandidate]] = []
    all_findings: list[AnalysisFinding] = list(inventory.findings)
    all_findings.extend(process_catalog.findings)

    package_shells: list[AnalyzedPackage] = []
    for package in inventory.packages:
        package_findings = sorted(package.findings, key=_finding_key)
        services: list[FlowService] = []
        documents: list[DocumentType] = []
        java_analyses: list[JavaServiceAnalysis] = []
        for artifact in package.artifacts:
            if artifact.probable_type in SERVICE_INDEX_ARTIFACTS:
                service_reference_inputs.append((package.name, artifact))
            if artifact.probable_type in DOCUMENT_ARTIFACTS:
                document, references = _parse_document_type(
                    scan_root, package.name, artifact, config, extraction_policy, id_factory
                )
                documents.append(document)
                all_document_reference_occurrences.extend(references)
                all_findings.extend(document.findings)
                continue
            if artifact.probable_type == "java_service":
                service = _parse_java_service(
                    scan_root,
                    package.name,
                    artifact,
                    config,
                    extraction_policy,
                    id_factory,
                )
                services.append(service)
                pending_services.append(service)
                if service.java_analysis is not None:
                    java_analyses.append(service.java_analysis)
                    all_findings.extend(service.java_analysis.findings)
                service_classifications[service.identity.full_name] = service.classification
                continue
            if artifact.probable_type == "opaque_service":
                service = _parse_opaque_service(
                    scan_root,
                    package.name,
                    artifact,
                    config,
                    extraction_policy,
                )
                services.append(service)
                pending_services.append(service)
                service_classifications[service.identity.full_name] = service.classification
                continue
            if artifact.probable_type not in ANALYZABLE_FLOW_ARTIFACTS:
                continue
            service = _parse_flow_service(
                scan_root, package.name, artifact, config, extraction_policy, id_factory
            )
            services.append(service)
            pending_services.append(service)
            service_classifications[service.identity.full_name] = service.classification
        package_services[package.name] = services
        package_documents[package.name] = documents
        all_findings.extend(package_findings)
        package_shells.append(
            AnalyzedPackage(
                name=package.name,
                root=package.root,
                services=[],
                java_service_analyses=[],
                document_types=[],
                service_index=sorted(
                    service_index.values(), key=lambda item: item.identity.full_name.casefold()
                ),
                findings=package_findings,
            )
        )

    resolved_services: dict[str, list[FlowService]] = {name: [] for name in package_services}
    all_calls: list[CallOccurrence] = []
    all_unique_dependencies: list[UniqueDependency] = []
    all_flow_maps: list[FlowMap] = []
    all_mapping_operations: list[MappingOperation] = []
    all_transformer_bindings: list[TransformerBinding] = []
    for service in pending_services:
        resolved_calls, unique_dependencies = _resolve_service_dependencies(
            service, service_index, service_classifications, config
        )
        java_analysis = (
            _resolve_java_invocations(service.java_analysis, resolved_calls)
            if service.java_analysis is not None
            else None
        )
        service = service.model_copy(
            update={
                "call_occurrences": resolved_calls,
                "unique_dependencies": unique_dependencies,
                "metrics": _metrics(
                    resolved_calls,
                    unique_dependencies,
                    service.flow_tree,
                    service.flow_maps,
                    service.mapping_operations,
                    service.transformer_bindings,
                    java_analysis,
                ),
                "java_analysis": java_analysis,
                "findings": _aggregate_findings(service.findings),
            }
        )
        all_calls.extend(resolved_calls)
        all_unique_dependencies.extend(unique_dependencies)
        all_flow_maps.extend(service.flow_maps)
        all_mapping_operations.extend(service.mapping_operations)
        all_transformer_bindings.extend(service.transformer_bindings)
        resolved_services[service.identity.package].append(service)

    all_document_types = sorted(
        [document for documents in package_documents.values() for document in documents],
        key=_document_type_key,
    )
    document_index = {document.identity.full_name: document for document in all_document_types}
    all_document_reference_occurrences.extend(
        _parse_service_document_reference_occurrences(
            scan_root, service_reference_inputs, id_factory
        )
    )
    all_document_reference_occurrences = _resolve_document_references(
        all_document_reference_occurrences, document_index, all_findings
    )
    all_document_dependencies = _aggregate_document_dependencies(
        all_document_reference_occurrences, document_index, id_factory
    )
    all_service_document_dependencies = _aggregate_service_document_dependencies(
        all_document_reference_occurrences, id_factory
    )
    all_findings.extend(
        _cycle_findings(all_document_dependencies, document_index, scan_root)
    )
    all_findings.extend(id_factory.findings)
    final_packages: list[AnalyzedPackage] = []
    for analyzed_package in package_shells:
        services_with_document_refs = [
            _attach_service_document_dependencies(
                service, all_document_reference_occurrences, all_service_document_dependencies
            )
            for service in resolved_services.get(analyzed_package.name, [])
        ]
        final_packages.append(
            analyzed_package.model_copy(
                update={
                    "services": sorted(
                        services_with_document_refs,
                        key=lambda item: item.identity.full_name.casefold(),
                    ),
                    "java_service_analyses": sorted(
                        [
                            service.java_analysis
                            for service in services_with_document_refs
                            if service.java_analysis is not None
                        ],
                        key=_java_service_analysis_key,
                    ),
                    "document_types": sorted(
                        package_documents.get(analyzed_package.name, []),
                        key=_document_type_key,
                    ),
                }
            )
        )

    all_calls = sorted(all_calls, key=_call_key)
    all_unique_dependencies = sorted(all_unique_dependencies, key=_unique_dependency_key)
    all_flow_maps = sorted(all_flow_maps, key=_flow_map_key)
    all_mapping_operations = sorted(all_mapping_operations, key=_mapping_operation_key)
    all_transformer_bindings = sorted(all_transformer_bindings, key=_transformer_binding_key)
    all_document_reference_occurrences = sorted(
        all_document_reference_occurrences, key=_document_reference_key
    )
    all_document_dependencies = sorted(all_document_dependencies, key=_document_dependency_key)
    all_service_document_dependencies = sorted(
        all_service_document_dependencies, key=_service_document_dependency_key
    )
    all_java_analyses = sorted(
        [
            analysis
            for package in final_packages
            for analysis in package.java_service_analyses
        ],
        key=_java_service_analysis_key,
    )
    all_java_imports = sorted(
        [item for analysis in all_java_analyses for item in analysis.imports],
        key=_java_import_key,
    )
    all_java_type_references = sorted(
        [item for analysis in all_java_analyses for item in analysis.referenced_types],
        key=_java_type_reference_key,
    )
    all_java_pipeline_accesses = sorted(
        [item for analysis in all_java_analyses for item in analysis.pipeline_accesses],
        key=_java_pipeline_access_key,
    )
    all_java_invocations = sorted(
        [item for analysis in all_java_analyses for item in analysis.invocation_occurrences],
        key=_java_invocation_key,
    )
    all_services = [service for package in final_packages for service in package.services]
    process_definitions, initial_process_entrypoints, process_definition_findings = (
        _process_definitions_from_catalog(process_catalog, config)
    )
    all_findings.extend(process_definition_findings)
    process_output = build_process_analysis(
        processes=process_definitions,
        process_entrypoints=initial_process_entrypoints,
        services=all_services,
        unique_dependencies=all_unique_dependencies,
        service_document_dependencies=all_service_document_dependencies,
        document_dependencies=all_document_dependencies,
    )
    all_findings.extend(process_output.findings)
    top_level_metrics = _top_level_metrics(
        all_calls,
        all_unique_dependencies,
        all_flow_maps,
        all_mapping_operations,
        all_transformer_bindings,
        final_packages,
        all_document_reference_occurrences,
        all_document_dependencies,
        all_service_document_dependencies,
        all_java_analyses,
        all_java_pipeline_accesses,
        all_java_invocations,
    )
    top_level_metrics = _with_process_metrics(
        top_level_metrics,
        all_services,
        process_output.processes,
        process_output.process_entrypoints,
        process_output.process_service_memberships,
        process_output.process_dependency_edges,
        process_output.process_unresolved_calls,
        process_output.process_document_relationships,
        process_output.technical_entrypoint_candidates,
    )
    return AnalysisResult(
        tool_version=__version__,
        packages=sorted(final_packages, key=lambda item: item.name.casefold()),
        metrics=top_level_metrics,
        extraction_policy=extraction_policy,
        call_occurrences=all_calls,
        unique_dependencies=all_unique_dependencies,
        flow_maps=all_flow_maps,
        mapping_operations=all_mapping_operations,
        transformer_bindings=all_transformer_bindings,
        document_types=all_document_types,
        document_reference_occurrences=all_document_reference_occurrences,
        document_dependencies=all_document_dependencies,
        service_document_dependencies=all_service_document_dependencies,
        java_service_analyses=all_java_analyses,
        java_imports=all_java_imports,
        java_type_references=all_java_type_references,
        java_pipeline_accesses=all_java_pipeline_accesses,
        java_invocation_occurrences=all_java_invocations,
        processes=process_output.processes,
        process_entrypoints=process_output.process_entrypoints,
        process_service_memberships=process_output.process_service_memberships,
        process_dependency_edges=process_output.process_dependency_edges,
        process_unresolved_calls=process_output.process_unresolved_calls,
        process_document_relationships=process_output.process_document_relationships,
        technical_entrypoint_candidates=process_output.technical_entrypoint_candidates,
        findings=_aggregate_findings(all_findings),
    )


def _build_service_index(packages: Iterable[PackageInventory]) -> dict[str, ServiceSummary]:
    index: dict[str, ServiceSummary] = {}
    for package in packages:
        for artifact in package.artifacts:
            if artifact.probable_type not in SERVICE_INDEX_ARTIFACTS:
                continue
            if artifact.identity is None or artifact.identity.full_name is None:
                continue
            service_type = _service_type_for_artifact(artifact.probable_type)
            identity = ServiceIdentity(
                package=package.name,
                namespace=artifact.identity.namespace or "",
                name=artifact.identity.name or "",
                full_name=artifact.identity.full_name,
                basis=artifact.identity.basis,
                source=artifact.source,
            )
            index[identity.full_name] = ServiceSummary(
                identity=identity,
                service_type=service_type,
                source_service_type=artifact.source_service_type,
                analysis_status=(
                    ServiceAnalysisStatus.OPAQUE
                    if service_type == ServiceType.OPAQUE
                    else (
                        ServiceAnalysisStatus.PARTIAL
                        if artifact.status != FindingStatus.SUPPORTED
                        else ServiceAnalysisStatus.FULL
                    )
                ),
                source=artifact.source,
            )
    return dict(sorted(index.items(), key=lambda item: item[0].casefold()))


def _service_type_for_artifact(probable_type: str) -> ServiceType:
    if probable_type in ANALYZABLE_FLOW_ARTIFACTS:
        return ServiceType.FLOW
    if probable_type == "java_service":
        return ServiceType.JAVA
    if probable_type == "opaque_service":
        return ServiceType.OPAQUE
    return ServiceType.UNKNOWN


def _parse_document_type(
    scan_root: Path,
    package_name: str,
    artifact: ArtifactCandidate,
    config: AppConfig,
    extraction_policy: ExtractionPolicySnapshot,
    id_factory: StableIdFactory,
) -> tuple[DocumentType, list[DocumentReferenceOccurrence]]:
    del extraction_policy
    node_path = _artifact_node_path(scan_root, artifact)
    findings: list[AnalysisFinding] = []
    references: list[DocumentReferenceOccurrence] = []
    fallback_identity = _document_identity_from_artifact(package_name, artifact)
    source = source_for_node(node_path, scan_root, "document_type")
    identity = DocumentIdentity(
        package=package_name,
        namespace=fallback_identity.namespace,
        name=fallback_identity.name,
        full_name=fallback_identity.full_name,
        basis=FactBasis.RECONSTRUCTED,
        source=source,
    )
    description: TextValue | None = None
    fields: list[DocumentField] = []

    try:
        root = parse_xml_file(node_path)
        record = _record_child(root, "record")
        if record is None or _value_child(record, "node_type") != "record":
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.MALFORMED,
                    code="DOCUMENT_TYPE_MALFORMED",
                    message="Document Type metadata is missing record/node_type=record.",
                    source=source,
                )
            )
        else:
            source = _element_source(node_path, scan_root, record, "document_type")
            declared_full_name = _value_child(record, "node_nsName")
            declared_package = _value_child(record, "node_pkg")
            if declared_full_name:
                namespace, name = _split_full_name(declared_full_name)
                identity = DocumentIdentity(
                    package=package_name,
                    namespace=namespace,
                    name=name,
                    full_name=declared_full_name,
                    basis=FactBasis.CONFIRMED,
                    source=source,
                    declared_package=declared_package,
                )
                if declared_full_name != fallback_identity.full_name:
                    findings.append(
                        AnalysisFinding(
                            status=FindingStatus.PARTIALLY_SUPPORTED,
                            code="DOCUMENT_IDENTITY_MISMATCH",
                            message=(
                                "Document node_nsName differs from namespace path identity "
                                f"{fallback_identity.full_name!r}."
                            ),
                            source=source,
                        )
                    )
            description = _apply_free_text_policy(
                _blank_to_none(_value_child(record, "node_comment")),
                "document_description",
                source,
                config,
                "node_comment",
            )
            findings.extend(
                _unsupported_document_metadata_findings(
                    record,
                    node_path,
                    scan_root,
                    "document",
                    identity.full_name,
                    config,
                    DOCUMENT_ROOT_KNOWN_METADATA,
                )
            )
            document_id = id_factory.make(
                "doc", source, package_name, "document", identity.full_name
            )
            rec_fields = _array_child(record, "rec_fields")
            if rec_fields is not None:
                fields, references = _parse_document_fields(
                    fields_parent=rec_fields,
                    scan_root=scan_root,
                    node_path=node_path,
                    document_id=document_id,
                    document_full_name=identity.full_name,
                    package_name=package_name,
                    config=config,
                    id_factory=id_factory,
                    findings=findings,
                    parent_structural_path="",
                    parent_field_path="",
                )
            return (
                DocumentType(
                    id=document_id,
                    identity=identity,
                    description=description,
                    fields=fields,
                    source=source,
                    findings=_aggregate_findings(findings),
                ),
                references,
            )
    except (XmlParseError, XmlSecurityError) as exc:
        findings.append(_xml_finding(exc, node_path, scan_root, "document_type"))

    document_id = id_factory.make("doc", source, package_name, "document", identity.full_name)
    return (
        DocumentType(
            id=document_id,
            identity=identity,
            description=description,
            fields=fields,
            source=source,
            confidence=InterpretationConfidence.RAW_ONLY,
            findings=_aggregate_findings(findings),
        ),
        references,
    )


def _parse_document_fields(
    *,
    fields_parent: etree._Element,
    scan_root: Path,
    node_path: Path,
    document_id: str,
    document_full_name: str,
    package_name: str,
    config: AppConfig,
    id_factory: StableIdFactory,
    findings: list[AnalysisFinding],
    parent_structural_path: str,
    parent_field_path: str,
) -> tuple[list[DocumentField], list[DocumentReferenceOccurrence]]:
    fields: list[DocumentField] = []
    references: list[DocumentReferenceOccurrence] = []
    seen_names: set[str] = set()
    for child in fields_parent:
        if isinstance(child.tag, str) and child.tag != "record":
            source_node = parent_field_path or parent_structural_path or "document"
            findings.append(
                _malformed_nested_record_finding(
                    node_path,
                    scan_root,
                    child,
                    document_full_name,
                    source_node,
                    "rec_fields contains a non-record child element.",
                )
            )
    for order, field_record in enumerate(_direct_children(fields_parent, "record"), start=1):
        field, field_refs = _parse_document_field(
            field_record=field_record,
            scan_root=scan_root,
            node_path=node_path,
            document_id=document_id,
            document_full_name=document_full_name,
            package_name=package_name,
            config=config,
            id_factory=id_factory,
            findings=findings,
            declared_order=order,
            parent_structural_path=parent_structural_path,
            parent_field_path=parent_field_path,
        )
        normalized = field.name.casefold()
        if normalized in seen_names:
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.PARTIALLY_SUPPORTED,
                    code="DUPLICATE_FIELD_NAME",
                    message=f"Duplicate field name {field.name!r} appears within one record.",
                    source=field.source,
                )
            )
        seen_names.add(normalized)
        fields.append(field)
        references.extend(field_refs)
    return fields, references


def _parse_document_field(
    *,
    field_record: etree._Element,
    scan_root: Path,
    node_path: Path,
    document_id: str,
    document_full_name: str,
    package_name: str,
    config: AppConfig,
    id_factory: StableIdFactory,
    findings: list[AnalysisFinding],
    declared_order: int,
    parent_structural_path: str,
    parent_field_path: str,
) -> tuple[DocumentField, list[DocumentReferenceOccurrence]]:
    source = _element_source(node_path, scan_root, field_record, "document_field")
    name = _value_child(field_record, "field_name")
    if name is None or name == "":
        name = "<unnamed>"
        findings.append(
            AnalysisFinding(
                status=FindingStatus.MALFORMED,
                code="MISSING_FIELD_NAME",
                message="Document field is missing field_name.",
                source=source,
            )
        )
    structural_path = f"{parent_structural_path}/field[{declared_order}]".strip("/")
    field_path = f"{parent_field_path}/{name}".strip("/")
    field_id = id_factory.make(
        "docfield", source, package_name, document_full_name, "field", structural_path
    )
    raw_field_type = _value_child(field_record, "field_type")
    field_type = _document_field_type(raw_field_type, source, findings)
    raw_dimension = _value_child(field_record, "field_dim")
    dimension = _document_dimension(raw_dimension, source, findings)

    child_fields: list[DocumentField] = []
    references: list[DocumentReferenceOccurrence] = []
    rec_fields_children = _named_children(field_record, "rec_fields")
    child_records = _array_child(field_record, "rec_fields")
    if field_type == DocumentFieldType.RECORD:
        for child in rec_fields_children:
            if child.tag != "array":
                findings.append(
                    _malformed_nested_record_finding(
                        node_path,
                        scan_root,
                        child,
                        document_full_name,
                        field_path,
                        "rec_fields metadata is not an array container.",
                    )
                )
    if child_records is not None:
        child_fields, references = _parse_document_fields(
            fields_parent=child_records,
            scan_root=scan_root,
            node_path=node_path,
            document_id=document_id,
            document_full_name=document_full_name,
            package_name=package_name,
            config=config,
            id_factory=id_factory,
            findings=findings,
            parent_structural_path=structural_path,
            parent_field_path=field_path,
        )

    declared_target = _value_child(field_record, "rec_ref")
    if field_type == DocumentFieldType.DOCUMENT_REFERENCE:
        if not declared_target:
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.UNRESOLVED,
                    code="MISSING_DOCUMENT_REFERENCE_TARGET",
                    message="Document reference field is missing rec_ref.",
                    source=source,
                )
            )
        else:
            references.append(
                DocumentReferenceOccurrence(
                    id=id_factory.make(
                        "docref",
                        source,
                        DocumentReferenceOwnerKind.DOCUMENT.value,
                        document_full_name,
                        structural_path,
                        declared_target,
                    ),
                    owner_kind=DocumentReferenceOwnerKind.DOCUMENT,
                    owner_name=document_full_name,
                    owner_id=document_id,
                    source_field_id=field_id,
                    source_field_path=field_path,
                    declared_target=declared_target,
                    resolved=False,
                    dimension=dimension,
                    raw_dimension=raw_dimension,
                    dependency_kind=DocumentDependencyKind.REFERENCES_DOCUMENT,
                    source=source,
                )
            )

    return (
        DocumentField(
            id=field_id,
            name=name,
            raw_field_type=raw_field_type,
            field_type=field_type,
            raw_dimension=raw_dimension,
            dimension=dimension,
            optional=_parse_optional(_value_child(field_record, "field_opt")),
            wrapper_type=_value_child(field_record, "wrapper_type"),
            document_reference=declared_target,
            declared_order=declared_order,
            structural_path=structural_path,
            field_path=field_path,
            source=source.model_copy(update={"source_node": field_path}),
            technical_metadata=_document_technical_metadata(field_record),
            text_metadata=_document_text_metadata(field_record, source, config),
            unknown_metadata=_document_unknown_metadata(
                field_record, node_path, scan_root, field_path, config, findings
            ),
            children=child_fields,
        ),
        references,
    )


def _parse_service_document_reference_occurrences(
    scan_root: Path,
    service_inputs: list[tuple[str, ArtifactCandidate]],
    id_factory: StableIdFactory,
) -> list[DocumentReferenceOccurrence]:
    occurrences: list[DocumentReferenceOccurrence] = []
    for package_name, artifact in service_inputs:
        del package_name
        if artifact.identity is None or artifact.identity.full_name is None:
            continue
        node_path = _artifact_node_path(scan_root, artifact)
        try:
            root = parse_xml_file(node_path)
        except (XmlParseError, XmlSecurityError):
            continue
        svc_sig = _record_child(root, "svc_sig")
        service_name = artifact.identity.full_name
        for direction, role in (
            ("sig_in", ServiceDocumentUsageRole.INPUT),
            ("sig_out", ServiceDocumentUsageRole.OUTPUT),
        ):
            direction_record = _record_child(svc_sig, direction)
            rec_fields = _array_child(direction_record, "rec_fields")
            if rec_fields is None:
                continue
            occurrences.extend(
                _service_signature_document_refs(
                    rec_fields,
                    scan_root,
                    node_path,
                    service_name,
                    role,
                    id_factory,
                    parent_structural_path=direction,
                    parent_field_path="",
                )
            )
    return occurrences


def _service_signature_document_refs(
    fields_parent: etree._Element,
    scan_root: Path,
    node_path: Path,
    service_name: str,
    role: ServiceDocumentUsageRole,
    id_factory: StableIdFactory,
    *,
    parent_structural_path: str,
    parent_field_path: str,
) -> list[DocumentReferenceOccurrence]:
    occurrences: list[DocumentReferenceOccurrence] = []
    for order, field_record in enumerate(_direct_children(fields_parent, "record"), start=1):
        name = _value_child(field_record, "field_name") or "<unnamed>"
        structural_path = f"{parent_structural_path}/field[{order}]"
        field_path = f"{parent_field_path}/{name}".strip("/")
        raw_type = _value_child(field_record, "field_type")
        raw_dimension = _value_child(field_record, "field_dim")
        declared_target = _value_child(field_record, "rec_ref")
        source = _element_source(node_path, scan_root, field_record, "signature_field").model_copy(
            update={"source_node": structural_path}
        )
        if raw_type == "recref" and declared_target:
            occurrences.append(
                DocumentReferenceOccurrence(
                    id=id_factory.make(
                        "docref",
                        source,
                        DocumentReferenceOwnerKind.SERVICE_SIGNATURE.value,
                        service_name,
                        structural_path,
                        declared_target,
                    ),
                    owner_kind=DocumentReferenceOwnerKind.SERVICE_SIGNATURE,
                    owner_name=service_name,
                    source_field_path=field_path,
                    declared_target=declared_target,
                    resolved=False,
                    dimension=_document_dimension(raw_dimension, source, []),
                    raw_dimension=raw_dimension,
                    dependency_kind=DocumentDependencyKind.USES_DOCUMENT,
                    usage_role=role,
                    source=source,
                )
            )
        child_records = _array_child(field_record, "rec_fields")
        if child_records is not None:
            occurrences.extend(
                _service_signature_document_refs(
                    child_records,
                    scan_root,
                    node_path,
                    service_name,
                    role,
                    id_factory,
                    parent_structural_path=structural_path,
                    parent_field_path=field_path,
                )
            )
    return occurrences


def _parse_flow_service(
    scan_root: Path,
    package_name: str,
    artifact: ArtifactCandidate,
    config: AppConfig,
    extraction_policy: ExtractionPolicySnapshot,
    id_factory: StableIdFactory,
) -> FlowService:
    if artifact.identity is None or artifact.identity.full_name is None:
        identity = ServiceIdentity(
            package=package_name,
            namespace="",
            name=artifact.relative_path.rsplit("/", 1)[-1],
            full_name=artifact.relative_path,
            basis=FactBasis.UNRESOLVED,
            source=artifact.source,
        )
    else:
        identity = ServiceIdentity(
            package=package_name,
            namespace=artifact.identity.namespace or "",
            name=artifact.identity.name or "",
            full_name=artifact.identity.full_name,
            basis=FactBasis.RECONSTRUCTED,
            source=artifact.source,
        )

    service_dir = scan_root / artifact.relative_path
    node_path = service_dir / "node.ndf"
    flow_path = service_dir / "flow.xml"
    findings: list[AnalysisFinding] = []
    signature = ServiceSignature(
        source=SourceReference(
            path=stable_relative_path(node_path, scan_root), artifact_type="node_ndf"
        )
    )
    description: TextValue | None = None
    description_status = ServiceDescriptionStatus.NO_DESCRIPTION
    source_service_type = artifact.source_service_type

    try:
        values = parse_values_file(node_path)
        source_service_type = _normalized_scalar_value(values, "svc_type") or source_service_type
        node_root = parse_xml_file(node_path)
        description, description_status, description_findings = _service_description(
            values, node_root, node_path, scan_root, config
        )
        findings.extend(description_findings)
        findings.extend(_service_signature_metadata_findings(node_root, node_path, scan_root))
        signature = _parse_signature(node_root, node_path, scan_root)
    except (XmlParseError, XmlSecurityError) as exc:
        findings.append(_xml_finding(exc, node_path, scan_root, "node_ndf"))

    flow_tree: FlowNode | None = None
    call_occurrences: list[CallOccurrence] = []
    flow_maps: list[FlowMap] = []
    mapping_operations: list[MappingOperation] = []
    transformer_bindings: list[TransformerBinding] = []
    if flow_path.exists():
        try:
            (
                flow_tree,
                call_occurrences,
                flow_maps,
                mapping_operations,
                transformer_bindings,
                flow_findings,
            ) = _parse_flow_xml(
                flow_path, scan_root, identity, config, id_factory
            )
            findings.extend(flow_findings)
        except (XmlParseError, XmlSecurityError) as exc:
            findings.append(_xml_finding(exc, flow_path, scan_root, "flow_xml"))
    else:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.UNRESOLVED,
                code="FLOW_XML_MISSING",
                message="node.ndf declares a FLOW service but flow.xml is missing.",
                source=SourceReference(
                    path=stable_relative_path(node_path, scan_root), artifact_type="flow_service"
                ),
            )
        )

    classification = classify_service(identity.full_name, identity.name, config)
    return FlowService(
        identity=identity,
        source_service_type=source_service_type,
        analysis_status=_service_analysis_status(ServiceType.FLOW, findings),
        description_status=description_status,
        description=description,
        signature=signature,
        classification=classification,
        flow_tree=flow_tree,
        metrics=_metrics(
            call_occurrences, [], flow_tree, flow_maps, mapping_operations, transformer_bindings
        ),
        call_occurrences=call_occurrences,
        flow_maps=flow_maps,
        mapping_operations=mapping_operations,
        transformer_bindings=transformer_bindings,
        extraction_policy=extraction_policy,
        findings=findings,
        source=artifact.source,
    )


def _parse_java_service(
    scan_root: Path,
    package_name: str,
    artifact: ArtifactCandidate,
    config: AppConfig,
    extraction_policy: ExtractionPolicySnapshot,
    id_factory: StableIdFactory,
) -> FlowService:
    identity = _service_identity(package_name, artifact)
    service_dir = scan_root / artifact.relative_path
    node_path = service_dir / "node.ndf"
    findings: list[AnalysisFinding] = []
    signature = ServiceSignature(
        source=SourceReference(
            path=stable_relative_path(node_path, scan_root), artifact_type="node_ndf"
        )
    )
    description: TextValue | None = None
    description_status = ServiceDescriptionStatus.NO_DESCRIPTION
    source_service_type = artifact.source_service_type

    try:
        values = parse_values_file(node_path)
        source_service_type = _normalized_scalar_value(values, "svc_type") or source_service_type
        node_root = parse_xml_file(node_path)
        description, description_status, description_findings = _service_description(
            values, node_root, node_path, scan_root, config
        )
        findings.extend(description_findings)
        findings.extend(_service_signature_metadata_findings(node_root, node_path, scan_root))
        signature = _parse_signature(node_root, node_path, scan_root)
    except (XmlParseError, XmlSecurityError) as exc:
        findings.append(_xml_finding(exc, node_path, scan_root, "node_ndf"))

    java_analysis, java_calls = analyze_java_service(
        scan_root=scan_root,
        package_name=package_name,
        artifact=artifact,
        identity=identity,
        signature=signature,
        id_factory=id_factory,
    )
    findings.extend(java_analysis.findings)
    classification = classify_service(identity.full_name, identity.name, config)
    return FlowService(
        identity=identity,
        service_type=ServiceType.JAVA,
        source_service_type=source_service_type,
        analysis_status=_service_analysis_status(ServiceType.JAVA, findings),
        description_status=description_status,
        description=description,
        signature=signature,
        classification=classification,
        metrics=_metrics(java_calls, [], None, [], [], [], java_analysis),
        call_occurrences=java_calls,
        java_analysis=java_analysis,
        extraction_policy=extraction_policy,
        findings=findings,
        source=artifact.source,
    )


def _parse_opaque_service(
    scan_root: Path,
    package_name: str,
    artifact: ArtifactCandidate,
    config: AppConfig,
    extraction_policy: ExtractionPolicySnapshot,
) -> FlowService:
    identity = _service_identity(package_name, artifact)
    service_dir = scan_root / artifact.relative_path
    node_path = service_dir / "node.ndf"
    findings: list[AnalysisFinding] = []
    signature = ServiceSignature(
        source=SourceReference(
            path=stable_relative_path(node_path, scan_root), artifact_type="node_ndf"
        )
    )
    description: TextValue | None = None
    description_status = ServiceDescriptionStatus.NO_DESCRIPTION
    source_service_type = artifact.source_service_type

    try:
        values = parse_values_file(node_path)
        source_service_type = _normalized_scalar_value(values, "svc_type") or source_service_type
        node_root = parse_xml_file(node_path)
        description, description_status, description_findings = _service_description(
            values, node_root, node_path, scan_root, config
        )
        findings.extend(description_findings)
        findings.extend(_service_signature_metadata_findings(node_root, node_path, scan_root))
        signature = _parse_signature(node_root, node_path, scan_root)
    except (XmlParseError, XmlSecurityError) as exc:
        findings.append(_xml_finding(exc, node_path, scan_root, "node_ndf"))

    findings.append(
        AnalysisFinding(
            status=FindingStatus.PARTIALLY_SUPPORTED,
            code="OPAQUE_SERVICE_IMPLEMENTATION_NOT_ANALYZED",
            message=(
                "Service identity and common metadata were retained, but source service type "
                f"{source_service_type or '<unknown>'!r} has no implementation-specific parser."
            ),
            source=_node_value_source(node_path, scan_root, "service_type", "svc_type"),
            severity=FindingSeverity.INFO,
        )
    )
    classification = classify_service(identity.full_name, identity.name, config)
    return FlowService(
        identity=identity,
        service_type=ServiceType.OPAQUE,
        source_service_type=source_service_type,
        analysis_status=ServiceAnalysisStatus.OPAQUE,
        description_status=description_status,
        description=description,
        signature=signature,
        classification=classification,
        metrics=AnalysisMetrics(),
        extraction_policy=extraction_policy,
        findings=findings,
        source=artifact.source,
    )


def _process_definitions_from_catalog(
    catalog: ParsedProcessCatalog, config: AppConfig
) -> tuple[list[ProcessDefinition], list[ProcessEntrypoint], list[AnalysisFinding]]:
    definitions: list[ProcessDefinition] = []
    entrypoints: list[ProcessEntrypoint] = []
    for parsed in catalog.definitions:
        description = None
        description_status = ProcessDescriptionStatus.NO_DESCRIPTION
        if parsed.description_malformed:
            description_status = ProcessDescriptionStatus.DESCRIPTION_MALFORMED
        elif parsed.description is not None and parsed.description_source is not None:
            description = _apply_free_text_policy(
                parsed.description,
                "process_description",
                parsed.description_source,
                config,
                "description",
                parsed.process_id,
            )
            description_status = _process_description_status(description)
        process_stable_id = _stable_process_id(parsed.process_id)
        process_entrypoint_ids: list[str] = []
        for entrypoint in parsed.entrypoints:
            entrypoint_id = _stable_process_entrypoint_id(
                parsed.process_id,
                entrypoint.declared_target,
                entrypoint.duplicate_index,
            )
            process_entrypoint_ids.append(entrypoint_id)
            entrypoints.append(
                ProcessEntrypoint(
                    id=entrypoint_id,
                    process_id=parsed.process_id,
                    declared_target=entrypoint.declared_target,
                    status=(
                        ProcessEntrypointStatus.DUPLICATE
                        if entrypoint.duplicate
                        else ProcessEntrypointStatus.RESOLVED
                    ),
                    source=entrypoint.source,
                )
            )
        definitions.append(
            ProcessDefinition(
                id=process_stable_id,
                process_id=parsed.process_id,
                name=parsed.name,
                description_status=description_status,
                description=description,
                entrypoint_ids=process_entrypoint_ids,
                source=parsed.source,
                id_source=parsed.id_source,
                name_source=parsed.name_source,
                description_source=parsed.description_source,
                findings=parsed.findings,
            )
        )
    return (
        sorted(definitions, key=lambda item: item.process_id.casefold()),
        sorted(entrypoints, key=lambda item: (item.process_id.casefold(), item.id)),
        [],
    )


def _process_description_status(description: TextValue | None) -> ProcessDescriptionStatus:
    if description is None:
        return ProcessDescriptionStatus.NO_DESCRIPTION
    if description.disclosure == TextDisclosure.REDACTED:
        return ProcessDescriptionStatus.DESCRIPTION_REDACTED
    if description.disclosure == TextDisclosure.OMITTED:
        return ProcessDescriptionStatus.DESCRIPTION_OMITTED
    if description.disclosure == TextDisclosure.BLOCKED_SECRET:
        return ProcessDescriptionStatus.DESCRIPTION_BLOCKED_SECRET
    return ProcessDescriptionStatus.SOURCE_DESCRIPTION


def _stable_process_id(process_id: str) -> str:
    digest = hashlib.sha256(process_id.encode("utf-8")).hexdigest()[:12]
    return f"process_{digest}"


def _stable_process_entrypoint_id(
    process_id: str, declared_target: str, duplicate_index: int
) -> str:
    digest = hashlib.sha256(
        f"{process_id}\0{declared_target}\0{duplicate_index}".encode()
    ).hexdigest()[:12]
    return f"process_entrypoint_{digest}"


def _service_identity(package_name: str, artifact: ArtifactCandidate) -> ServiceIdentity:
    if artifact.identity is None or artifact.identity.full_name is None:
        return ServiceIdentity(
            package=package_name,
            namespace="",
            name=artifact.relative_path.rsplit("/", 1)[-1],
            full_name=artifact.relative_path,
            basis=FactBasis.UNRESOLVED,
            source=artifact.source,
        )
    return ServiceIdentity(
        package=package_name,
        namespace=artifact.identity.namespace or "",
        name=artifact.identity.name or "",
        full_name=artifact.identity.full_name,
        basis=FactBasis.RECONSTRUCTED,
        source=artifact.source,
    )


def _normalized_scalar_value(values: dict[str, object], name: str) -> str | None:
    value = scalar_value(values, name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _service_description(
    values: dict[str, object],
    node_root: etree._Element,
    node_path: Path,
    scan_root: Path,
    config: AppConfig,
) -> tuple[TextValue | None, ServiceDescriptionStatus, list[AnalysisFinding]]:
    if "node_comment" not in values:
        return None, ServiceDescriptionStatus.NO_DESCRIPTION, []
    raw_value = values["node_comment"]
    source = _node_named_child_source(
        node_path, scan_root, "node_comment", "node_comment", node_root
    )
    if not isinstance(raw_value, str):
        return (
            None,
            ServiceDescriptionStatus.DESCRIPTION_MALFORMED,
            [
                AnalysisFinding(
                    status=FindingStatus.MALFORMED,
                    code="SERVICE_DESCRIPTION_MALFORMED",
                    message="Service node_comment metadata is not a scalar text value.",
                    source=source,
                    severity=FindingSeverity.WARNING,
                )
            ],
        )
    text = _blank_to_none(raw_value)
    if text is None:
        return None, ServiceDescriptionStatus.NO_DESCRIPTION, []
    description = _apply_free_text_policy(
        text,
        "service_description",
        source,
        config,
        "node_comment",
    )
    if description is None:
        return None, ServiceDescriptionStatus.NO_DESCRIPTION, []
    return description, _description_status(description), []


def _description_status(description: TextValue) -> ServiceDescriptionStatus:
    if description.disclosure == TextDisclosure.REDACTED:
        return ServiceDescriptionStatus.DESCRIPTION_REDACTED
    if description.disclosure == TextDisclosure.OMITTED:
        return ServiceDescriptionStatus.DESCRIPTION_OMITTED
    if description.disclosure == TextDisclosure.BLOCKED_SECRET:
        return ServiceDescriptionStatus.DESCRIPTION_BLOCKED_SECRET
    return ServiceDescriptionStatus.SOURCE_DESCRIPTION


def _service_analysis_status(
    service_type: ServiceType, findings: list[AnalysisFinding]
) -> ServiceAnalysisStatus:
    if service_type == ServiceType.OPAQUE:
        return ServiceAnalysisStatus.OPAQUE
    if any(
        finding.status in {FindingStatus.MALFORMED, FindingStatus.UNRESOLVED}
        or (
            finding.status == FindingStatus.PARTIALLY_SUPPORTED
            and finding.severity != FindingSeverity.INFO
        )
        for finding in findings
    ):
        return ServiceAnalysisStatus.PARTIAL
    return ServiceAnalysisStatus.FULL


def _service_signature_metadata_findings(
    node_root: etree._Element, node_path: Path, scan_root: Path
) -> list[AnalysisFinding]:
    svc_sig = _first_named_child(node_root, "svc_sig")
    if svc_sig is None:
        return []
    if svc_sig.tag != "record":
        return [
            _service_signature_partial_finding(
                node_path,
                scan_root,
                svc_sig,
                "Service signature metadata is not a record.",
            )
        ]
    findings: list[AnalysisFinding] = []
    for direction in ("sig_in", "sig_out"):
        direction_record = _first_named_child(svc_sig, direction)
        if direction_record is None:
            continue
        if direction_record.tag != "record":
            findings.append(
                _service_signature_partial_finding(
                    node_path,
                    scan_root,
                    direction_record,
                    f"Service signature {direction} metadata is not a record.",
                )
            )
            continue
        findings.extend(
            _signature_record_metadata_findings(
                direction_record, node_path, scan_root, f"svc_sig/{direction}"
            )
        )
    return findings


def _signature_record_metadata_findings(
    record: etree._Element, node_path: Path, scan_root: Path, path_label: str
) -> list[AnalysisFinding]:
    rec_fields = _first_named_child(record, "rec_fields")
    if rec_fields is None:
        return []
    if rec_fields.tag != "array":
        return [
            _service_signature_partial_finding(
                node_path,
                scan_root,
                rec_fields,
                f"Service signature {path_label}/rec_fields metadata is not an array.",
            )
        ]
    findings: list[AnalysisFinding] = []
    for index, child in enumerate([item for item in rec_fields if isinstance(item.tag, str)]):
        if child.tag != "record":
            findings.append(
                _service_signature_partial_finding(
                    node_path,
                    scan_root,
                    child,
                    f"Service signature {path_label}/rec_fields[{index + 1}] is not a record.",
                )
            )
            continue
        findings.extend(
            _signature_record_metadata_findings(
                child, node_path, scan_root, f"{path_label}/rec_fields[{index + 1}]"
            )
        )
    return findings


def _service_signature_partial_finding(
    node_path: Path, scan_root: Path, element: etree._Element, message: str
) -> AnalysisFinding:
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        code="SERVICE_SIGNATURE_METADATA_PARTIAL",
        message=message,
        source=_element_source(node_path, scan_root, element, "service_signature"),
        severity=FindingSeverity.WARNING,
    )


def _parse_signature(
    node_root: etree._Element, node_path: Path, scan_root: Path
) -> ServiceSignature:
    svc_sig_node = _first_named_child(node_root, "svc_sig")
    source = _element_source(node_path, scan_root, svc_sig_node, "service_signature")
    if svc_sig_node is not None:
        source = source.model_copy(
            update={"source_node": _named_source_node(svc_sig_node, "svc_sig")}
        )
    svc_sig = svc_sig_node if svc_sig_node is not None and svc_sig_node.tag == "record" else None
    sig_in = _record_child(svc_sig, "sig_in")
    sig_out = _record_child(svc_sig, "sig_out")
    return ServiceSignature(
        inputs=_parse_signature_fields(sig_in, node_path, scan_root, "sig_in"),
        outputs=_parse_signature_fields(sig_out, node_path, scan_root, "sig_out"),
        source=source,
    )


def _parse_signature_fields(
    record: etree._Element | None, node_path: Path, scan_root: Path, direction: str
) -> list[SignatureField]:
    if record is None:
        return []
    rec_fields = _array_child(record, "rec_fields")
    if rec_fields is None:
        return []
    fields = [
        _parse_signature_field(field, node_path, scan_root, f"{direction}/rec_fields[{index}]")
        for index, field in enumerate(_direct_children(rec_fields, "record"), start=1)
    ]
    return sorted(fields, key=lambda item: item.name.casefold())


def _parse_signature_field(
    field: etree._Element, node_path: Path, scan_root: Path, xml_suffix: str
) -> SignatureField:
    name = _value_child(field, "field_name") or "<unnamed>"
    raw_children = _array_child(field, "rec_fields")
    children: list[SignatureField] = []
    if raw_children is not None:
        children = [
            _parse_signature_field(
                child, node_path, scan_root, f"{xml_suffix}/rec_fields[{index}]"
            )
            for index, child in enumerate(_direct_children(raw_children, "record"), start=1)
        ]
    source = _element_source(node_path, scan_root, field, "signature_field").model_copy(
        update={"source_node": f"/Values/record[@name='svc_sig']/{xml_suffix}"}
    )
    return SignatureField(
        name=name,
        data_type=_value_child(field, "field_type"),
        dimensions=_parse_int(_value_child(field, "field_dim")),
        optional=_parse_optional(_value_child(field, "field_opt")),
        document_reference=_value_child(field, "rec_ref"),
        wrapper_type=_value_child(field, "wrapper_type"),
        children=sorted(children, key=lambda item: item.name.casefold()),
        source=source,
    )


def _parse_flow_xml(
    flow_path: Path,
    scan_root: Path,
    identity: ServiceIdentity,
    config: AppConfig,
    id_factory: StableIdFactory,
) -> tuple[
    FlowNode | None,
    list[CallOccurrence],
    list[FlowMap],
    list[MappingOperation],
    list[TransformerBinding],
    list[AnalysisFinding],
]:
    root = parse_xml_file(flow_path)
    findings: list[AnalysisFinding] = []
    calls: list[CallOccurrence] = []
    flow_maps: list[FlowMap] = []
    mapping_operations: list[MappingOperation] = []
    transformer_bindings: list[TransformerBinding] = []
    unsupported_seen: set[str] = set()
    counters = {"node": 0, "call": 0, "map": 0, "mapop": 0, "binding": 0}

    def next_node_id() -> str:
        counters["node"] += 1
        return f"fn{counters['node']:04d}"

    def visit(
        element: etree._Element,
        parent_id: str | None,
        parent_path: list[str],
        parent_call_occurrence_id: str | None = None,
        parent_call_target: str | None = None,
        parent_call_tag: str | None = None,
    ) -> list[FlowNode]:
        if not isinstance(element.tag, str):
            return []
        tag = element.tag
        if tag == "COMMENT":
            return []
        if tag in MAPPING_INTERNAL_TAGS:
            if tag == "MAPSOURCE":
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.PARTIALLY_SUPPORTED,
                        code="ORPHAN_MAPSOURCE",
                        message="MAPSOURCE metadata appeared outside a supported MAP container.",
                        source=_element_source(flow_path, scan_root, element, "mapsource"),
                    )
                )
            elif tag == "MAPTARGET":
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.PARTIALLY_SUPPORTED,
                        code="ORPHAN_MAPTARGET",
                        message="MAPTARGET metadata appeared outside a supported MAP container.",
                        source=_element_source(flow_path, scan_root, element, "maptarget"),
                    )
                )
            else:
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.PARTIALLY_SUPPORTED,
                        code="UNKNOWN_MAPPING_CHILD",
                        message=f"FLOW mapping element {tag} appeared outside a MAP container.",
                        source=_element_source(flow_path, scan_root, element, tag.lower()),
                    )
                )
            return []
        if tag not in FLOW_NODE_TAGS:
            if tag.isupper() and tag not in unsupported_seen:
                unsupported_seen.add(tag)
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.PARTIALLY_SUPPORTED,
                        code="UNSUPPORTED_FLOW_ELEMENT",
                        message=f"FLOW element {tag} is observed but not interpreted in M2a.",
                        source=_element_source(flow_path, scan_root, element, tag.lower()),
                    )
                )
            child_nodes = []
            for child in element:
                child_nodes.extend(
                    visit(
                        child,
                        parent_id,
                        parent_path,
                        parent_call_occurrence_id,
                        parent_call_target,
                        parent_call_tag,
                    )
                )
            return child_nodes

        node_id = next_node_id()
        structural_path_parts = [*parent_path, node_id]
        structural_path = "/".join(structural_path_parts)
        node_type = FLOW_NODE_TAGS[tag]
        call_occurrence_id: str | None = None
        target: str | None = None
        if tag in CALL_TAGS:
            target = element.get("SERVICE")
            if target:
                counters["call"] += 1
                call_type = CALL_TAGS[tag]
                call_source = _element_source(flow_path, scan_root, element, tag.lower())
                call_occurrence_id = id_factory.make(
                    "call",
                    call_source,
                    identity.full_name,
                    tag,
                    structural_path,
                    counters["call"],
                )
                calls.append(
                    CallOccurrence(
                        id=call_occurrence_id,
                        caller=identity.full_name,
                        target=target,
                        call_type=call_type,
                        dependency_kind=_dependency_kind(call_type),
                        order=counters["call"],
                        parent_flow_path=list(parent_path),
                        structural_path=structural_path,
                        resolved=False,
                        target_classification=classify_service(
                            target, target.rsplit(":", 1)[-1], config
                        ),
                        source=call_source,
                    )
                )
            else:
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.UNKNOWN,
                        code="INVOKE_WITHOUT_SERVICE",
                        message=f"{tag} element does not declare a SERVICE attribute.",
                        source=_element_source(flow_path, scan_root, element, tag.lower()),
                    )
                )

        active_call_id = call_occurrence_id or parent_call_occurrence_id
        active_call_target = target or parent_call_target
        active_call_tag = tag if call_occurrence_id is not None else parent_call_tag
        if node_type == FlowNodeType.MAP:
            counters["map"] += 1
            parsed_map, parsed_operations, parsed_bindings = _parse_flow_map(
                element=element,
                flow_path=flow_path,
                scan_root=scan_root,
                identity=identity,
                config=config,
                id_factory=id_factory,
                counters=counters,
                structural_path=structural_path,
                parent_path=parent_path,
                parent_call_occurrence_id=active_call_id,
                parent_call_target=active_call_target,
                parent_call_tag=active_call_tag,
                findings=findings,
            )
            flow_maps.append(parsed_map)
            mapping_operations.extend(parsed_operations)
            transformer_bindings.extend(parsed_bindings)

        children: list[FlowNode] = []
        for child in element:
            if (
                node_type == FlowNodeType.MAP
                and isinstance(child.tag, str)
                and child.tag in MAPPING_INTERNAL_TAGS
            ):
                continue
            if (
                node_type == FlowNodeType.BRANCH
                and isinstance(child.tag, str)
                and child.tag != "COMMENT"
            ):
                label_source = _element_source(flow_path, scan_root, child, "branch_case")
                raw_label = child.get("NAME")
                label = _apply_free_text_policy(
                    _blank_to_none(raw_label), "branch_case_name", label_source, config, "NAME"
                )
                case_id = next_node_id()
                case_path_parts = [*structural_path_parts, case_id]
                case_children = visit(
                    child,
                    case_id,
                    case_path_parts,
                    active_call_id,
                    active_call_target,
                    active_call_tag,
                )
                children.append(
                    FlowNode(
                        id=case_id,
                        type=FlowNodeType.BRANCH_CASE,
                        label=label,
                        is_default_case=raw_label == "$default",
                        attributes={"source_type": child.tag},
                        parent_id=node_id,
                        structural_path="/".join(case_path_parts),
                        children=case_children,
                        source=label_source,
                    )
                )
            else:
                children.extend(
                    visit(
                        child,
                        node_id,
                        structural_path_parts,
                        active_call_id,
                        active_call_target,
                        active_call_tag,
                    )
            )

        if node_type == FlowNodeType.EXIT:
            _validate_exit(element, flow_path, scan_root, findings)
        source = _element_source(flow_path, scan_root, element, tag.lower())
        technical_attrs, text_attrs, unknown_attrs = _classified_attributes(
            element=element,
            source=source,
            config=config,
            technical_names=FLOW_TECHNICAL_ATTRIBUTES.get(tag, set()),
            free_text_names=FLOW_FREE_TEXT_ATTRIBUTES,
        )
        node = FlowNode(
            id=node_id,
            type=node_type,
            label=text_attrs.get("NAME"),
            attributes=technical_attrs,
            text_attributes=text_attrs,
            unknown_attributes=unknown_attrs,
            parent_id=parent_id,
            structural_path=structural_path,
            children=children,
            exit_on=element.get("EXIT-ON") if node_type == FlowNodeType.SEQUENCE else None,
            form=element.get("FORM") if node_type == FlowNodeType.SEQUENCE else None,
            switch=element.get("SWITCH") if node_type == FlowNodeType.BRANCH else None,
            evaluate_labels=_parse_optional(element.get("LABELEXPRESSIONS"))
            if node_type == FlowNodeType.BRANCH
            else None,
            in_array=element.get("IN-ARRAY") if node_type == FlowNodeType.LOOP else None,
            out_array=element.get("OUT-ARRAY") if node_type == FlowNodeType.LOOP else None,
            exit_from=element.get("FROM") if node_type == FlowNodeType.EXIT else None,
            signal=element.get("SIGNAL") if node_type == FlowNodeType.EXIT else None,
            failure_message=element.get("FAILURE-MESSAGE")
            if node_type == FlowNodeType.EXIT
            else None,
            target=target,
            call_occurrence_id=call_occurrence_id,
            source=source,
        )
        return [node]

    roots = visit(root, None, [])
    flow_tree = roots[0] if roots else None
    mapping_operations = _with_document_traversal_order(mapping_operations)
    return (
        flow_tree,
        sorted(calls, key=_call_key),
        sorted(flow_maps, key=_flow_map_key),
        sorted(mapping_operations, key=_mapping_operation_key),
        sorted(transformer_bindings, key=_transformer_binding_key),
        sorted(findings, key=_finding_key),
    )


def _parse_flow_map(
    *,
    element: etree._Element,
    flow_path: Path,
    scan_root: Path,
    identity: ServiceIdentity,
    config: AppConfig,
    id_factory: StableIdFactory,
    counters: dict[str, int],
    structural_path: str,
    parent_path: list[str],
    parent_call_occurrence_id: str | None,
    parent_call_target: str | None,
    parent_call_tag: str | None,
    findings: list[AnalysisFinding],
) -> tuple[FlowMap, list[MappingOperation], list[TransformerBinding]]:
    source = _element_source(flow_path, scan_root, element, "map")
    flow_map_id = id_factory.make(
        "map", source, identity.full_name, "MAP", structural_path, counters["map"]
    )
    source_schema: MapSchemaMetadata | None = None
    target_schema: MapSchemaMetadata | None = None
    operations: list[MappingOperation] = []
    bindings: list[TransformerBinding] = []
    direct_tags = [child.tag for child in element if isinstance(child.tag, str)]
    if "MAPSOURCE" in direct_tags and "MAPTARGET" not in direct_tags:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="ORPHAN_MAPSOURCE",
                message="MAPSOURCE metadata did not have paired MAPTARGET metadata.",
                source=source,
            )
        )
    if "MAPTARGET" in direct_tags and "MAPSOURCE" not in direct_tags:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="ORPHAN_MAPTARGET",
                message="MAPTARGET metadata did not have paired MAPSOURCE metadata.",
                source=source,
            )
        )
    if (
        "MAPSOURCE" in direct_tags
        and "MAPTARGET" in direct_tags
        and direct_tags.index("MAPSOURCE") < direct_tags.index("MAPTARGET")
    ):
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="PARTIAL_MAPPING_INTERPRETATION",
                message="MAPSOURCE appeared before MAPTARGET; metadata order was preserved.",
                source=source,
            )
        )

    map_operation_order = 0
    for child in element:
        if not isinstance(child.tag, str) or child.tag == "COMMENT":
            continue
        child_tag = child.tag
        if child_tag == "MAPSOURCE":
            if source_schema is None:
                source_schema = _parse_map_schema_metadata(
                    "source", child, flow_path, scan_root
                )
            continue
        if child_tag == "MAPTARGET":
            if target_schema is None:
                target_schema = _parse_map_schema_metadata(
                    "target", child, flow_path, scan_root
            )
            continue
        if child_tag in MAPPING_OPERATION_TAGS:
            counters["mapop"] += 1
            map_operation_order += 1
            operation = _parse_mapping_operation(
                element=child,
                flow_path=flow_path,
                scan_root=scan_root,
                identity=identity,
                config=config,
                id_factory=id_factory,
                counters=counters,
                flow_map_id=flow_map_id,
                map_structural_path=structural_path,
                map_operation_order=map_operation_order,
                findings=findings,
            )
            operation_bindings = _transformer_bindings_for_operation(
                operation=operation,
                map_mode=element.get("MODE"),
                parent_call_occurrence_id=parent_call_occurrence_id,
                parent_call_target=parent_call_target,
                parent_call_tag=parent_call_tag,
                identity=identity,
                id_factory=id_factory,
                counters=counters,
                findings=findings,
            )
            if operation_bindings:
                operation = operation.model_copy(
                    update={
                        "transformer_binding_ids": [
                            binding.id for binding in operation_bindings
                        ]
                    }
                )
                bindings.extend(operation_bindings)
            operations.append(operation)
            continue
        if child_tag not in FLOW_NODE_TAGS:
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.PARTIALLY_SUPPORTED,
                    code="UNKNOWN_MAPPING_CHILD",
                    message=f"Unsupported MAP child {child_tag} was preserved as a finding.",
                    source=_element_source(flow_path, scan_root, child, child_tag.lower()),
                )
            )

    technical_attrs, text_attrs, unknown_attrs = _classified_attributes(
        element=element,
        source=source,
        config=config,
        technical_names=FLOW_TECHNICAL_ATTRIBUTES["MAP"],
        free_text_names=FLOW_FREE_TEXT_ATTRIBUTES,
    )
    flow_map = FlowMap(
        id=flow_map_id,
        service=identity.full_name,
        mode=element.get("MODE"),
        order=counters["map"],
        structural_path=structural_path,
        parent_flow_path=list(parent_path),
        parent_call_occurrence_id=parent_call_occurrence_id,
        source_schema=source_schema,
        target_schema=target_schema,
        operation_ids=[operation.id for operation in operations],
        raw_attrs=technical_attrs,
        technical_attrs=technical_attrs,
        text_attrs=text_attrs,
        unknown_attrs=unknown_attrs,
        source=source,
    )
    return flow_map, operations, bindings


def _parse_mapping_operation(
    *,
    element: etree._Element,
    flow_path: Path,
    scan_root: Path,
    identity: ServiceIdentity,
    config: AppConfig,
    id_factory: StableIdFactory,
    counters: dict[str, int],
    flow_map_id: str,
    map_structural_path: str,
    map_operation_order: int,
    findings: list[AnalysisFinding],
) -> MappingOperation:
    source = _element_source(flow_path, scan_root, element, element.tag.lower())
    operation_order = counters["mapop"]
    operation_type = {
        "MAPCOPY": MappingOperationType.COPY,
        "MAPSET": MappingOperationType.SET,
        "MAPDELETE": MappingOperationType.DELETE,
    }[element.tag]
    structural_path = f"{map_structural_path}/{element.tag.lower()}[{operation_order}]"
    operation_id = id_factory.make(
        "mapop",
        source,
        identity.full_name,
        operation_type.value,
        structural_path,
        operation_order,
    )
    technical_attrs, text_attrs, unknown_attrs = _classified_attributes(
        element=element,
        source=source,
        config=config,
        technical_names=MAPPING_TECHNICAL_ATTRIBUTES[element.tag],
        free_text_names=MAPPING_FREE_TEXT_ATTRIBUTES,
    )
    _validate_mapping_attrs(element, source, findings)

    source_endpoint: MappingEndpoint | None = None
    target_endpoint: MappingEndpoint | None = None
    delete_endpoint: MappingEndpoint | None = None
    literal: LiteralValue | None = None
    confidence = InterpretationConfidence.CONFIRMED

    if operation_type == MappingOperationType.COPY:
        source_endpoint = _endpoint_from_attr(element, "FROM", source, findings)
        target_endpoint = _endpoint_from_attr(element, "TO", source, findings)
    elif operation_type == MappingOperationType.SET:
        target_endpoint = _endpoint_from_attr(element, "FIELD", source, findings)
        literal = _parse_mapset_literal(element, source, config, flow_path, scan_root, findings)
        if literal.present:
            confidence = InterpretationConfidence.PARTIALLY_INTERPRETED
    elif operation_type == MappingOperationType.DELETE:
        delete_endpoint = _endpoint_from_attr(element, "FIELD", source, findings)

    return MappingOperation(
        id=operation_id,
        service=identity.full_name,
        flow_map_id=flow_map_id,
        operation_type=operation_type,
        order=operation_order,
        map_operation_order=map_operation_order,
        structural_path=structural_path,
        confidence=confidence,
        source=source,
        raw_attrs=technical_attrs,
        technical_attrs=technical_attrs,
        text_attrs=text_attrs,
        unknown_attrs=unknown_attrs,
        source_endpoint=source_endpoint,
        target_endpoint=target_endpoint,
        delete_endpoint=delete_endpoint,
        literal=literal,
    )


def _transformer_bindings_for_operation(
    *,
    operation: MappingOperation,
    map_mode: str | None,
    parent_call_occurrence_id: str | None,
    parent_call_target: str | None,
    parent_call_tag: str | None,
    identity: ServiceIdentity,
    id_factory: StableIdFactory,
    counters: dict[str, int],
    findings: list[AnalysisFinding],
) -> list[TransformerBinding]:
    if parent_call_tag != "MAPINVOKE" or not parent_call_occurrence_id or not parent_call_target:
        return []
    mode = (map_mode or "").casefold()
    direction: TransformerBindingDirection | None = None
    pipeline_endpoint: MappingEndpoint | None = None
    transformer_endpoint: MappingEndpoint | None = None

    if operation.operation_type == MappingOperationType.COPY:
        if mode == "invokeinput":
            direction = TransformerBindingDirection.INTO_TRANSFORMER
            pipeline_endpoint = operation.source_endpoint
            transformer_endpoint = operation.target_endpoint
        elif mode == "invokeoutput":
            direction = TransformerBindingDirection.FROM_TRANSFORMER
            transformer_endpoint = operation.source_endpoint
            pipeline_endpoint = operation.target_endpoint
    elif operation.operation_type == MappingOperationType.SET and mode == "invokeinput":
        direction = TransformerBindingDirection.INTO_TRANSFORMER
        transformer_endpoint = operation.target_endpoint

    if direction is None:
        if operation.operation_type in {MappingOperationType.COPY, MappingOperationType.SET}:
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.PARTIALLY_SUPPORTED,
                    code="AMBIGUOUS_TRANSFORMER_DIRECTION",
                    message=(
                        "MAPINVOKE child mapping operation could not be assigned a "
                        f"direction from MODE={map_mode!r}."
                    ),
                    source=operation.source,
                )
            )
        return []

    counters["binding"] += 1
    binding_id = id_factory.make(
        "bind",
        operation.source,
        identity.full_name,
        operation.id,
        direction.value,
        counters["binding"],
    )
    return [
        TransformerBinding(
            id=binding_id,
            service=identity.full_name,
            transformer_service=parent_call_target,
            call_occurrence_id=parent_call_occurrence_id,
            flow_map_id=operation.flow_map_id,
            mapping_operation_id=operation.id,
            direction=direction,
            order=counters["binding"],
            structural_path=operation.structural_path,
            transformer_endpoint=transformer_endpoint,
            pipeline_endpoint=pipeline_endpoint,
            literal=operation.literal,
            source=operation.source,
        )
    ]


def _parse_map_schema_metadata(
    kind: str, element: etree._Element, flow_path: Path, scan_root: Path
) -> MapSchemaMetadata:
    values = _first_child(element, "Values")
    xml_record = _record_child(values, "xml")
    rec_fields = _array_child(xml_record, "rec_fields")
    field_count = len(_direct_children(rec_fields, "record")) if rec_fields is not None else 0
    return MapSchemaMetadata(
        kind=kind,
        field_count=field_count,
        source=_element_source(flow_path, scan_root, element, f"map{kind}"),
    )


def _validate_mapping_attrs(
    element: etree._Element, source: SourceReference, findings: list[AnalysisFinding]
) -> None:
    allowed = {
        "MAPCOPY": {"FROM", "NAME", "TO"},
        "MAPSET": {"FIELD", "GLOBALVARIABLES", "NAME", "OVERWRITE", "VARIABLES"},
        "MAPDELETE": {"FIELD", "NAME"},
    }[element.tag]
    unknown = sorted(set(element.attrib) - allowed)
    if unknown:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="UNKNOWN_MAPPING_ATTRIBUTE",
                message=(
                    f"{element.tag} has unsupported attributes: {', '.join(unknown)}."
                ),
                source=source,
            )
        )


def _endpoint_from_attr(
    element: etree._Element,
    attr_name: str,
    source: SourceReference,
    findings: list[AnalysisFinding],
) -> MappingEndpoint | None:
    raw_path = element.get(attr_name)
    if not raw_path:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="MISSING_MAPPING_ENDPOINT",
                message=f"{element.tag} is missing required {attr_name} endpoint.",
                source=source,
            )
        )
        return None
    endpoint = MappingEndpoint(
        raw_path=raw_path,
        path=_pipeline_path(raw_path),
        source=source,
    )
    if not raw_path.startswith("/"):
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="MALFORMED_PIPELINE_PATH",
                message=f"{element.tag} {attr_name} endpoint is not an absolute pipeline path.",
                source=source,
            )
        )
    return endpoint


def _pipeline_path(raw_path: str) -> PipelinePath:
    segments = [segment for segment in raw_path.split("/") if segment]
    return PipelinePath(
        raw_path=raw_path,
        segments=segments,
        is_absolute=raw_path.startswith("/"),
        contains_index="[" in raw_path and "]" in raw_path,
        contains_wildcard="*" in raw_path,
        contains_document_ref=":" in raw_path,
    )


def _with_document_traversal_order(
    operations: list[MappingOperation],
) -> list[MappingOperation]:
    ordered = sorted(
        operations,
        key=lambda operation: (
            operation.service.casefold(),
            operation.source.path.casefold(),
            operation.source.line or 0,
            operation.source.xml_path or "",
            operation.id,
        ),
    )
    traversal_orders = {operation.id: index for index, operation in enumerate(ordered, start=1)}
    return [
        operation.model_copy(
            update={"document_traversal_order": traversal_orders[operation.id]}
        )
        for operation in operations
    ]


def _parse_mapset_literal(
    element: etree._Element,
    source: SourceReference,
    config: AppConfig,
    flow_path: Path,
    scan_root: Path,
    findings: list[AnalysisFinding],
) -> LiteralValue:
    data = _first_child(element, "DATA")
    if data is None:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="MISSING_LITERAL_DATA",
                message="MAPSET did not contain a DATA literal payload.",
                source=source,
            )
        )
        return LiteralValue(present=False, disclosure=LiteralDisclosure.NOT_PRESENT)

    data_source = _element_source(flow_path, scan_root, data, "data")
    if data.get("ENCODING") != "XMLValues":
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="UNSUPPORTED_LITERAL_ENCODING",
                message=f"DATA literal encoding {data.get('ENCODING')!r} is not interpreted.",
                source=data_source,
            )
        )
    values = _first_child(data, "Values")
    raw_value = _value_child(values, "xml")
    type_record = _record_child(values, "type")
    declared_type = _value_child(type_record, "field_type")
    declared_field_name = _value_child(type_record, "field_name")
    secret_context = _is_secret_context(
        element.get("FIELD"),
        element.get("NAME"),
        declared_type,
        declared_field_name,
    )
    length = len(raw_value) if raw_value is not None else None
    literal = LiteralValue(
        present=True,
        declared_type=declared_type,
        declared_field_name=declared_field_name,
        length=length if config.extraction.literals.mode != ExtractionMode.OMIT else None,
        is_empty=raw_value == "" if raw_value is not None else None,
        is_null_like=raw_value is None or raw_value.casefold() in {"$null", "null"},
        source=data_source,
    )

    if config.extraction.literals.mode == ExtractionMode.OMIT:
        return literal.model_copy(update={"disclosure": LiteralDisclosure.OMITTED})
    if secret_context:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="SECRET_LITERAL_REDACTED",
                message="Literal value was redacted because its mapping context is secret-like.",
                source=data_source,
            )
        )
        return literal.model_copy(
            update={
                "disclosure": LiteralDisclosure.BLOCKED_SECRET,
                "marker": "<redacted:secret-literal>",
            }
        )
    if config.extraction.literals.mode == ExtractionMode.INCLUDE:
        return literal.model_copy(
            update={"disclosure": LiteralDisclosure.INCLUDED, "value": raw_value}
        )
    return literal.model_copy(
        update={"disclosure": LiteralDisclosure.REDACTED, "marker": "<redacted:literal>"}
    )


def _artifact_node_path(scan_root: Path, artifact: ArtifactCandidate) -> Path:
    for file in artifact.files:
        if Path(file.path).name == "node.ndf":
            return scan_root / file.path
    return scan_root / artifact.relative_path / "node.ndf"


def source_for_node(path: Path, scan_root: Path, artifact_type: str) -> SourceReference:
    return SourceReference(path=stable_relative_path(path, scan_root), artifact_type=artifact_type)


def _document_identity_from_artifact(
    package_name: str, artifact: ArtifactCandidate
) -> DocumentIdentity:
    namespace = artifact.identity.namespace if artifact.identity else ""
    name = artifact.identity.name if artifact.identity else ""
    full_name = artifact.identity.full_name if artifact.identity else f"{namespace}:{name}"
    return DocumentIdentity(
        package=package_name,
        namespace=namespace or "",
        name=name or "",
        full_name=full_name or "",
        basis=artifact.identity.basis if artifact.identity else FactBasis.RECONSTRUCTED,
        source=artifact.source,
    )


def _split_full_name(full_name: str) -> tuple[str, str]:
    if ":" not in full_name:
        return "", full_name
    namespace, name = full_name.rsplit(":", 1)
    return namespace, name


def _document_field_type(
    raw_field_type: str | None, source: SourceReference, findings: list[AnalysisFinding]
) -> DocumentFieldType:
    if raw_field_type == "string":
        return DocumentFieldType.STRING
    if raw_field_type == "object":
        return DocumentFieldType.OBJECT
    if raw_field_type == "record":
        return DocumentFieldType.RECORD
    if raw_field_type == "recref":
        return DocumentFieldType.DOCUMENT_REFERENCE
    findings.append(
        AnalysisFinding(
            status=FindingStatus.PARTIALLY_SUPPORTED,
            code="UNKNOWN_FIELD_TYPE",
            message=f"Document field type {raw_field_type!r} is not recognized.",
            source=source,
        )
    )
    return DocumentFieldType.UNKNOWN


def _document_dimension(
    raw_dimension: str | None, source: SourceReference, findings: list[AnalysisFinding]
) -> DocumentDimensionKind:
    if raw_dimension == "0":
        return DocumentDimensionKind.SCALAR
    if raw_dimension == "1":
        return DocumentDimensionKind.LIST
    if raw_dimension is None:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="INVALID_DIMENSION",
                message="Document field is missing field_dim.",
                source=source,
            )
        )
        return DocumentDimensionKind.UNKNOWN
    if raw_dimension.isdecimal() and int(raw_dimension) > 1:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="UNSUPPORTED_DIMENSION",
                message=f"Document field dimension {raw_dimension!r} is preserved as raw metadata.",
                source=source,
            )
        )
        return DocumentDimensionKind.MULTIDIMENSIONAL
    findings.append(
        AnalysisFinding(
            status=FindingStatus.PARTIALLY_SUPPORTED,
            code="INVALID_DIMENSION",
            message=f"Document field dimension {raw_dimension!r} is invalid.",
            source=source,
        )
    )
    return DocumentDimensionKind.UNKNOWN


def _document_technical_metadata(field_record: etree._Element) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for name in sorted(DOCUMENT_TECHNICAL_METADATA):
        if name == "field_options_count":
            field_options = _array_child(field_record, "field_options")
            if field_options is not None:
                metadata[name] = str(len(_direct_children(field_options, "value")))
            continue
        value = _value_child(field_record, name)
        if value is not None:
            metadata[name] = value
    node_hints = _record_child(field_record, "node_hints")
    if node_hints is not None:
        for name in ("field_usereditable", "field_largerEditor", "field_password"):
            value = _value_child(node_hints, name)
            if value is not None:
                metadata[name] = value
    return dict(sorted(metadata.items()))


def _document_text_metadata(
    field_record: etree._Element, source: SourceReference, config: AppConfig
) -> dict[str, TextValue]:
    metadata: dict[str, TextValue] = {}
    for name in sorted(DOCUMENT_FREE_TEXT_METADATA):
        text = _apply_free_text_policy(
            _blank_to_none(_value_child(field_record, name)),
            f"document_field.{name}",
            source,
            config,
            name,
        )
        if text is not None:
            metadata[name] = text
    return metadata


def _document_unknown_metadata(
    field_record: etree._Element,
    node_path: Path,
    scan_root: Path,
    field_path: str,
    config: AppConfig,
    findings: list[AnalysisFinding],
) -> list[AttributeValue]:
    unknown: list[AttributeValue] = []
    for child in field_record:
        if not isinstance(child.tag, str):
            continue
        name = child.get("name")
        if not name or name in DOCUMENT_FIELD_KNOWN_METADATA:
            continue
        source = _element_source(node_path, scan_root, child, "document_field").model_copy(
            update={"source_node": field_path}
        )
        if child.tag == "value":
            attribute = _unknown_attribute(name, child.text or "", source, config)
        else:
            attribute = _unknown_attribute(name, f"<{child.tag}>", source, config)
        unknown.append(attribute)
        findings.append(_unsupported_document_metadata_finding(name, "field", source, attribute))
    return sorted(unknown, key=lambda item: item.name.casefold())


def _unsupported_document_metadata_findings(
    element: etree._Element,
    node_path: Path,
    scan_root: Path,
    owner_type: str,
    owner_path: str,
    config: AppConfig,
    known_names: set[str],
) -> list[AnalysisFinding]:
    findings: list[AnalysisFinding] = []
    for child in element:
        if not isinstance(child.tag, str):
            continue
        name = child.get("name")
        if not name or name in known_names:
            continue
        source = _element_source(node_path, scan_root, child, f"document_{owner_type}").model_copy(
            update={"source_node": owner_path}
        )
        value = (child.text or "") if child.tag == "value" else f"<{child.tag}>"
        attribute = _unknown_attribute(name, value, source, config)
        findings.append(_unsupported_document_metadata_finding(name, owner_type, source, attribute))
    return findings


def _unsupported_document_metadata_finding(
    name: str, owner_type: str, source: SourceReference, attribute: AttributeValue
) -> AnalysisFinding:
    disclosure = (
        attribute.text.disclosure.value
        if attribute.text is not None
        else TextDisclosure.OMITTED.value
    )
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        severity=FindingSeverity.INFO,
        confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
        code="UNSUPPORTED_DOCUMENT_METADATA",
        message=(
            f"Unsupported document metadata {name!r} on {owner_type} metadata "
            "was preserved without semantic interpretation "
            f"(value disclosure: {disclosure})."
        ),
        source=source,
    )


def _malformed_nested_record_finding(
    node_path: Path,
    scan_root: Path,
    element: etree._Element,
    document_full_name: str,
    field_path: str,
    reason: str,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        severity=FindingSeverity.WARNING,
        confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
        code="MALFORMED_NESTED_RECORD",
        message=(
            f"Malformed nested record metadata in document {document_full_name!r} "
            f"at field {field_path!r}: {reason}"
        ),
        source=_element_source(node_path, scan_root, element, "document_field").model_copy(
            update={"source_node": field_path}
        ),
    )


def _resolve_document_references(
    references: list[DocumentReferenceOccurrence],
    document_index: dict[str, DocumentType],
    findings: list[AnalysisFinding],
) -> list[DocumentReferenceOccurrence]:
    resolved: list[DocumentReferenceOccurrence] = []
    for reference in references:
        is_resolved = reference.declared_target in document_index
        if not is_resolved:
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.UNRESOLVED,
                    code="UNRESOLVED_DOCUMENT_REFERENCE",
                    message=(
                        "Document reference target "
                        f"{reference.declared_target!r} is not present in the analyzed snapshot."
                    ),
                    source=reference.source,
                )
            )
        resolved.append(
            reference.model_copy(
                update={
                    "resolved": is_resolved,
                    "canonical_target": reference.declared_target if is_resolved else None,
                }
            )
        )
    return resolved


def _aggregate_document_dependencies(
    references: list[DocumentReferenceOccurrence],
    document_index: dict[str, DocumentType],
    id_factory: StableIdFactory,
) -> list[DocumentDependency]:
    del document_index
    grouped: dict[tuple[str, str, DocumentDependencyKind], list[DocumentReferenceOccurrence]] = (
        defaultdict(list)
    )
    for reference in references:
        if reference.owner_kind != DocumentReferenceOwnerKind.DOCUMENT:
            continue
        target = reference.canonical_target or reference.declared_target
        grouped[(reference.owner_name, target, reference.dependency_kind)].append(reference)

    dependencies: list[DocumentDependency] = []
    for (source_document, target_document, kind), occurrences in grouped.items():
        ordered = sorted(occurrences, key=_document_reference_key)
        dependencies.append(
            DocumentDependency(
                id=id_factory.make(
                    "docdep",
                    ordered[0].source,
                    source_document,
                    kind.value,
                    target_document,
                ),
                source_document=source_document,
                target_document=target_document,
                dependency_kind=kind,
                resolved=all(occurrence.resolved for occurrence in ordered),
                occurrence_count=len(ordered),
                occurrence_ids=[occurrence.id for occurrence in ordered],
                source_samples=[occurrence.source for occurrence in ordered[:SOURCE_SAMPLE_LIMIT]],
            )
        )
    return sorted(dependencies, key=_document_dependency_key)


def _aggregate_service_document_dependencies(
    references: list[DocumentReferenceOccurrence],
    id_factory: StableIdFactory,
) -> list[ServiceDocumentDependency]:
    grouped: dict[tuple[str, str], list[DocumentReferenceOccurrence]] = defaultdict(list)
    for reference in references:
        if reference.owner_kind != DocumentReferenceOwnerKind.SERVICE_SIGNATURE:
            continue
        target = reference.canonical_target or reference.declared_target
        grouped[(reference.owner_name, target)].append(reference)

    dependencies: list[ServiceDocumentDependency] = []
    for (service, target_document), occurrences in grouped.items():
        ordered = sorted(occurrences, key=_document_reference_key)
        roles = {occurrence.usage_role for occurrence in ordered}
        if {ServiceDocumentUsageRole.INPUT, ServiceDocumentUsageRole.OUTPUT}.issubset(roles):
            role = ServiceDocumentUsageRole.INPUT_OUTPUT
        elif ServiceDocumentUsageRole.INPUT in roles:
            role = ServiceDocumentUsageRole.INPUT
        else:
            role = ServiceDocumentUsageRole.OUTPUT
        dependencies.append(
            ServiceDocumentDependency(
                id=id_factory.make(
                    "svcdoc",
                    ordered[0].source,
                    service,
                    DocumentDependencyKind.USES_DOCUMENT.value,
                    target_document,
                    role.value,
                ),
                service=service,
                target_document=target_document,
                dependency_kind=DocumentDependencyKind.USES_DOCUMENT,
                usage_role=role,
                resolved=all(occurrence.resolved for occurrence in ordered),
                occurrence_count=len(ordered),
                occurrence_ids=[occurrence.id for occurrence in ordered],
                source_samples=[occurrence.source for occurrence in ordered[:SOURCE_SAMPLE_LIMIT]],
            )
        )
    return sorted(dependencies, key=_service_document_dependency_key)


def _attach_service_document_dependencies(
    service: FlowService,
    references: list[DocumentReferenceOccurrence],
    dependencies: list[ServiceDocumentDependency],
) -> FlowService:
    service_references = sorted(
        [
            reference
            for reference in references
            if reference.owner_kind == DocumentReferenceOwnerKind.SERVICE_SIGNATURE
            and reference.owner_name == service.identity.full_name
        ],
        key=_document_reference_key,
    )
    service_dependencies = sorted(
        [
            dependency
            for dependency in dependencies
            if dependency.service == service.identity.full_name
        ],
        key=_service_document_dependency_key,
    )
    return service.model_copy(
        update={
            "document_reference_occurrences": service_references,
            "service_document_dependencies": service_dependencies,
        }
    )


def _cycle_findings(
    dependencies: list[DocumentDependency],
    document_index: dict[str, DocumentType],
    scan_root: Path,
) -> list[AnalysisFinding]:
    graph: dict[str, list[str]] = defaultdict(list)
    for dependency in dependencies:
        if dependency.resolved:
            graph[dependency.source_document].append(dependency.target_document)

    findings: list[AnalysisFinding] = []
    visited: set[str] = set()
    stack: list[str] = []
    reported: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        if node in stack:
            cycle = tuple(stack[stack.index(node) :] + [node])
            canonical = tuple(sorted(set(cycle)))
            if canonical not in reported:
                reported.add(canonical)
                document = document_index.get(node)
                source = document.source if document is not None else SourceReference(path=".")
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.PARTIALLY_SUPPORTED,
                        code="CYCLIC_DOCUMENT_REFERENCE",
                        message=(
                            "Document reference cycle was detected and not expanded "
                            "recursively."
                        ),
                        source=source,
                    )
                )
            return
        if node in visited:
            return
        visited.add(node)
        stack.append(node)
        for target in sorted(graph.get(node, []), key=str.casefold):
            visit(target)
        stack.pop()

    for document_name in sorted(graph, key=str.casefold):
        visit(document_name)
    return findings


def _resolve_service_dependencies(
    service: FlowService,
    service_index: dict[str, ServiceSummary],
    service_classifications: dict[str, ClassificationResult],
    config: AppConfig,
) -> tuple[list[CallOccurrence], list[UniqueDependency]]:
    resolved_calls: list[CallOccurrence] = []
    for call in service.call_occurrences:
        target_summary = service_index.get(call.target)
        target_name = call.target.rsplit(":", 1)[-1]
        target_classification = service_classifications.get(call.target)
        if target_classification is None:
            target_classification = classify_service(call.target, target_name, config)
        resolved_calls.append(
            call.model_copy(
                update={
                    "resolved": target_summary is not None,
                    "target_type": target_summary.service_type if target_summary else None,
                    "target_analysis_status": (
                        target_summary.analysis_status if target_summary else None
                    ),
                    "target_classification": target_classification,
                }
            )
        )
    return sorted(resolved_calls, key=_call_key), _aggregate_unique_dependencies(resolved_calls)


def _resolve_java_invocations(
    java_analysis: JavaServiceAnalysis | None, resolved_calls: list[CallOccurrence]
) -> JavaServiceAnalysis | None:
    if java_analysis is None:
        return None
    calls_by_target = {
        call.target: call for call in resolved_calls if call.call_type == CallType.JAVA_INVOKE
    }
    resolved_invocations = []
    for invocation in java_analysis.invocation_occurrences:
        call = (
            calls_by_target.get(invocation.canonical_target)
            if invocation.canonical_target is not None
            else None
        )
        if call is None:
            resolved_invocations.append(invocation)
            continue
        resolved_invocations.append(
            invocation.model_copy(
                update={
                    "resolved": call.resolved,
                    "target_type": call.target_type,
                }
            )
        )
    return java_analysis.model_copy(update={"invocation_occurrences": resolved_invocations})


def _aggregate_unique_dependencies(calls: list[CallOccurrence]) -> list[UniqueDependency]:
    grouped: dict[tuple[str, str, DependencyKind], list[CallOccurrence]] = defaultdict(list)
    for call in calls:
        grouped[(call.caller, call.target, call.dependency_kind)].append(call)

    dependencies: list[UniqueDependency] = []
    for (caller, target, kind), occurrences in grouped.items():
        ordered = sorted(occurrences, key=_call_key)
        dependency_id = _dependency_id(caller, target, kind)
        first = ordered[0]
        dependencies.append(
            UniqueDependency(
                id=dependency_id,
                source_service=caller,
                target_service=target,
                dependency_kind=kind,
                resolved=any(call.resolved for call in ordered),
                target_type=first.target_type,
                target_analysis_status=first.target_analysis_status,
                target_classification=first.target_classification,
                occurrence_count=len(ordered),
                occurrence_ids=[call.id for call in ordered],
                source_samples=[call.source for call in ordered[:UNRESOLVED_SOURCE_SAMPLE_LIMIT]],
            )
        )
    return sorted(dependencies, key=_unique_dependency_key)


def _metrics(
    calls: list[CallOccurrence],
    unique_dependencies: list[UniqueDependency],
    flow_tree: FlowNode | None,
    flow_maps: list[FlowMap],
    mapping_operations: list[MappingOperation],
    transformer_bindings: list[TransformerBinding],
    java_analysis: JavaServiceAnalysis | None = None,
) -> AnalysisMetrics:
    call_type_counts = Counter(call.call_type.value for call in calls)
    unique_kind_counts = Counter(dep.dependency_kind.value for dep in unique_dependencies)
    resolved_call_target_type_counts = Counter(
        call.target_type.value for call in calls if call.resolved and call.target_type is not None
    )
    resolved_dependency_target_type_counts = Counter(
        dependency.target_type.value
        for dependency in unique_dependencies
        if dependency.resolved and dependency.target_type is not None
    )
    mapping_type_counts = Counter(
        operation.operation_type.value for operation in mapping_operations
    )
    binding_direction_counts = Counter(
        binding.direction.value for binding in transformer_bindings
    )
    flow_node_counts = Counter[str]()
    if flow_tree is not None:
        _count_flow_nodes(flow_tree, flow_node_counts)
    flow_calls = [call for call in calls if call.call_type != CallType.JAVA_INVOKE]
    java_static_calls = [call for call in calls if call.call_type == CallType.JAVA_INVOKE]
    flow_dependencies = [
        dependency
        for dependency in unique_dependencies
        if not any(
            occurrence_id.startswith("call_java_")
            for occurrence_id in dependency.occurrence_ids
        )
    ]
    java_dependencies = [
        dependency
        for dependency in unique_dependencies
        if any(
            occurrence_id.startswith("call_java_")
            for occurrence_id in dependency.occurrence_ids
        )
    ]
    java_metrics = java_analysis.metrics if java_analysis is not None else AnalysisMetrics()
    return AnalysisMetrics(
        call_occurrence_count=len(calls),
        flow_call_occurrence_count=len(flow_calls),
        java_static_call_occurrence_count=len(java_static_calls),
        java_dynamic_call_occurrence_count=java_metrics.java_dynamic_call_occurrence_count,
        total_call_occurrence_count=len(calls),
        unique_dependency_count=len(unique_dependencies),
        resolved_call_occurrence_target_type_counts=dict(
            sorted(resolved_call_target_type_counts.items())
        ),
        resolved_unique_dependency_target_type_counts=dict(
            sorted(resolved_dependency_target_type_counts.items())
        ),
        flow_unique_dependency_count=len(flow_dependencies),
        java_unique_dependency_count=len(java_dependencies),
        total_unique_dependency_count=len(unique_dependencies),
        resolved_call_occurrence_count=sum(1 for call in calls if call.resolved),
        unresolved_call_occurrence_count=sum(1 for call in calls if not call.resolved),
        resolved_unique_dependency_count=sum(1 for dep in unique_dependencies if dep.resolved),
        unresolved_unique_dependency_count=sum(
            1 for dep in unique_dependencies if not dep.resolved
        ),
        call_type_counts=dict(sorted(call_type_counts.items())),
        unique_dependency_kind_counts=dict(sorted(unique_kind_counts.items())),
        flow_node_counts=dict(sorted(flow_node_counts.items())),
        flow_map_count=len(flow_maps),
        mapping_operation_count=len(mapping_operations),
        mapping_operation_type_counts=dict(sorted(mapping_type_counts.items())),
        transformer_binding_count=len(transformer_bindings),
        transformer_binding_direction_counts=dict(sorted(binding_direction_counts.items())),
        partially_interpreted_mapping_count=sum(
            1
            for operation in mapping_operations
            if operation.confidence != InterpretationConfidence.CONFIRMED
        ),
        java_service_analysis_count=java_metrics.java_service_analysis_count,
        java_source_match_count=java_metrics.java_source_match_count,
        java_source_only_count=java_metrics.java_source_only_count,
        java_fragment_only_count=java_metrics.java_fragment_only_count,
        java_source_mismatch_count=java_metrics.java_source_mismatch_count,
        java_source_method_not_found_count=java_metrics.java_source_method_not_found_count,
        java_source_method_ambiguous_count=java_metrics.java_source_method_ambiguous_count,
        java_source_identity_mismatch_count=java_metrics.java_source_identity_mismatch_count,
        java_source_partial_parse_count=java_metrics.java_source_partial_parse_count,
        java_pipeline_access_count=java_metrics.java_pipeline_access_count,
        java_pipeline_access_kind_counts=java_metrics.java_pipeline_access_kind_counts,
        java_pipeline_cursor_scope_counts=java_metrics.java_pipeline_cursor_scope_counts,
        java_invocation_occurrence_count=java_metrics.java_invocation_occurrence_count,
    )


def _top_level_metrics(
    calls: list[CallOccurrence],
    unique_dependencies: list[UniqueDependency],
    flow_maps: list[FlowMap],
    mapping_operations: list[MappingOperation],
    transformer_bindings: list[TransformerBinding],
    packages: list[AnalyzedPackage],
    document_references: list[DocumentReferenceOccurrence],
    document_dependencies: list[DocumentDependency],
    service_document_dependencies: list[ServiceDocumentDependency],
    java_analyses: list[JavaServiceAnalysis],
    java_pipeline_accesses: list[JavaPipelineAccess],
    java_invocations: list[JavaInvocationOccurrence],
) -> AnalysisMetrics:
    metrics = _metrics(
        calls,
        unique_dependencies,
        None,
        flow_maps,
        mapping_operations,
        transformer_bindings,
    )
    flow_node_counts = Counter[str]()
    document_types = [document for package in packages for document in package.document_types]
    services = [service for package in packages for service in package.services]
    service_type_counts = Counter(service.service_type.value for service in services)
    service_status_counts = Counter(service.analysis_status.value for service in services)
    description_status_counts = Counter(
        service.description_status.value for service in services
    )
    opaque_services = [
        service for service in services if service.service_type == ServiceType.OPAQUE
    ]
    java_status_counts = Counter(analysis.source_set.status.value for analysis in java_analyses)
    java_access_counts = Counter(access.access_kind.value for access in java_pipeline_accesses)
    java_scope_counts = Counter(access.cursor_scope.value for access in java_pipeline_accesses)
    java_static_call_count = sum(1 for call in calls if call.call_type == CallType.JAVA_INVOKE)
    java_dynamic_call_count = sum(
        1
        for invocation in java_invocations
        if invocation.target_status != JavaInvocationTargetStatus.STATIC_TARGET
    )
    java_dependencies = [
        dependency
        for dependency in unique_dependencies
        if any(
            occurrence_id.startswith("call_java_")
            for occurrence_id in dependency.occurrence_ids
        )
    ]
    for package in packages:
        for service in package.services:
            if service.flow_tree is not None:
                _count_flow_nodes(service.flow_tree, flow_node_counts)
    return metrics.model_copy(
        update={
            "flow_node_counts": dict(sorted(flow_node_counts.items())),
            "service_type_counts": dict(sorted(service_type_counts.items())),
            "service_analysis_status_counts": dict(sorted(service_status_counts.items())),
            "service_description_status_counts": dict(
                sorted(description_status_counts.items())
            ),
            "opaque_service_count": len(opaque_services),
            "opaque_service_with_description_count": sum(
                1 for service in opaque_services if service.description is not None
            ),
            "opaque_service_without_description_count": sum(
                1 for service in opaque_services if service.description is None
            ),
            "document_type_count": len(document_types),
            "document_field_count": sum(
                _count_document_fields(document.fields) for document in document_types
            ),
            "document_reference_occurrence_count": len(document_references),
            "resolved_document_reference_count": sum(
                1 for reference in document_references if reference.resolved
            ),
            "unresolved_document_reference_count": sum(
                1 for reference in document_references if not reference.resolved
            ),
            "unique_document_dependency_count": len(document_dependencies),
            "service_document_dependency_count": len(service_document_dependencies),
            "flow_call_occurrence_count": sum(
                1 for call in calls if call.call_type != CallType.JAVA_INVOKE
            ),
            "java_static_call_occurrence_count": java_static_call_count,
            "java_dynamic_call_occurrence_count": java_dynamic_call_count,
            "total_call_occurrence_count": len(calls),
            "flow_unique_dependency_count": len(unique_dependencies) - len(java_dependencies),
            "java_unique_dependency_count": len(java_dependencies),
            "total_unique_dependency_count": len(unique_dependencies),
            "java_service_analysis_count": len(java_analyses),
            "java_source_match_count": java_status_counts[
                JavaSourceStatus.SOURCE_AND_FRAGMENT_MATCH.value
            ],
            "java_source_only_count": java_status_counts[JavaSourceStatus.SOURCE_ONLY.value],
            "java_fragment_only_count": java_status_counts[JavaSourceStatus.FRAGMENT_ONLY.value],
            "java_source_mismatch_count": java_status_counts[
                JavaSourceStatus.SOURCE_FRAGMENT_MISMATCH.value
            ],
            "java_source_method_not_found_count": java_status_counts[
                JavaSourceStatus.SOURCE_METHOD_NOT_FOUND.value
            ],
            "java_source_method_ambiguous_count": java_status_counts[
                JavaSourceStatus.SOURCE_METHOD_AMBIGUOUS.value
            ],
            "java_source_identity_mismatch_count": java_status_counts[
                JavaSourceStatus.SOURCE_IDENTITY_MISMATCH.value
            ],
            "java_source_partial_parse_count": java_status_counts[
                JavaSourceStatus.SOURCE_PARTIAL_PARSE.value
            ],
            "java_pipeline_access_count": len(java_pipeline_accesses),
            "java_pipeline_access_kind_counts": dict(sorted(java_access_counts.items())),
            "java_pipeline_cursor_scope_counts": dict(sorted(java_scope_counts.items())),
            "java_invocation_occurrence_count": len(java_invocations),
        }
    )


def _with_process_metrics(
    metrics: AnalysisMetrics,
    services: list[FlowService],
    processes: list[ProcessDefinition],
    entrypoints: list[ProcessEntrypoint],
    memberships: list[ProcessServiceMembership],
    process_edges: list[ProcessDependencyEdge],
    unresolved_calls: list[ProcessUnresolvedCall],
    document_relationships: list[ProcessDocumentRelationship],
    candidates: list[TechnicalEntrypointCandidate],
) -> AnalysisMetrics:
    service_process_counts = Counter(membership.service for membership in memberships)
    service_names = {service.identity.full_name for service in services}
    services_in_declared_processes = set(service_process_counts)
    return metrics.model_copy(
        update={
            "process_definition_count": len(processes),
            "process_with_description_count": sum(
                1 for process in processes if process.description is not None
            ),
            "process_without_description_count": sum(
                1 for process in processes if process.description is None
            ),
            "declared_entrypoint_count": len(entrypoints),
            "resolved_entrypoint_count": sum(
                1
                for entrypoint in entrypoints
                if entrypoint.status == ProcessEntrypointStatus.RESOLVED
            ),
            "unresolved_entrypoint_count": sum(
                1
                for entrypoint in entrypoints
                if entrypoint.status != ProcessEntrypointStatus.RESOLVED
            ),
            "technical_entrypoint_candidate_count": len(candidates),
            "process_service_membership_count": len(memberships),
            "process_entrypoint_membership_count": sum(
                1 for membership in memberships if membership.entrypoint
            ),
            "process_dependency_edge_count": len(process_edges),
            "process_unresolved_call_count": len(unresolved_calls),
            "process_document_relationship_count": len(document_relationships),
            "processes_with_findings_count": sum(
                1 for process in processes if process.findings
            ),
            "services_in_multiple_processes_count": sum(
                1 for count in service_process_counts.values() if count > 1
            ),
            "services_in_no_declared_process_count": len(
                service_names - services_in_declared_processes
            ),
        }
    )


def _count_flow_nodes(node: FlowNode, counts: Counter[str]) -> None:
    counts[node.type.value] += 1
    for child in node.children:
        _count_flow_nodes(child, counts)


def _count_document_fields(fields: list[DocumentField]) -> int:
    return sum(1 + _count_document_fields(field.children) for field in fields)


def _validate_exit(
    element: etree._Element,
    flow_path: Path,
    scan_root: Path,
    findings: list[AnalysisFinding],
) -> None:
    unknown_attrs = sorted(set(element.attrib) - SUPPORTED_EXIT_ATTRIBUTES)
    if unknown_attrs or not element.get("FROM") or not element.get("SIGNAL"):
        details = []
        if unknown_attrs:
            details.append(f"unsupported attributes: {', '.join(unknown_attrs)}")
        if not element.get("FROM"):
            details.append("missing FROM")
        if not element.get("SIGNAL"):
            details.append("missing SIGNAL")
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="EXIT_UNSUPPORTED_FORM",
                message=(
                    "EXIT element was parsed but has an unsupported shape "
                    f"({'; '.join(details)})."
                ),
                source=_element_source(flow_path, scan_root, element, "exit"),
            )
        )


def _dependency_kind(call_type: CallType) -> DependencyKind:
    if call_type == CallType.MAPINVOKE:
        return DependencyKind.USES_TRANSFORMER
    return DependencyKind.INVOKES


def _dependency_id(caller: str, target: str, kind: DependencyKind) -> str:
    digest = hashlib.sha256(f"{caller}\0{target}\0{kind.value}".encode()).hexdigest()
    return f"dep_{digest[:12]}"


def _value_child(element: etree._Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = _direct_named_child(element, "value", name)
    if child is None:
        return None
    return child.text


def _node_value_source(
    node_path: Path, scan_root: Path, artifact_type: str, value_name: str
) -> SourceReference:
    return SourceReference(
        path=stable_relative_path(node_path, scan_root),
        artifact_type=artifact_type,
        source_node=f"/Values/value[@name='{value_name}']",
    )


def _node_named_child_source(
    node_path: Path,
    scan_root: Path,
    artifact_type: str,
    name: str,
    node_root: etree._Element,
) -> SourceReference:
    child = _first_named_child(node_root, name)
    if child is None:
        return SourceReference(
            path=stable_relative_path(node_path, scan_root),
            artifact_type=artifact_type,
        )
    return SourceReference(
        path=stable_relative_path(node_path, scan_root),
        artifact_type=artifact_type,
        source_node=_named_source_node(child, name),
    )


def _named_source_node(element: etree._Element, name: str) -> str:
    return f"/Values/{element.tag}[@name='{name}']"


def _record_child(element: etree._Element | None, name: str) -> etree._Element | None:
    return _direct_named_child(element, "record", name)


def _array_child(element: etree._Element | None, name: str) -> etree._Element | None:
    return _direct_named_child(element, "array", name)


def _direct_named_child(
    element: etree._Element | None, tag: str, name: str
) -> etree._Element | None:
    if element is None:
        return None
    for child in element:
        if isinstance(child.tag, str) and child.tag == tag and child.get("name") == name:
            return child
    return None


def _first_named_child(element: etree._Element | None, name: str) -> etree._Element | None:
    if element is None:
        return None
    for child in element:
        if isinstance(child.tag, str) and child.get("name") == name:
            return child
    return None


def _named_children(element: etree._Element | None, name: str) -> list[etree._Element]:
    if element is None:
        return []
    return [
        child
        for child in element
        if isinstance(child.tag, str) and child.get("name") == name
    ]


def _direct_children(element: etree._Element, tag: str) -> list[etree._Element]:
    return [child for child in element if isinstance(child.tag, str) and child.tag == tag]


def _first_child(element: etree._Element | None, tag: str) -> etree._Element | None:
    if element is None:
        return None
    for child in element:
        if isinstance(child.tag, str) and child.tag == tag:
            return child
    return None


def _element_source(
    flow_path: Path, scan_root: Path, element: etree._Element | None, artifact_type: str
) -> SourceReference:
    if element is None:
        return SourceReference(
            path=stable_relative_path(flow_path, scan_root), artifact_type=artifact_type
        )
    return SourceReference(
        path=stable_relative_path(flow_path, scan_root),
        artifact_type=artifact_type,
        xml_path=_xml_path(element),
        line=element.sourceline,
    )


def _xml_path(element: etree._Element) -> str:
    parts: list[str] = []
    current: etree._Element | None = element
    while current is not None and isinstance(current.tag, str):
        parent = current.getparent()
        if parent is None:
            index = 1
        else:
            siblings = [
                child
                for child in parent
                if isinstance(child.tag, str) and child.tag == current.tag
            ]
            index = siblings.index(current) + 1
        parts.append(f"{current.tag}[{index}]")
        current = parent
    return "/" + "/".join(reversed(parts))


def _xml_finding(
    exc: Exception, path: Path, scan_root: Path, artifact_type: str
) -> AnalysisFinding:
    code = "XML_UNSAFE" if isinstance(exc, XmlSecurityError) else "XML_MALFORMED"
    return AnalysisFinding(
        status=FindingStatus.MALFORMED,
        code=code,
        message=str(exc),
        source=SourceReference(
            path=stable_relative_path(path, scan_root), artifact_type=artifact_type
        ),
    )


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_optional(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.casefold() == "true"


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _extraction_policy_snapshot(config: AppConfig) -> ExtractionPolicySnapshot:
    return ExtractionPolicySnapshot(
        literal_mode=config.extraction.literals.mode.value,
        free_text_mode=config.extraction.freeText.mode.value,
    )


def _classified_attributes(
    *,
    element: etree._Element,
    source: SourceReference,
    config: AppConfig,
    technical_names: set[str],
    free_text_names: set[str],
) -> tuple[dict[str, str], dict[str, TextValue], list[AttributeValue]]:
    technical_attrs: dict[str, str] = {}
    text_attrs: dict[str, TextValue] = {}
    unknown_attrs: list[AttributeValue] = []
    for name, value in sorted(element.attrib.items()):
        if name in technical_names:
            technical_attrs[name] = value
            continue
        if name in free_text_names or _is_free_text_attribute_name(name):
            text_value = _apply_free_text_policy(
                value, f"{element.tag}.{name}", source, config, name
            )
            if text_value is not None:
                text_attrs[name] = text_value
            continue
        unknown_attrs.append(_unknown_attribute(name, value, source, config))
    return technical_attrs, text_attrs, unknown_attrs


def _unknown_attribute(
    name: str, value: str, source: SourceReference, config: AppConfig
) -> AttributeValue:
    secret = _is_secret_context(name, value)
    if config.extraction.freeText.mode == ExtractionMode.OMIT:
        disclosure = TextDisclosure.OMITTED
        marker = None
    elif secret:
        disclosure = TextDisclosure.BLOCKED_SECRET
        marker = "<redacted:secret-attribute>"
    else:
        disclosure = TextDisclosure.REDACTED
        marker = "<redacted:attribute>"
    return AttributeValue(
        name=name,
        classification=(
            AttributeClassification.SECRET_SENSITIVE_TEXT
            if secret
            else AttributeClassification.UNKNOWN
        ),
        text=TextValue(
            present=True,
            role=f"unknown_attribute.{name}",
            disclosure=disclosure,
            length=None if config.extraction.freeText.mode == ExtractionMode.OMIT else len(value),
            marker=marker,
            source=source,
        ),
        source=source,
    )


def _is_free_text_attribute_name(name: str) -> bool:
    normalized = name.upper().replace("_", "-")
    return (
        normalized in FREE_TEXT_ATTRIBUTE_NAMES
        or normalized.endswith("-COMMENT")
        or normalized.endswith("-DESCRIPTION")
        or normalized.endswith("-LABEL")
        or normalized.endswith("-NOTE")
        or normalized.endswith("-TITLE")
    )


def _apply_free_text_policy(
    value: str | None,
    role: str,
    source: SourceReference,
    config: AppConfig,
    *context: str | None,
) -> TextValue | None:
    if value is None:
        return None
    secret = _is_secret_context(value, role, *context)
    if config.extraction.freeText.mode == ExtractionMode.OMIT:
        return TextValue(
            present=True,
            role=role,
            disclosure=TextDisclosure.OMITTED,
            source=source,
        )
    if secret:
        return TextValue(
            present=True,
            role=role,
            disclosure=TextDisclosure.BLOCKED_SECRET,
            length=len(value),
            marker="<redacted:secret-free-text>",
            source=source,
        )
    if config.extraction.freeText.mode == ExtractionMode.REDACT:
        return TextValue(
            present=True,
            role=role,
            disclosure=TextDisclosure.REDACTED,
            length=len(value),
            marker="<redacted:free-text>",
            source=source,
        )
    return TextValue(
        present=True,
        role=role,
        disclosure=TextDisclosure.INCLUDED,
        length=len(value),
        value=value,
        source=source,
    )


def _is_secret_context(*values: str | None) -> bool:
    combined = " ".join(value.casefold() for value in values if value)
    return any(term in combined for term in SECRET_TERMS)


def _call_key(call: CallOccurrence) -> tuple[str, int, str, str]:
    return (call.caller.casefold(), call.order, call.id, call.target.casefold())


def _unique_dependency_key(dependency: UniqueDependency) -> tuple[str, str, str]:
    return (
        dependency.source_service.casefold(),
        dependency.dependency_kind.value,
        dependency.target_service.casefold(),
    )


def _flow_map_key(flow_map: FlowMap) -> tuple[str, int, str, str]:
    return (
        flow_map.service.casefold(),
        flow_map.order,
        flow_map.structural_path,
        flow_map.id,
    )


def _mapping_operation_key(operation: MappingOperation) -> tuple[str, int, str, str]:
    return (
        operation.service.casefold(),
        operation.order,
        operation.structural_path,
        operation.id,
    )


def _transformer_binding_key(binding: TransformerBinding) -> tuple[str, int, str, str]:
    return (
        binding.service.casefold(),
        binding.order,
        binding.structural_path,
        binding.id,
    )


def _document_type_key(document: DocumentType) -> tuple[str, str]:
    return (document.identity.full_name.casefold(), document.id)


def _document_reference_key(
    reference: DocumentReferenceOccurrence,
) -> tuple[str, str, str, str, str]:
    return (
        reference.owner_kind.value,
        reference.owner_name.casefold(),
        reference.source_field_path.casefold(),
        reference.declared_target.casefold(),
        reference.id,
    )


def _document_dependency_key(dependency: DocumentDependency) -> tuple[str, str, str]:
    return (
        dependency.source_document.casefold(),
        dependency.target_document.casefold(),
        dependency.id,
    )


def _service_document_dependency_key(
    dependency: ServiceDocumentDependency,
) -> tuple[str, str, str, str]:
    return (
        dependency.service.casefold(),
        dependency.target_document.casefold(),
        dependency.usage_role.value,
        dependency.id,
    )


def _java_service_analysis_key(analysis: JavaServiceAnalysis) -> tuple[str, str]:
    return (analysis.identity.full_name.casefold(), analysis.id)


def _java_import_key(java_import: JavaImport) -> tuple[str, int, str]:
    return (
        java_import.service.casefold(),
        java_import.declaration_order,
        java_import.declaration.casefold(),
    )


def _java_type_reference_key(reference: JavaTypeReference) -> tuple[str, int, str]:
    return (
        reference.service.casefold(),
        reference.token_ordinal,
        reference.type_name.casefold(),
    )


def _java_pipeline_access_key(access: JavaPipelineAccess) -> tuple[str, int, str]:
    return (access.service.casefold(), access.token_ordinal, access.id)


def _java_invocation_key(invocation: JavaInvocationOccurrence) -> tuple[str, int, str]:
    return (invocation.caller.casefold(), invocation.token_ordinal, invocation.id)


def _finding_key(finding: AnalysisFinding) -> tuple[str, str, str]:
    return (finding.source.path.casefold(), finding.code, finding.message)


def _aggregate_findings(findings: list[AnalysisFinding]) -> list[AnalysisFinding]:
    grouped: dict[tuple[str, str, str, str | None], list[AnalysisFinding]] = defaultdict(list)
    passthrough: list[AnalysisFinding] = []
    for finding in findings:
        if finding.code not in AGGREGATABLE_FINDINGS:
            passthrough.append(finding)
            continue
        grouped[
            (
                finding.code,
                finding.message,
                finding.source.path,
                finding.source.artifact_type,
            )
        ].append(finding)

    aggregated: list[AnalysisFinding] = []
    for group in grouped.values():
        ordered = sorted(group, key=_finding_key)
        first = ordered[0]
        samples = [finding.source for finding in ordered[:SOURCE_SAMPLE_LIMIT]]
        aggregated.append(
            first.model_copy(
                update={
                    "occurrence_count": len(ordered),
                    "sample_source_references": samples,
                }
            )
        )
    return sorted([*passthrough, *aggregated], key=_finding_key)
