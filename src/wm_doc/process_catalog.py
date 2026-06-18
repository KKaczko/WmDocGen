from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from yaml.events import AliasEvent, MappingStartEvent, ScalarEvent, SequenceStartEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from wm_doc.ir import (
    AnalysisFinding,
    FindingSeverity,
    FindingStatus,
    SourceReference,
)

MAX_PROCESS_CATALOG_BYTES = 256 * 1024
MAX_PROCESS_COUNT = 500
MAX_ENTRYPOINTS_PER_PROCESS = 100
PROCESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *{f"COM{index}" for index in range(1, 10)},
    *{f"LPT{index}" for index in range(1, 10)},
}
ALLOWED_YAML_TAGS = {
    "tag:yaml.org,2002:map",
    "tag:yaml.org,2002:seq",
    "tag:yaml.org,2002:str",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:null",
    "tag:yaml.org,2002:bool",
}


@dataclass(frozen=True)
class ParsedProcessEntrypoint:
    declared_target: str
    source: SourceReference
    duplicate_index: int = 0
    duplicate: bool = False


@dataclass(frozen=True)
class ParsedProcessDefinition:
    process_id: str
    name: str
    source: SourceReference
    id_source: SourceReference
    name_source: SourceReference
    description: str | None = None
    description_source: SourceReference | None = None
    description_malformed: bool = False
    entrypoints: list[ParsedProcessEntrypoint] = field(default_factory=list)
    findings: list[AnalysisFinding] = field(default_factory=list)


@dataclass(frozen=True)
class ParsedProcessCatalog:
    path: Path | None
    source_path: str
    definitions: list[ParsedProcessDefinition] = field(default_factory=list)
    findings: list[AnalysisFinding] = field(default_factory=list)


class ProcessCatalogLoader(yaml.SafeLoader):
    """Safe PyYAML loader marker for process catalogs."""


