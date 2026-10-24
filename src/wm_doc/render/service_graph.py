"""One small call graph per service: who reaches it, what it calls, and where data goes."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from wm_doc.builtins import builtin_effect, is_builtin_name
from wm_doc.effects import REST_V1_KIND, ServiceFacts, rest_v1_method
from wm_doc.external_systems import EMPTY_CATALOG, ExternalSystemCatalog, system_label
from wm_doc.ir import AnalysisResult, FlowService, Importance, ReferenceTargetKind, ServiceType
from wm_doc.render.dot import _escape, _node_id

SERVICE_GRAPH_DIR = "graphs/services"
MAX_CALLERS = 8
MAX_CALLEES = 14
MAX_REFERRERS = 6


class ServiceGraphContext:
    """Lookups shared by every service graph of one analysis."""

    def __init__(
        self,
        analysis: AnalysisResult,
        external_systems: ExternalSystemCatalog = EMPTY_CATALOG,
    ) -> None:
        self.services = {service.identity.full_name: service for service in analysis.services}
        self.external_systems = external_systems
        self.referrers: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.connections: dict[str, list[str]] = defaultdict(list)
        for service in analysis.services:
            method = rest_v1_method(service.identity.full_name)
            if method is not None:
                # The /rest/... path is left out: SVG output must not contain path-like text.
                label = f"HTTP {method}" if not method.startswith("any") else "other HTTP methods"
                self.referrers[service.identity.full_name].append((REST_V1_KIND, label))
        for reference in analysis.artifact_references:
            if reference.target_kind is ReferenceTargetKind.SERVICE:
                item = (reference.source_kind, reference.source_name)
                if item not in self.referrers[reference.target_name]:
                    self.referrers[reference.target_name].append(item)
            elif reference.target_kind is ReferenceTargetKind.ARTIFACT:
                if reference.target_name not in self.connections[reference.source_name]:
                    self.connections[reference.source_name].append(reference.target_name)


def render_service_graph_dot(
    service: FlowService, facts: ServiceFacts, context: ServiceGraphContext
) -> str:
    name = service.identity.full_name
    lines = [
        "digraph service {",
        "  rankdir=LR;",
        '  node [shape=box, fontsize=10, fontname="Helvetica"];',
        "  edge [fontsize=9];",
        f'  {_node_id(name)} [label="{_escape(name)}", style="filled,bold", '
        'fillcolor="#dbeafe", kind="service"];',
    ]

    referrers = sorted(context.referrers.get(name, []), key=lambda item: item[1].casefold())
    for kind, source in referrers[:MAX_REFERRERS]:
        node = _node_id(f"artifact\0{source}")
        lines.append(
            f'  {node} [label="{_escape(source)}\\n({_escape(kind)})", shape=cds, '
            'kind="entry_artifact"];'
        )
        lines.append(f'  {node} -> {_node_id(name)} [label="starts", kind="reference"];')
    _overflow(lines, len(referrers) - MAX_REFERRERS, "more artifacts", name, incoming=True)

    callers = list(facts.callers)
    for caller in callers[:MAX_CALLERS]:
        lines.append(f'  {_node_id(caller)} [label="{_escape(caller)}", kind="caller"];')
        lines.append(f'  {_node_id(caller)} -> {_node_id(name)} [kind="calls"];')
    _overflow(lines, len(callers) - MAX_CALLERS, "more callers", name, incoming=True)

    ranked: list[tuple[int, str]] = []
    platform_helpers = 0
    seen: set[str] = set()
    for dependency in service.unique_dependencies:
        target = dependency.target_service
        if target in seen or target == name:
            continue
        seen.add(target)
        effect = builtin_effect(target)
        if is_builtin_name(target):
            if effect is None or effect.data is None:
                platform_helpers += 1
                continue
        elif dependency.target_classification.importance is Importance.LOW:
            platform_helpers += 1  # utilities by the classification config
            continue
        ranked.append((_callee_rank(target, context), target))
    callees = [target for _rank, target in sorted(ranked, key=lambda item: (item[0], item[1]))]
    for target in callees[:MAX_CALLEES]:
        lines.extend(_callee_lines(name, target, facts, context))
    _overflow(lines, len(callees) - MAX_CALLEES, "more called services", name, incoming=False)
    if platform_helpers:
        node = _node_id(f"helpers\0{name}")
        lines.append(
            f'  {node} [label="{platform_helpers} helper call(s)", style=dotted, '
            'kind="helpers"];'
        )
        lines.append(f"  {_node_id(name)} -> {node} [style=dotted];")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _callee_lines(
    name: str, target: str, facts: ServiceFacts, context: ServiceGraphContext
) -> list[str]:
    node = _node_id(target)
    effect = builtin_effect(target)
    if effect is not None and effect.data is not None:
        # Only the action and the system: literal locations (URLs, file paths, queue names)
        # stay in the page's table and never enter rendered images.
        label = f"{_escape(effect.label)}\\n{_escape(effect.data.system)}"
        return [
            f'  {node} [label="{label}", shape=note, kind="platform_effect"];',
            f"  {_node_id(name)} -> {node};",
        ]
    callee = context.services.get(target)
    if callee is None:
        system = context.external_systems.match(target)
        suffix = f"\\n{_escape(system_label(system))}" if system is not None else ""
        return [
            f'  {node} [label="{_escape(target)}{suffix}", style=dashed, kind="external"];',
            f"  {_node_id(name)} -> {node};",
        ]
    if callee.service_type is ServiceType.OPAQUE:
        lines = [
            f'  {node} [label="{_escape(target)}\\n({_escape(callee.source_service_type or "")})", '
            'shape=component, kind="opaque_service"];',
            f"  {_node_id(name)} -> {node};",
        ]
        for connection in sorted(context.connections.get(target, []), key=str.casefold):
            connection_node = _node_id(f"connection\0{connection}")
            lines.append(
                f'  {connection_node} [label="{_escape(connection)}", shape=cylinder, '
                'kind="connection"];'
            )
            lines.append(f'  {node} -> {connection_node} [label="uses", kind="reference"];')
        return lines
    return [
        f'  {node} [label="{_escape(target)}", kind="service"];',
        f"  {_node_id(name)} -> {node};",
    ]


def _callee_rank(target: str, context: ServiceGraphContext) -> int:
    """Data-moving calls first, then services in the analysed packages, then outside calls."""
    effect = builtin_effect(target)
    if effect is not None and effect.data is not None:
        return 0
    callee = context.services.get(target)
    if callee is not None and callee.service_type is ServiceType.OPAQUE:
        return 0
    if callee is not None:
        return 1
    return 2


def _overflow(lines: list[str], extra: int, label: str, name: str, *, incoming: bool) -> None:
    if extra <= 0:
        return
    node = _node_id(f"{label}\0{name}")
    lines.append(f'  {node} [label="+{extra} {label}", style=dotted, kind="overflow"];')
    edge = f"{node} -> {_node_id(name)}" if incoming else f"{_node_id(name)} -> {node}"
    lines.append(f"  {edge} [style=dotted];")


def write_service_graphs(
    output_dir: Path,
    services: list[FlowService],
    facts: dict[str, ServiceFacts],
    context: ServiceGraphContext,
    page_filenames: dict[str, str],
) -> dict[str, Path]:
    """Write graphs/services/<page stem>.dot for every service; return name -> path."""
    graph_dir = output_dir / SERVICE_GRAPH_DIR
    graph_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    for service in services:
        name = service.identity.full_name
        stem = page_filenames[name].removesuffix(".md")
        path = graph_dir / f"{stem}.dot"
        path.write_text(render_service_graph_dot(service, facts[name], context), encoding="utf-8")
        written[name] = path
    return written
