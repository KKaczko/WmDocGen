from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from lxml import etree

from wm_doc import __version__
from wm_doc.config import AppConfig, classify_service
from wm_doc.discovery import scan_path
from wm_doc.ir import (
    AnalysisFinding,
    AnalysisResult,
    AnalyzedPackage,
    ArtifactCandidate,
    ClassificationResult,
    DependencyEdge,
    DependencyType,
    FactBasis,
    FindingStatus,
    FlowContainer,
    FlowInvoke,
    FlowService,
    PackageInventory,
    ServiceIdentity,
    ServiceSignature,
    ServiceSummary,
    ServiceType,
    SignatureField,
    SourceReference,
    UnresolvedDependency,
    stable_relative_path,
)
from wm_doc.values import ValuesData, parse_values_file, record_value, scalar_value
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file

SUPPORTED_FLOW_CONTAINERS = {"FLOW", "SEQUENCE", "BRANCH", "LOOP", "REPEAT"}
SUPPORTED_INVOKE_ELEMENTS = {"INVOKE", "MAPINVOKE"}
ANALYZABLE_FLOW_ARTIFACTS = {"flow_service", "flow_service_metadata_without_flow"}


def analyze_path(path: Path, config: AppConfig) -> AnalysisResult:
    scan_root = path.resolve()
    inventory = scan_path(scan_root)
    service_index = _build_service_index(inventory.packages)
    packages: list[AnalyzedPackage] = []
    all_edges: list[DependencyEdge] = []
    all_unresolved: list[UnresolvedDependency] = []
    all_findings: list[AnalysisFinding] = list(inventory.findings)

    service_classifications: dict[str, ClassificationResult] = {}
    pending_services: list[FlowService] = []
    package_services: dict[str, list[FlowService]] = {}

    for package in inventory.packages:
        package_findings = list(package.findings)
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
        packages.append(
            AnalyzedPackage(
                name=package.name,
                root=package.root,
                services=[],
                service_index=sorted(
                    service_index.values(), key=lambda item: item.identity.full_name.casefold()
                ),
                findings=sorted(package_findings, key=_finding_key),
            )
        )

    resolved_services: dict[str, list[FlowService]] = {name: [] for name in package_services}
    for service in pending_services:
        edges, unresolved = _resolve_dependencies(
            service, service_index, service_classifications, config
        )
        all_edges.extend(edges)
        all_unresolved.extend(unresolved)
        service = service.model_copy(
            update={
                "dependencies": edges,
                "unresolved_dependencies": unresolved,
                "findings": sorted(service.findings, key=_finding_key),
            }
        )
        resolved_services[service.identity.package].append(service)

    final_packages: list[AnalyzedPackage] = []
    for analyzed_package in packages:
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

    return AnalysisResult(
        tool_version=__version__,
        packages=sorted(final_packages, key=lambda item: item.name.casefold()),
        edges=sorted(all_edges, key=_edge_key),
        unresolved_dependencies=sorted(all_unresolved, key=_unresolved_key),
        findings=sorted(all_findings, key=_finding_key),
    )


def _build_service_index(packages: Iterable[PackageInventory]) -> dict[str, ServiceSummary]:
    index: dict[str, ServiceSummary] = {}
    for package in packages:
        for artifact in package.artifacts:
            if artifact.probable_type not in {"flow_service", "java_service"}:
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
        unresolved_source = artifact.source
        identity = ServiceIdentity(
            package=package_name,
            namespace="",
            name=artifact.relative_path.rsplit("/", 1)[-1],
            full_name=artifact.relative_path,
            basis=FactBasis.UNRESOLVED,
            source=unresolved_source,
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
        signature = _parse_signature(values, node_path, scan_root)
    except (XmlParseError, XmlSecurityError) as exc:
        findings.append(_xml_finding(exc, node_path, scan_root, "node_ndf"))

    containers: list[FlowContainer] = []
    invokes: list[FlowInvoke] = []
    if flow_path.exists():
        try:
            containers, invokes, flow_findings = _parse_flow_xml(flow_path, scan_root)
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
        containers=containers,
        invokes=invokes,
        findings=findings,
        source=artifact.source,
    )


def _parse_signature(values: ValuesData, node_path: Path, scan_root: Path) -> ServiceSignature:
    source = SourceReference(
        path=stable_relative_path(node_path, scan_root),
        artifact_type="service_signature",
        xml_path="/Values/record[@name='svc_sig']",
    )
    svc_sig = record_value(values, "svc_sig") or {}
    sig_in = record_value(svc_sig, "sig_in") or {}
    sig_out = record_value(svc_sig, "sig_out") or {}
    return ServiceSignature(
        inputs=_parse_signature_fields(sig_in, node_path, scan_root, "sig_in"),
        outputs=_parse_signature_fields(sig_out, node_path, scan_root, "sig_out"),
        source=source,
    )


def _parse_signature_fields(
    record: ValuesData, node_path: Path, scan_root: Path, direction: str
) -> list[SignatureField]:
    raw_fields = record.get("rec_fields")
    if not isinstance(raw_fields, list):
        return []
    fields = [
        _parse_signature_field(field, node_path, scan_root, f"{direction}/rec_fields[{index}]")
        for index, field in enumerate(raw_fields, start=1)
        if isinstance(field, dict)
    ]
    return sorted(fields, key=lambda item: item.name.casefold())