def load_process_catalog(
    path: Path, scan_root: Path, *, explicit: bool
) -> ParsedProcessCatalog:
    source_path = _catalog_source_path(path, scan_root)
    source = SourceReference(path=source_path, artifact_type="process_catalog")
    if not path.exists():
        missing_findings = []
        if explicit:
            missing_findings.append(
                _finding(
                    "PROCESS_CONFIG_MISSING",
                    "Explicit process catalog path was not found.",
                    source,
                    FindingStatus.UNRESOLVED,
                    FindingSeverity.WARNING,
                )
            )
        return ParsedProcessCatalog(
            path=path, source_path=source_path, findings=missing_findings
        )

    if path.stat().st_size > MAX_PROCESS_CATALOG_BYTES:
        return ParsedProcessCatalog(
            path=path,
            source_path=source_path,
            findings=[
                _finding(
                    "PROCESS_CONFIG_MALFORMED",
                    "Process catalog exceeds the supported 256 KiB size limit.",
                    source,
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            ],
        )

    try:
        text = path.read_text(encoding="utf-8")
        _reject_unsafe_yaml_events(text, source)
        documents = list(yaml.compose_all(text, Loader=ProcessCatalogLoader))
    except (OSError, UnicodeError, yaml.YAMLError, ValueError) as exc:
        return ParsedProcessCatalog(
            path=path,
            source_path=source_path,
            findings=[
                _finding(
                    "PROCESS_CONFIG_MALFORMED",
                    _safe_yaml_message("Process catalog could not be parsed safely.", exc),
                    source,
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            ],
        )

    if len(documents) != 1 or documents[0] is None:
        return ParsedProcessCatalog(
            path=path,
            source_path=source_path,
            findings=[
                _finding(
                    "PROCESS_CONFIG_MALFORMED",
                    "Process catalog must contain exactly one YAML document.",
                    source,
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            ],
        )

    root = documents[0]
    duplicate_finding = _first_duplicate_key_finding(root, source_path)
    if duplicate_finding is not None:
        return ParsedProcessCatalog(
            path=path, source_path=source_path, findings=[duplicate_finding]
        )
    if not isinstance(root, MappingNode):
        return ParsedProcessCatalog(
            path=path,
            source_path=source_path,
            findings=[
                _finding(
                    "PROCESS_CONFIG_MALFORMED",
                    "Process catalog root must be a mapping.",
                    _source_for_node(source_path, root, "process_catalog"),
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            ],
        )

    root_map = _mapping_by_key(root)
    findings: list[AnalysisFinding] = []
    for key, key_node in root_map.key_nodes.items():
        if key not in {"version", "processes"}:
            findings.append(
                _finding(
                    "PROCESS_CONFIG_UNKNOWN_KEY",
                    f"Unsupported process catalog top-level key {key!r} was ignored.",
                    _source_for_node(source_path, key_node, "process_catalog"),
                    FindingStatus.PARTIALLY_SUPPORTED,
                    FindingSeverity.INFO,
                )
            )

    version_node = root_map.values.get("version")
    if not (
        isinstance(version_node, ScalarNode)
        and version_node.tag == "tag:yaml.org,2002:int"
        and version_node.value == "1"
    ):
        findings.append(
            _finding(
                "PROCESS_CONFIG_VERSION_UNSUPPORTED",
                "Process catalog version must be integer 1.",
                _source_for_node(source_path, version_node or root, "process_catalog.version"),
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessCatalog(path=path, source_path=source_path, findings=findings)

    processes_node = root_map.values.get("processes")
    if not isinstance(processes_node, SequenceNode):
        findings.append(
            _finding(
                "PROCESS_CONFIG_MALFORMED",
                "Process catalog key 'processes' must be a list.",
                _source_for_node(source_path, processes_node or root, "process_catalog.processes"),
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessCatalog(path=path, source_path=source_path, findings=findings)
    if len(processes_node.value) > MAX_PROCESS_COUNT:
        findings.append(
            _finding(
                "PROCESS_CONFIG_MALFORMED",
                f"Process catalog contains more than {MAX_PROCESS_COUNT} processes.",
                _source_for_node(source_path, processes_node, "process_catalog.processes"),
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessCatalog(path=path, source_path=source_path, findings=findings)

    definitions: list[ParsedProcessDefinition] = []
    seen_ids: dict[str, SourceReference] = {}
    for index, process_node in enumerate(processes_node.value):
        definition = _parse_process_node(process_node, source_path, index, seen_ids)
        findings.extend(definition.findings)
        if definition.process_id:
            definitions.append(definition)
    return ParsedProcessCatalog(
        path=path,
        source_path=source_path,
        definitions=sorted(definitions, key=lambda item: item.process_id.casefold()),
        findings=findings,
    )


@dataclass(frozen=True)
class _MappingData:
    values: dict[str, Node]
    key_nodes: dict[str, Node]


def _parse_process_node(
    node: Node,
    source_path: str,
    index: int,
    seen_ids: dict[str, SourceReference],
) -> ParsedProcessDefinition:
    source = _source_for_node(source_path, node, "process_catalog", f"processes[{index}]")
    local_findings: list[AnalysisFinding] = []
    if not isinstance(node, MappingNode):
        local_findings.append(
            _finding(
                "PROCESS_CONFIG_MALFORMED",
                "Each process catalog entry must be a mapping.",
                source,
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessDefinition("", "", source, source, source, findings=local_findings)

    data = _mapping_by_key(node)
    for key, key_node in data.key_nodes.items():
        if key not in {"id", "name", "description", "entrypoints"}:
            local_findings.append(
                _finding(
                    "PROCESS_CONFIG_UNKNOWN_KEY",
                    f"Unsupported process key {key!r} was ignored.",
                    _source_for_node(
                        source_path,
                        key_node,
                        "process_catalog",
                        f"processes[{index}].{key}",
                    ),
                    FindingStatus.PARTIALLY_SUPPORTED,
                    FindingSeverity.INFO,
                )
            )

    id_node = data.values.get("id")
    id_source = _source_for_node(
        source_path,
        id_node or node,
        "process_catalog",
        f"processes[{index}].id",
    )
    process_id = _string_scalar(id_node)
    if process_id is None or not _valid_process_id(process_id):
        local_findings.append(
            _finding(
                "PROCESS_ID_INVALID",
                "Process id is missing or is not a safe process identifier.",
                id_source,
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessDefinition("", "", source, id_source, source, findings=local_findings)
    process_key = process_id.casefold()
    if process_key in seen_ids:
        local_findings.append(
            _finding(
                "PROCESS_ID_DUPLICATE",
                f"Duplicate process id {process_id!r}; later definition was skipped.",
                id_source,
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessDefinition("", "", source, id_source, source, findings=local_findings)
    seen_ids[process_key] = id_source

    name_node = data.values.get("name")
    name_source = _source_for_node(
        source_path, name_node or node, "process_catalog", f"processes[{index}].name"
    )
    name = _string_scalar(name_node)
    if name is None or not name.strip():
        local_findings.append(
            _finding(
                "PROCESS_NAME_MISSING",
                "Process name is missing or is not a scalar string.",
                name_source,
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
        return ParsedProcessDefinition(
            "", "", source, id_source, name_source, findings=local_findings
        )
    name = name.strip()

    description = None
    description_source = None
    description_malformed = False
    if "description" in data.values:
        description_node = data.values["description"]
        description_source = _source_for_node(
            source_path,
            description_node,
            "process_catalog",
            f"processes[{index}].description",
        )
        description = _string_scalar(description_node)
        if description is None:
            description_malformed = True
            local_findings.append(
                _finding(
                    "PROCESS_DESCRIPTION_MALFORMED",
                    "Process description is not a scalar string and was omitted.",
                    description_source,
                    FindingStatus.MALFORMED,
                    FindingSeverity.WARNING,
                )
            )
        elif not description.strip():
            description = None

    entrypoints_node = data.values.get("entrypoints")
    entrypoints: list[ParsedProcessEntrypoint] = []
    if not isinstance(entrypoints_node, SequenceNode) or not entrypoints_node.value:
        local_findings.append(
            _finding(
                "PROCESS_ENTRYPOINTS_MISSING",
                "Process entrypoints must be a non-empty list of canonical service names.",
                _source_for_node(
                    source_path,
                    entrypoints_node or node,
                    "process_catalog",
                    f"processes[{index}].entrypoints",
                ),
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
    elif len(entrypoints_node.value) > MAX_ENTRYPOINTS_PER_PROCESS:
        local_findings.append(
            _finding(
                "PROCESS_CONFIG_MALFORMED",
                f"Process contains more than {MAX_ENTRYPOINTS_PER_PROCESS} entrypoints.",
                _source_for_node(
                    source_path,
                    entrypoints_node,
                    "process_catalog",
                    f"processes[{index}].entrypoints",
                ),
                FindingStatus.MALFORMED,
                FindingSeverity.ERROR,
            )
        )
    else:
        counts: dict[str, int] = {}
        for entry_index, entry_node in enumerate(entrypoints_node.value):
            entry_source = _source_for_node(
                source_path,
                entry_node,
                "process_catalog",
                f"processes[{index}].entrypoints[{entry_index}]",
            )
            target = _string_scalar(entry_node)
            if target is None or not target.strip():
                local_findings.append(
                    _finding(
                        "PROCESS_ENTRYPOINT_MALFORMED",
                        "Process entrypoint is not a scalar canonical service name.",
                        entry_source,
                        FindingStatus.MALFORMED,
                        FindingSeverity.ERROR,
                    )
                )
                continue
            target = target.strip()
            duplicate_index = counts.get(target, 0)
            counts[target] = duplicate_index + 1
            entrypoints.append(
                ParsedProcessEntrypoint(
                    declared_target=target,
                    source=entry_source,
                    duplicate_index=duplicate_index,
                    duplicate=duplicate_index > 0,
                )
            )
    return ParsedProcessDefinition(
        process_id=process_id,
        name=name,
        description=description,
        description_source=description_source,
        description_malformed=description_malformed,
        entrypoints=entrypoints,
        source=source,
        id_source=id_source,
        name_source=name_source,
        findings=local_findings,
    )


def _reject_unsafe_yaml_events(text: str, source: SourceReference) -> None:
    for event in yaml.parse(text, Loader=ProcessCatalogLoader):
        if isinstance(event, AliasEvent) or getattr(event, "anchor", None):
            raise ValueError("YAML aliases and anchors are not supported in process catalogs.")
        tag = getattr(event, "tag", None)
        if tag and tag not in ALLOWED_YAML_TAGS:
            raise ValueError("YAML custom tags are not supported in process catalogs.")
        if (
            isinstance(event, (MappingStartEvent, SequenceStartEvent, ScalarEvent))
            and getattr(event, "implicit", None) is False
        ):
            raise ValueError("YAML explicit tags are not supported in process catalogs.")
    del source


def _first_duplicate_key_finding(node: Node, source_path: str) -> AnalysisFinding | None:
    if isinstance(node, MappingNode):
        seen: set[str] = set()
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                return _finding(
                    "PROCESS_CONFIG_MALFORMED",
                    "Process catalog mapping keys must be scalar strings.",
                    _source_for_node(source_path, key_node, "process_catalog"),
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            key = str(key_node.value)
            folded = key.casefold()
            if folded in seen:
                return _finding(
                    "PROCESS_CONFIG_MALFORMED",
                    f"Process catalog contains duplicate key {key!r}.",
                    _source_for_node(source_path, key_node, "process_catalog"),
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            seen.add(folded)
            nested = _first_duplicate_key_finding(value_node, source_path)
            if nested is not None:
                return nested
    if isinstance(node, SequenceNode):
        for child in node.value:
            nested = _first_duplicate_key_finding(child, source_path)
            if nested is not None:
                return nested
    return None


def _mapping_by_key(node: MappingNode) -> _MappingData:
    values: dict[str, Node] = {}
    key_nodes: dict[str, Node] = {}
    for key_node, value_node in node.value:
        if isinstance(key_node, ScalarNode):
            key = str(key_node.value)
            values[key] = value_node
            key_nodes[key] = key_node
    return _MappingData(values=values, key_nodes=key_nodes)


def _string_scalar(node: Node | None) -> str | None:
    if isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:str":
        return str(node.value)
    return None


def _is_int_scalar(node: Node | None) -> bool:
    return isinstance(node, ScalarNode) and node.tag == "tag:yaml.org,2002:int"


def _valid_process_id(process_id: str) -> bool:
    if not PROCESS_ID_RE.match(process_id):
        return False
    if ".." in process_id or process_id.startswith(".") or process_id.endswith("."):
        return False
    basename = process_id.split(".", 1)[0].upper()
    return basename not in WINDOWS_RESERVED_NAMES


def _source_for_node(
    source_path: str,
    node: Node | None,
    artifact_type: str,
    source_node: str | None = None,
) -> SourceReference:
    if node is None:
        return SourceReference(
            path=source_path, artifact_type=artifact_type, source_node=source_node
        )
    mark = node.start_mark
    return SourceReference(
        path=source_path,
        artifact_type=artifact_type,
        source_node=source_node,
        line=mark.line + 1 if mark is not None else None,
        column=mark.column + 1 if mark is not None else None,
    )


def _catalog_source_path(path: Path, scan_root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = scan_root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return path.name


def _finding(
    code: str,
    message: str,
    source: SourceReference,
    status: FindingStatus,
    severity: FindingSeverity,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=status,
        code=code,
        message=message,
        source=source,
        severity=severity,
    )


def _safe_yaml_message(prefix: str, exc: Exception) -> str:
    message = " ".join(str(exc).replace("\r", " ").replace("\n", " ").split())
    if not message:
        return prefix
    # PyYAML can include snippets or local filenames in diagnostic text; keep the message generic.
    if any(marker in message for marker in (" in \"", "line ", "column ")):
        return prefix
    return f"{prefix} {message}"
