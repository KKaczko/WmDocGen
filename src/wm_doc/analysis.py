from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path

from lxml import etree

from wm_doc import __version__
from wm_doc.config import AppConfig, classify_service
from wm_doc.discovery import scan_path
from wm_doc.ir import (
    AnalysisFinding,
    AnalysisMetrics,
    AnalysisResult,
    AnalyzedPackage,
    ArtifactCandidate,
    CallOccurrence,
    CallType,
    ClassificationResult,
    DependencyKind,
    FactBasis,
    FindingStatus,
    FlowNode,
    FlowNodeType,
    FlowService,
    PackageInventory,
    ServiceIdentity,
    ServiceSignature,
    ServiceSummary,
    ServiceType,
    SignatureField,
    SourceReference,
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
DEFERRED_MAP_ELEMENTS = {"MAPCOPY", "MAPSET", "MAPDELETE", "MAPSOURCE", "MAPTARGET", "DATA"}
SUPPORTED_EXIT_ATTRIBUTES = {"FROM", "SIGNAL", "FAILURE-MESSAGE"}
UNRESOLVED_SOURCE_SAMPLE_LIMIT = 3


def analyze_path(path: Path, config: AppConfig) -> AnalysisResult:
    scan_root = path.resolve()
    inventory = scan_path(scan_root)
    service_index = _build_service_index(inventory.packages)
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
            service = _parse_flow_service(scan_root, package.name, artifact, config)
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
    for service in pending_services:
        resolved_calls, unique_dependencies = _resolve_service_dependencies(
            service, service_index, service_classifications, config
        )
        service = service.model_copy(
            update={
                "call_occurrences": resolved_calls,
                "unique_dependencies": unique_dependencies,
                "metrics": _metrics(resolved_calls, unique_dependencies, service.flow_tree),
                "findings": sorted(service.findings, key=_finding_key),
            }
        )
        all_calls.extend(resolved_calls)
        all_unique_dependencies.extend(unique_dependencies)
        resolved_services[service.identity.package].append(service)

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
    return AnalysisResult(
        tool_version=__version__,
        packages=sorted(final_packages, key=lambda item: item.name.casefold()),
        metrics=_top_level_metrics(all_calls, all_unique_dependencies, final_packages),
        call_occurrences=all_calls,
        unique_dependencies=all_unique_dependencies,
        findings=sorted(all_findings, key=_finding_key),
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
    scan_root: Path, package_name: str, artifact: ArtifactCandidate, config: AppConfig
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
    description: str | None = None

    try:
        values = parse_values_file(node_path)
        description = _blank_to_none(scalar_value(values, "node_comment"))
        node_root = parse_xml_file(node_path)
        signature = _parse_signature(node_root, node_path, scan_root)
    except (XmlParseError, XmlSecurityError) as exc:
        findings.append(_xml_finding(exc, node_path, scan_root, "node_ndf"))

    flow_tree: FlowNode | None = None
    call_occurrences: list[CallOccurrence] = []
    if flow_path.exists():
        try:
            flow_tree, call_occurrences, flow_findings = _parse_flow_xml(
                flow_path, scan_root, identity, config
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
        metrics=_metrics(call_occurrences, [], flow_tree),
        call_occurrences=call_occurrences,
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
    flow_path: Path, scan_root: Path, identity: ServiceIdentity, config: AppConfig
) -> tuple[FlowNode | None, list[CallOccurrence], list[AnalysisFinding]]:
    root = parse_xml_file(flow_path)
    findings: list[AnalysisFinding] = []
    calls: list[CallOccurrence] = []
    unsupported_seen: set[str] = set()
    deferred_seen: set[str] = set()
    counters = {"node": 0, "call": 0}

    def next_node_id() -> str:
        counters["node"] += 1
        return f"fn{counters['node']:04d}"

    def next_call_id() -> str:
        counters["call"] += 1
        return f"call{counters['call']:04d}"

    def visit(
        element: etree._Element,
        parent_id: str | None,
        parent_path: list[str],
    ) -> list[FlowNode]:
        if not isinstance(element.tag, str):
            return []
        tag = element.tag
        if tag == "COMMENT":
            return []
        if tag in DEFERRED_MAP_ELEMENTS:
            if tag not in deferred_seen:
                deferred_seen.add(tag)
                findings.append(
                    AnalysisFinding(
                        status=FindingStatus.PARTIALLY_SUPPORTED,
                        code="MAP_OPERATION_DEFERRED",
                        message=f"FLOW element {tag} is deferred to M2b mapping semantics.",
                        source=_element_source(flow_path, scan_root, element, tag.lower()),
                    )
                )
            child_nodes: list[FlowNode] = []
            for child in element:
                child_nodes.extend(visit(child, parent_id, parent_path))
            return child_nodes
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
                child_nodes.extend(visit(child, parent_id, parent_path))
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
                call_occurrence_id = next_call_id()
                call_type = CALL_TAGS[tag]
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
                        source=_element_source(flow_path, scan_root, element, tag.lower()),
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

        children: list[FlowNode] = []
        for child in element:
            if (
                node_type == FlowNodeType.BRANCH
                and isinstance(child.tag, str)
                and child.tag != "COMMENT"
            ):
                label = child.get("NAME")
                case_id = next_node_id()
                case_path_parts = [*structural_path_parts, case_id]
                case_children = visit(child, case_id, case_path_parts)
                children.append(
                    FlowNode(
                        id=case_id,
                        type=FlowNodeType.BRANCH_CASE,
                        label=label,
                        is_default_case=label == "$default",
                        attributes={"source_type": child.tag},
                        parent_id=node_id,
                        structural_path="/".join(case_path_parts),
                        children=case_children,
                        source=_element_source(flow_path, scan_root, child, "branch_case"),
                    )
                )
            else:
                children.extend(visit(child, node_id, structural_path_parts))

        if node_type == FlowNodeType.EXIT:
            _validate_exit(element, flow_path, scan_root, findings)
        source = _element_source(flow_path, scan_root, element, tag.lower())
        node = FlowNode(
            id=node_id,
            type=node_type,
            label=element.get("NAME"),
            attributes=dict(sorted(element.attrib.items())),
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
    return flow_tree, sorted(calls, key=_call_key), sorted(findings, key=_finding_key)


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
) -> AnalysisMetrics:
    call_type_counts = Counter(call.call_type.value for call in calls)
    unique_kind_counts = Counter(dep.dependency_kind.value for dep in unique_dependencies)
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
    )


def _top_level_metrics(
    calls: list[CallOccurrence],
    unique_dependencies: list[UniqueDependency],
    packages: list[AnalyzedPackage],
) -> AnalysisMetrics:
    metrics = _metrics(calls, unique_dependencies, None)
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


def _call_key(call: CallOccurrence) -> tuple[str, int, str, str]:
    return (call.caller.casefold(), call.order, call.id, call.target.casefold())


def _unique_dependency_key(dependency: UniqueDependency) -> tuple[str, str, str]:
    return (
        dependency.source_service.casefold(),
        dependency.dependency_kind.value,
        dependency.target_service.casefold(),
    )


def _finding_key(finding: AnalysisFinding) -> tuple[str, str, str]:
    return (finding.source.path.casefold(), finding.code, finding.message)