def _parse_signature_field(
    field: ValuesData, node_path: Path, scan_root: Path, xml_suffix: str
) -> SignatureField:
    name = scalar_value(field, "field_name") or "<unnamed>"
    raw_children = field.get("rec_fields")
    children: list[SignatureField] = []
    if isinstance(raw_children, list):
        children = [
            _parse_signature_field(
                child, node_path, scan_root, f"{xml_suffix}/rec_fields[{index}]"
            )
            for index, child in enumerate(raw_children, start=1)
            if isinstance(child, dict)
        ]
    return SignatureField(
        name=name,
        data_type=scalar_value(field, "field_type"),
        dimensions=_parse_int(scalar_value(field, "field_dim")),
        optional=_parse_optional(scalar_value(field, "field_opt")),
        document_reference=scalar_value(field, "rec_ref"),
        wrapper_type=scalar_value(field, "wrapper_type"),
        children=sorted(children, key=lambda item: item.name.casefold()),
        source=SourceReference(
            path=stable_relative_path(node_path, scan_root),
            artifact_type="signature_field",
            xml_path=f"/Values/record[@name='svc_sig']/{xml_suffix}",
        ),
    )


def _parse_flow_xml(
    flow_path: Path, scan_root: Path
) -> tuple[list[FlowContainer], list[FlowInvoke], list[AnalysisFinding]]:
    root = parse_xml_file(flow_path)
    containers: list[FlowContainer] = []
    invokes: list[FlowInvoke] = []
    findings: list[AnalysisFinding] = []
    unsupported_seen: set[str] = set()
    counters = {"container": 0, "invoke": 0}

    def next_id(kind: str) -> str:
        counters[kind] += 1
        return f"{kind[0]}{counters[kind]:04d}"

    def visit(element: etree._Element, stack: list[FlowContainer]) -> None:
        if not isinstance(element.tag, str):
            return
        tag = element.tag
        if tag == "COMMENT":
            return
        if tag in SUPPORTED_FLOW_CONTAINERS:
            container = FlowContainer(
                id=next_id("container"),
                type=tag,
                name=element.get("NAME"),
                comment=_element_comment(element),
                attributes=dict(sorted(element.attrib.items())),
                parent_id=stack[-1].id if stack else None,
                source=_element_source(flow_path, scan_root, element, tag.lower()),
            )
            containers.append(container)
            for child in element:
                visit(child, [*stack, container])
            return
        if tag in SUPPORTED_INVOKE_ELEMENTS:
            target = element.get("SERVICE")
            if target:
                invoke_id = next_id("invoke")
                invokes.append(
                    FlowInvoke(
                        id=invoke_id,
                        type=tag,
                        target=target,
                        static=True,
                        comment=_element_comment(element),
                        parent_containers=[container.id for container in stack],
                        structural_path="/".join(
                            [container.id for container in stack] + [invoke_id]
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
            for child in element:
                visit(child, stack)
            return
        if tag.isupper() and tag not in unsupported_seen:
            unsupported_seen.add(tag)
            findings.append(
                AnalysisFinding(
                    status=FindingStatus.PARTIALLY_SUPPORTED,
                    code="UNSUPPORTED_FLOW_ELEMENT",
                    message=f"FLOW element {tag} is observed but not interpreted in M1.",
                    source=_element_source(flow_path, scan_root, element, tag.lower()),
                )
            )
        for child in element:
            visit(child, stack)

    visit(root, [])
    return containers, invokes, sorted(findings, key=_finding_key)


def _resolve_dependencies(
    service: FlowService,
    service_index: dict[str, ServiceSummary],
    service_classifications: dict[str, ClassificationResult],
    config: AppConfig,
) -> tuple[list[DependencyEdge], list[UnresolvedDependency]]:
    edges: list[DependencyEdge] = []
    unresolved: list[UnresolvedDependency] = []
    for invoke in service.invokes:
        target_summary = service_index.get(invoke.target)
        target_name = invoke.target.rsplit(":", 1)[-1]
        target_classification = service_classifications.get(invoke.target)
        if target_classification is None:
            target_classification = classify_service(invoke.target, target_name, config)
        edge = DependencyEdge(
            source_service=service.identity.full_name,
            target_service=invoke.target,
            dependency_type=DependencyType.INVOKES,
            resolved=target_summary is not None,
            target_type=target_summary.service_type if target_summary is not None else None,
            target_classification=target_classification,
            invoke_id=invoke.id,
            source=invoke.source,
        )
        edges.append(edge)
        if target_summary is None:
            unresolved.append(
                UnresolvedDependency(
                    source_service=service.identity.full_name,
                    target_service=invoke.target,
                    dependency_type=DependencyType.INVOKES,
                    invoke_id=invoke.id,
                    source=invoke.source,
                )
            )
    return sorted(edges, key=_edge_key), sorted(unresolved, key=_unresolved_key)


def _element_comment(element: etree._Element) -> str | None:
    child = element.find("COMMENT")
    if child is None:
        return None
    return _blank_to_none(child.text)


def _element_source(
    flow_path: Path, scan_root: Path, element: etree._Element, artifact_type: str
) -> SourceReference:
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


def _edge_key(edge: DependencyEdge) -> tuple[str, str, str]:
    return (edge.source_service.casefold(), edge.invoke_id, edge.target_service.casefold())


def _unresolved_key(unresolved: UnresolvedDependency) -> tuple[str, str, str]:
    return (
        unresolved.source_service.casefold(),
        unresolved.invoke_id,
        unresolved.target_service.casefold(),
    )


def _finding_key(finding: AnalysisFinding) -> tuple[str, str, str]:
    return (finding.source.path.casefold(), finding.code, finding.message)
