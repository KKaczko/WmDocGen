"""Inventory page for namespace nodes that are not analysed services or documents."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from wm_doc.effects import rest_v1_endpoint
from wm_doc.ir import AdapterRole, AnalysisResult, FlowService, NamespaceArtifact, ServiceType
from wm_doc.render.service_markdown import service_markdown_filename
from wm_doc.triggers import trigger_summary

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
            "specifications. They are listed by the node type declared in their `node.ndf`. "
            "Triggers and JDBC adapter services, connections and notifications are read for "
            "the facts in the sections below; other nodes are listed only."
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
    lines += _trigger_section(analysis)
    lines += _rest_v1_section(analysis)
    lines += _adapter_service_section(opaque)
    lines += _connection_section(analysis, opaque)
    lines += _notification_section(analysis)
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


def _link(name: str) -> str:
    return f"[`{name}`](services/{service_markdown_filename(name)})"


def _names(names: list[str], limit: int = 5) -> str:
    shown = ", ".join(f"`{name}`" for name in names[:limit])
    extra = len(names) - limit
    return shown + (f" and {extra} more" if extra > 0 else "") if names else "-"


def _trigger_section(analysis: AnalysisResult) -> list[str]:
    triggers = [a for a in analysis.namespace_artifacts if a.trigger is not None]
    if not triggers:
        return []
    services = {service.identity.full_name for service in analysis.services}
    lines = [
        "",
        "## Triggers",
        "",
        "| Trigger | Kind | Listens to | Handler services |",
        "| --- | --- | --- | --- |",
    ]
    for artifact in triggers:
        trigger = artifact.trigger
        assert trigger is not None
        handlers = sorted(
            {item.handler for item in trigger.subscriptions if item.handler}, key=str.casefold
        )
        shown = ", ".join(
            _link(name) if name in services else f"`{name}`" for name in handlers
        )
        lines.append(
            f"| `{artifact.full_name}` | {trigger.kind} | "
            f"{trigger_summary(trigger) or 'not determined'} | {shown or '-'} |"
        )
    return lines


def _rest_v1_section(analysis: AnalysisResult) -> list[str]:
    handlers = sorted(
        (
            (endpoint, service.identity.full_name)
            for service in analysis.services
            if (endpoint := rest_v1_endpoint(service.identity.full_name)) is not None
        ),
        key=lambda item: item[1].casefold(),
    )
    if not handlers:
        return []
    lines = [
        "",
        "## Legacy REST v1 handlers",
        "",
        "Services named `_get`, `_post`, `_put`, `_patch`, `_delete` or `_default` handle "
        "requests to `/rest/<namespace as path>`.",
        "",
        "| Endpoint | Service |",
        "| --- | --- |",
    ]
    lines += [f"| `{endpoint}` | {_link(name)} |" for endpoint, name in handlers]
    return lines


def _adapter_service_section(opaque: list[FlowService]) -> list[str]:
    adapters = sorted(
        (service for service in opaque if service.adapter is not None),
        key=lambda service: service.identity.full_name.casefold(),
    )
    if not adapters:
        return []
    lines = [
        "",
        "## JDBC adapter services",
        "",
        "| Service | Operation | Tables | Connection |",
        "| --- | --- | --- | --- |",
    ]
    for service in adapters:
        details = service.adapter
        assert details is not None
        lines.append(
            f"| {_link(service.identity.full_name)} | `{details.operation or '?'}` | "
            f"{_names(details.tables)} | `{details.connection or 'not determined'}` |"
        )
    return lines


def _connection_section(analysis: AnalysisResult, opaque: list[FlowService]) -> list[str]:
    connections = [
        a
        for a in analysis.namespace_artifacts
        if a.adapter is not None and a.adapter.role is AdapterRole.CONNECTION
    ]
    if not connections:
        return []
    users: dict[str, int] = Counter(
        service.adapter.connection
        for service in opaque
        if service.adapter is not None and service.adapter.connection
    )
    lines = [
        "",
        "## JDBC connections",
        "",
        "Only the database product, database name and transaction type are read; server, "
        "port, user, password and other connection properties are not.",
        "",
        "| Connection | Database product | Database name | Transactions | Adapter services |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for artifact in connections:
        details = artifact.adapter
        assert details is not None
        lines.append(
            f"| `{artifact.full_name}` | {details.database_product or 'not recognised'} | "
            f"`{details.database_name or '-'}` | `{details.transaction_type or '-'}` | "
            f"{users.get(artifact.full_name, 0)} |"
        )
    return lines


def _notification_section(analysis: AnalysisResult) -> list[str]:
    notifications = [
        a
        for a in analysis.namespace_artifacts
        if a.adapter is not None and a.adapter.role is AdapterRole.NOTIFICATION
    ]
    if not notifications:
        return []
    lines = [
        "",
        "## JDBC adapter notifications",
        "",
        "| Notification | Type | Tables | Connection | Publishes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for artifact in notifications:
        details = artifact.adapter
        assert details is not None
        lines.append(
            f"| `{artifact.full_name}` | `{details.operation or '?'}` | {_names(details.tables)} | "
            f"`{details.connection or 'not determined'}` | "
            f"`{details.published_document or 'not determined'}` |"
        )
    return lines


def write_artifact_inventory(output_dir: Path, analysis: AnalysisResult) -> Path:
    path = output_dir / ARTIFACTS_MARKDOWN
    path.write_text(render_artifact_inventory(analysis), encoding="utf-8")
    return path
