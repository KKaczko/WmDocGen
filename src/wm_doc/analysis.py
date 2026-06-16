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
    ExtractionPolicySnapshot,
    FactBasis,
    FindingStatus,
    FlowMap,
    FlowNode,
    FlowNodeType,
    FlowService,
    InterpretationConfidence,
    LiteralDisclosure,
    LiteralValue,
    MappingEndpoint,
    MappingOperation,
    MappingOperationType,
    MapSchemaMetadata,
    PackageInventory,
    PipelinePath,
    ServiceIdentity,
    ServiceSignature,
    ServiceSummary,
    ServiceType,
    SignatureField,
    SourceReference,
    TextDisclosure,
    TextValue,
    TransformerBinding,
    TransformerBindingDirection,
    UniqueDependency,
    stable_relative_path,
)
from wm_doc.values import parse_values_file, scalar_value
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file

ANALYZABLE_FLOW_ARTIFACTS = {"flow_service", "flow_service_metadata_without_flow"}
SERVICE_INDEX_ARTIFACTS = {"flow_service", "java_service"}
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
    "ID_COLLISION_RESOLVED",
    "MISSING_LITERAL_DATA",
    "ORPHAN_MAPSOURCE",
    "ORPHAN_MAPTARGET",
    "PARTIAL_MAPPING_INTERPRETATION",
    "SECRET_LITERAL_REDACTED",
    "UNKNOWN_MAPPING_ATTRIBUTE",
    "UNKNOWN_MAPPING_CHILD",
    "UNSUPPORTED_LITERAL_ENCODING",
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


def analyze_path(path: Path, config: AppConfig) -> AnalysisResult:
    scan_root = path.resolve()
    inventory = scan_path(scan_root)
    service_index = _build_service_index(inventory.packages)
    extraction_policy = _extraction_policy_snapshot(config)
    id_factory = StableIdFactory()
    service_classifications: dict[str, ClassificationResult] = {}
    package_services: dict[str, list[FlowService]] = {}
    pending_services: list[FlowService] = []
    all_findings: list[AnalysisFinding] = list(inventory.findings)

    package_shells: list[AnalyzedPackage] = []
    for package in inventory.packages:
        package_findings = sorted(package.findings, key=_finding_key)
        services: list[FlowService] = []
        for artifact in package.artifacts:
            if artifact.probable_type not in ANALYZABLE_FLOW_ARTIFACTS:
                continue
            service = _parse_flow_service(
                scan_root, package.name, artifact, config, extraction_policy, id_factory
            )
            services.append(service)
            pending_services.append(service)
            service_classifications[service.identity.full_name] = service.classification
        package_services[package.name] = services
        all_findings.extend(package_findings)
        package_shells.append(
            AnalyzedPackage(
                name=package.name,
                root=package.root,
                services=[],
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
                ),
                "findings": _aggregate_findings(service.findings),
            }
        )
        all_calls.extend(resolved_calls)
        all_unique_dependencies.extend(unique_dependencies)
        all_flow_maps.extend(service.flow_maps)
        all_mapping_operations.extend(service.mapping_operations)
        all_transformer_bindings.extend(service.transformer_bindings)
        resolved_services[service.identity.package].append(service)

    all_findings.extend(id_factory.findings)
    final_packages: list[AnalyzedPackage] = []
    for analyzed_package in package_shells:
        final_packages.append(
            analyzed_package.model_copy(
                update={
                    "services": sorted(
                        resolved_services.get(analyzed_package.name, []),
                        key=lambda item: item.identity.full_name.casefold(),
                    )
                }
            )
        )

    all_calls = sorted(all_calls, key=_call_key)
    all_unique_dependencies = sorted(all_unique_dependencies, key=_unique_dependency_key)
    all_flow_maps = sorted(all_flow_maps, key=_flow_map_key)
    all_mapping_operations = sorted(all_mapping_operations, key=_mapping_operation_key)
    all_transformer_bindings = sorted(all_transformer_bindings, key=_transformer_binding_key)
    return AnalysisResult(
        tool_version=__version__,
        packages=sorted(final_packages, key=lambda item: item.name.casefold()),
        metrics=_top_level_metrics(
            all_calls,
            all_unique_dependencies,
            all_flow_maps,
            all_mapping_operations,
            all_transformer_bindings,
            final_packages,
        ),
        extraction_policy=extraction_policy,
        call_occurrences=all_calls,
        unique_dependencies=all_unique_dependencies,
        flow_maps=all_flow_maps,
        mapping_operations=all_mapping_operations,
        transformer_bindings=all_transformer_bindings,
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
            service_type = (
                ServiceType.FLOW if artifact.probable_type == "flow_service" else ServiceType.JAVA
            )
            identity = ServiceIdentity(
                package=package.name,
                namespace=artifact.identity.namespace or "",
                name=artifact.identity.name or "",
                full_name=artifact.identity.full_name,
                basis=artifact.identity.basis,
                source=artifact.source,
            )
            index[identity.full_name] = ServiceSummary(
                identity=identity, service_type=service_type, source=artifact.source
            )
    return dict(sorted(index.items(), key=lambda item: item[0].casefold()))


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

    try:
        values = parse_values_file(node_path)
        description = _apply_free_text_policy(
            _blank_to_none(scalar_value(values, "node_comment")),
            "service_description",
            SourceReference(
                path=stable_relative_path(node_path, scan_root), artifact_type="node_comment"
            ),
            config,
            "node_comment",
        )
        node_root = parse_xml_file(node_path)
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


def _parse_signature(
    node_root: etree._Element, node_path: Path, scan_root: Path
) -> ServiceSignature:
    svc_sig = _record_child(node_root, "svc_sig")
    source = _element_source(node_path, scan_root, svc_sig, "service_signature")
    source = source.model_copy(update={"source_node": "/Values/record[@name='svc_sig']"})
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
                    "target_classification": target_classification,
                }
            )
        )
    return sorted(resolved_calls, key=_call_key), _aggregate_unique_dependencies(resolved_calls)


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
) -> AnalysisMetrics:
    call_type_counts = Counter(call.call_type.value for call in calls)
    unique_kind_counts = Counter(dep.dependency_kind.value for dep in unique_dependencies)
    mapping_type_counts = Counter(
        operation.operation_type.value for operation in mapping_operations
    )
    binding_direction_counts = Counter(
        binding.direction.value for binding in transformer_bindings
    )
    flow_node_counts = Counter[str]()
    if flow_tree is not None:
        _count_flow_nodes(flow_tree, flow_node_counts)
    return AnalysisMetrics(
        call_occurrence_count=len(calls),
        unique_dependency_count=len(unique_dependencies),
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
    )


def _top_level_metrics(
    calls: list[CallOccurrence],
    unique_dependencies: list[UniqueDependency],
    flow_maps: list[FlowMap],
    mapping_operations: list[MappingOperation],
    transformer_bindings: list[TransformerBinding],
    packages: list[AnalyzedPackage],
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
    for package in packages:
        for service in package.services:
            if service.flow_tree is not None:
                _count_flow_nodes(service.flow_tree, flow_node_counts)
    return metrics.model_copy(
        update={"flow_node_counts": dict(sorted(flow_node_counts.items()))}
    )


def _count_flow_nodes(node: FlowNode, counts: Counter[str]) -> None:
    counts[node.type.value] += 1
    for child in node.children:
        _count_flow_nodes(child, counts)


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
