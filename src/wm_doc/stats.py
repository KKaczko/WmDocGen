"""Read-only overview of an analysed server, meant to be run on production first.

It answers the questions that decide what to build or configure next: how many services
of each kind there are, which artifact types exist, which FLOW constructs are not yet
interpreted, which platform services are missing from the effect catalog, where calls
leave the analysed packages (the input for `external-systems.yml`), and which services
are largest for a language model.

The report contains package, namespace, service and artifact-type names and counts. It
contains no code, field values, literals or comments.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from wm_doc.builtins import builtin_effect, is_builtin_name
from wm_doc.ir import AnalysisResult, FlowService, ServiceType
from wm_doc.pseudocode import render_pseudocode
from wm_doc.render.artifact_markdown import artifact_kind

UNSUPPORTED_TAG_RE = re.compile(r"FLOW element (\S+) is observed")
CHARS_PER_TOKEN = 3.5
LARGEST_SERVICES = 15
TOP_ITEMS = 40


def namespace_prefix(full_name: str, depth: int = 2) -> str:
    namespace = full_name.split(":", 1)[0]
    return ".".join(namespace.split(".")[:depth])


def render_stats(analysis: AnalysisResult) -> str:
    services = [service for package in analysis.packages for service in package.services]
    lines = [
        "# wm-doc server statistics",
        "",
        "Counts and names only: no code, values, literals or comments.",
        "",
        "## Packages",
        "",
        f"- Analysed: {len(analysis.packages)}",
        f"- Skipped: {len(analysis.excluded_packages)}",
    ]
    reasons = Counter(package.reason for package in analysis.excluded_packages)
    lines += [f"  - {count} x {reason}" for reason, count in sorted(reasons.items())]
    types = Counter(service.service_type.value for service in services)
    lines += [
        "",
        "## Services",
        "",
        "| Kind | Count |",
        "| --- | ---: |",
        f"| FLOW | {types.get('FLOW', 0)} |",
        f"| Java | {types.get('JAVA', 0)} |",
        f"| Opaque (adapter and other services) | {types.get('OPAQUE', 0)} |",
        f"| Document types | {len(analysis.document_types)} |",
        "",
    ]
    disabled = [service for service in services if service.disabled_steps]
    if disabled:
        total = sum(service.disabled_steps for service in disabled)
        lines += [
            f"Disabled FLOW steps (left out, they never run): {total} in "
            f"{len(disabled)} service(s).",
            "",
        ]
    lines += _opaque_section(services)
    lines += _artifact_section(analysis)
    lines += _unsupported_flow_section(services)
    lines += _uncatalogued_platform_section(services)
    lines += _external_calls_section(analysis)
    lines += _unresolved_reasons_section(analysis)
    lines += _largest_services_section(services)
    return "\n".join(lines).rstrip() + "\n"


def _opaque_section(services: list[FlowService]) -> list[str]:
    counts = Counter(
        service.source_service_type or "<not declared>"
        for service in services
        if service.service_type is ServiceType.OPAQUE
    )
    lines = ["## Opaque services by svc_type", ""]
    if not counts:
        return [*lines, "None.", ""]
    lines += ["| svc_type | Count |", "| --- | ---: |"]
    lines += [f"| `{name}` | {count} |" for name, count in counts.most_common()]
    return [*lines, ""]


def _artifact_section(analysis: AnalysisResult) -> list[str]:
    counts = Counter(artifact_kind(artifact) for artifact in analysis.namespace_artifacts)
    lines = ["## Other artifacts by node type", ""]
    if not counts:
        return [*lines, "None.", ""]
    lines += ["| node_type | Count |", "| --- | ---: |"]
    lines += [f"| `{name}` | {count} |" for name, count in counts.most_common()]
    return [*lines, ""]


def _unsupported_flow_section(services: list[FlowService]) -> list[str]:
    by_tag: Counter[str] = Counter()
    for service in services:
        for finding in service.findings:
            if finding.code != "UNSUPPORTED_FLOW_ELEMENT":
                continue
            match = UNSUPPORTED_TAG_RE.search(finding.message)
            by_tag[match.group(1) if match else "<unknown>"] += 1
    lines = ["## FLOW elements not interpreted", ""]
    if not by_tag:
        return [*lines, "None: every FLOW element was recognised.", ""]
    lines += ["| Element | Services |", "| --- | ---: |"]
    lines += [f"| `{tag}` | {count} |" for tag, count in by_tag.most_common()]
    return [*lines, ""]


def _uncatalogued_platform_section(services: list[FlowService]) -> list[str]:
    callers: dict[str, set[str]] = defaultdict(set)
    for service in services:
        for dependency in service.unique_dependencies:
            target = dependency.target_service
            if is_builtin_name(target) and builtin_effect(target) is None:
                callers[target].add(service.identity.full_name)
    lines = [
        "## Platform services missing from the effect catalog",
        "",
        (
            "Every one is listed. Describe them in a file passed with `--platform-services` "
            "(format: `src/wm_doc/data/platform_services.yml`)."
        ),
        "",
    ]
    if not callers:
        return [*lines, "None.", ""]
    lines += ["| Service | Callers |", "| --- | ---: |"]
    ranked = sorted(callers.items(), key=lambda item: (-len(item[1]), item[0].casefold()))
    lines += [f"| `{name}` | {len(users)} |" for name, users in ranked]
    return [*lines, ""]


def _external_calls_section(analysis: AnalysisResult) -> list[str]:
    targets: dict[str, set[str]] = defaultdict(set)
    callers: dict[str, set[str]] = defaultdict(set)
    for dependency in analysis.unique_dependencies:
        if dependency.resolved or is_builtin_name(dependency.target_service):
            continue
        prefix = namespace_prefix(dependency.target_service)
        targets[prefix].add(dependency.target_service)
        callers[prefix].add(dependency.source_service)
    lines = [
        "## Calls leaving the analysed packages",
        "",
        (
            "Grouped by the first two namespace segments. Declare the systems behind these "
            "in `external-systems.yml`, or include the packages that contain them."
        ),
        "",
    ]
    if not targets:
        return [*lines, "None.", ""]
    lines += ["| Namespace prefix | Target services | Calling services |", "| --- | ---: | ---: |"]
    ranked = sorted(targets, key=lambda prefix: (-len(targets[prefix]), prefix.casefold()))
    lines += [
        f"| `{prefix}` | {len(targets[prefix])} | {len(callers[prefix])} |"
        for prefix in ranked[:TOP_ITEMS]
    ]
    if len(ranked) > TOP_ITEMS:
        lines.append(f"| ... {len(ranked) - TOP_ITEMS} more | | |")
    return [*lines, ""]


def _unresolved_reasons_section(analysis: AnalysisResult) -> list[str]:
    """Whether each unresolved call target exists in the folder as something else."""
    present = {
        artifact.full_name: artifact_kind(artifact) for artifact in analysis.namespace_artifacts
    }
    targets: dict[str, set[str]] = defaultdict(set)
    found: dict[str, Counter[str]] = defaultdict(Counter)
    for dependency in analysis.unique_dependencies:
        target = dependency.target_service
        if dependency.resolved or is_builtin_name(target):
            continue
        prefix = namespace_prefix(target)
        if target in targets[prefix]:
            continue
        targets[prefix].add(target)
        kind = present.get(target)
        if kind is not None:
            found[prefix][kind] += 1
    lines = [
        "## Why calls leave the analysed packages",
        "",
        (
            "For the call targets above: a node with the exact name exists in the scanned "
            "folder but is not a recognised service (the kinds are counted), or no node with "
            "that name is in the folder at all (its package is missing, skipped or named "
            "differently)."
        ),
        "",
    ]
    if not targets:
        return [*lines, "None.", ""]
    lines += [
        "| Namespace prefix | Targets | In the folder, not a service | Not in the folder |",
        "| --- | ---: | --- | ---: |",
    ]
    ranked = sorted(targets, key=lambda prefix: (-len(targets[prefix]), prefix.casefold()))
    for prefix in ranked[:TOP_ITEMS]:
        kinds = found[prefix]
        shown = ", ".join(f"{count} `{kind}`" for kind, count in kinds.most_common()) or "-"
        missing = len(targets[prefix]) - sum(kinds.values())
        lines.append(f"| `{prefix}` | {len(targets[prefix])} | {shown} | {missing} |")
    if len(ranked) > TOP_ITEMS:
        lines.append(f"| ... {len(ranked) - TOP_ITEMS} more | | | |")
    return [*lines, ""]


def _largest_services_section(services: list[FlowService]) -> list[str]:
    sizes = sorted(
        (
            (len(render_pseudocode(service, lambda _: None)), service.identity.full_name)
            for service in services
        ),
        reverse=True,
    )
    lines = [
        "## Largest services for a language model",
        "",
        "Estimated prompt size of the pseudo-code view, before callee descriptions.",
        "",
    ]
    if not sizes:
        return [*lines, "None.", ""]
    lines += ["| Service | Estimated tokens |", "| --- | ---: |"]
    lines += [
        f"| `{name}` | {round(chars / CHARS_PER_TOKEN)} |"
        for chars, name in sizes[:LARGEST_SERVICES]
    ]
    return [*lines, ""]
