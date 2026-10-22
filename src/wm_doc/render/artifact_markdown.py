"""Inventory page for namespace nodes that are not analysed services or documents."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from wm_doc.ir import AnalysisResult, NamespaceArtifact, ServiceType

ARTIFACTS_MARKDOWN = "artifacts.md"
MAX_EXAMPLES = 5


def artifact_kind(artifact: NamespaceArtifact) -> str:
    """The node type as declared, or the discovery classification when none is declared."""
    return artifact.node_type or artifact.probable_type


def render_artifact_inventory(analysis: AnalysisResult) -> str:
    by_kind: dict[str, list[NamespaceArtifact]] = defaultdict(list)
    for artifact in analysis.namespace_artifacts:
        by_kind[artifact_kind(artifact)].append(artifact)
    opaque = [
        service
        for package in analysis.packages
        for service in package.services
        if service.service_type is ServiceType.OPAQUE
    ]
    opaque_types = Counter(service.source_service_type or "<not declared>" for service in opaque)

    lines = [
        "# Other Artifacts",
        "",
        (
            "Namespace nodes that are not analysed services or document types: for example "
            "triggers, REST and SOAP descriptors, adapter connections and notifications, and "
            "specifications. They are listed by the node type declared in their `node.ndf`; "
            "their content is not interpreted."
        ),
        "",
        "## By node type",
        "",
    ]
    if by_kind:
        lines += ["| Node type | Count |", "| --- | ---: |"]
        lines += [
            f"| `{kind}` | {len(by_kind[kind])} |" for kind in sorted(by_kind, key=str.casefold)
        ]
    else:
        lines.append("No other namespace artifacts were found.")
    lines += ["", "## Opaque services by service type", ""]
    if opaque_types:
        lines += [
            (
                "Services whose `svc_type` is not FLOW or Java, such as adapter services. Only "
                "their name and signature are documented."
            ),
            "",
            "| Service type | Count | Examples |",
            "| --- | ---: | --- |",
        ]
        for service_type in sorted(opaque_types, key=str.casefold):
            examples = sorted(
                service.identity.full_name
                for service in opaque
                if (service.source_service_type or "<not declared>") == service_type
            )[:MAX_EXAMPLES]
            shown = ", ".join(f"`{name}`" for name in examples)
            lines.append(f"| `{service_type}` | {opaque_types[service_type]} | {shown} |")
    else:
        lines.append("No opaque services were found.")
    for kind in sorted(by_kind, key=str.casefold):
        lines += ["", f"## `{kind}`", "", "| Name | Package | Source |", "| --- | --- | --- |"]
        for artifact in by_kind[kind]:
            lines.append(
                f"| `{artifact.full_name}` | `{artifact.package}` | `{artifact.source.path}` |"
            )
    lines += ["", "## Skipped packages", ""]
    if analysis.excluded_packages:
        lines += ["| Package | Reason |", "| --- | --- |"]
        lines += [
            f"| `{package.name}` | {package.reason} |" for package in analysis.excluded_packages
        ]
    else:
        lines.append("No packages were skipped.")
    lines.append("")
    return "\n".join(lines)


def write_artifact_inventory(output_dir: Path, analysis: AnalysisResult) -> Path:
    path = output_dir / ARTIFACTS_MARKDOWN
    path.write_text(render_artifact_inventory(analysis), encoding="utf-8")
    return path
