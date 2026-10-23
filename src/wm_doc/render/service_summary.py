"""Deterministic one-paragraph summary of what a service does.

Everything here is derived from facts already in ``analysis.v9`` -- the signature,
the ordered call occurrences, the resolved dependencies and the platform effect
catalog in :mod:`wm_doc.builtins`. No model is involved, so a summary can restate
the analysis but can never invent a fact that the analysis does not contain.

``analysis.json`` never stores summaries; they are produced at render
time and are not written back into the canonical snapshot.
"""

from __future__ import annotations

from wm_doc.adapters import operation_phrase
from wm_doc.builtins import FAMILY_RANK, BuiltinFamily, builtin_effect, is_builtin_name
from wm_doc.effects import ADAPTER_KNOWN_FROM, ServiceFacts
from wm_doc.ir import FlowNode, FlowNodeType, FlowService, ServiceType, SignatureField

# Families that describe how a service copes with failure or traces itself, not what it does.
_NOT_EFFECTS = {BuiltinFamily.ERROR_HANDLING, BuiltinFamily.LOGGING}

_MECHANISM_TEXT: dict[str, str] = {
    "try": "TRY/CATCH blocks",
    "exit-on-success": "a try/catch sequence (exit on first success)",
    "repeat": "REPEAT on failure",
    "exit-failure": "EXIT with a failure signal",
}

# Families that describe what a service does to the outside world, ranked by how
# much they matter to a reader deciding whether this service is business-critical.
_NOTABLE_FAMILIES: tuple[BuiltinFamily, ...] = (
    BuiltinFamily.TRANSACTION,
    BuiltinFamily.DATABASE,
    BuiltinFamily.MESSAGING,
    BuiltinFamily.REMOTE,
    BuiltinFamily.FILE,
    BuiltinFamily.SERVER_ADMIN,
    BuiltinFamily.SECURITY,
)

_FAMILY_LAYER: dict[BuiltinFamily, str] = {
    BuiltinFamily.TRANSACTION: "DATA_ACCESS",
    BuiltinFamily.DATABASE: "DATA_ACCESS",
    BuiltinFamily.MESSAGING: "MESSAGING",
    BuiltinFamily.REMOTE: "INTEGRATION",
    BuiltinFamily.FILE: "FILE_IO",
    BuiltinFamily.SERVER_ADMIN: "ADMINISTRATION",
    BuiltinFamily.SECURITY: "SECURITY",
    BuiltinFamily.SCHEMA: "VALIDATION",
    BuiltinFamily.XML: "TRANSFORMATION",
    BuiltinFamily.JSON: "TRANSFORMATION",
    BuiltinFamily.FLAT_FILE: "TRANSFORMATION",
    BuiltinFamily.DOCUMENT: "TRANSFORMATION",
}


def _field_names(fields: list[SignatureField], limit: int = 4) -> list[str]:
    return [field.name for field in fields[:limit]]


def _join(parts: list[str]) -> str:
    """Join clauses as ``a``, ``a and b`` or ``a, b and c``."""
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _sentence_case(text: str) -> str:
    """Upper-case only the first character, preserving identifier casing elsewhere."""
    return text[:1].upper() + text[1:] if text else text


def _effect_sentence(service: FlowService) -> str | None:
    """Describe the platform effects, most significant family first, then call order."""
    first_seen: dict[str, tuple[int, int]] = {}
    for position, call in enumerate(service.call_occurrences):
        effect = builtin_effect(call.target)
        if effect is None or effect.family in _NOT_EFFECTS:
            continue
        if effect.label not in first_seen:
            first_seen[effect.label] = (FAMILY_RANK.get(effect.family, 99), position)
    labels = sorted(first_seen, key=lambda label: first_seen[label])
    if not labels:
        return None
    shown = labels[:4]
    sentence = _sentence_case(_join(shown))
    if len(labels) > len(shown):
        sentence += f", and {len(labels) - len(shown)} further platform operation(s)"
    return sentence + "."


def _signature_sentence(service: FlowService) -> str | None:
    inputs = _field_names(service.signature.inputs)
    outputs = _field_names(service.signature.outputs)
    if not inputs and not outputs:
        return None
    clauses: list[str] = []
    if inputs:
        extra = len(service.signature.inputs) - len(inputs)
        names = ", ".join(f"`{name}`" for name in inputs)
        clauses.append(f"takes {names}" + (f" and {extra} more" if extra > 0 else ""))
    if outputs:
        extra = len(service.signature.outputs) - len(outputs)
        names = ", ".join(f"`{name}`" for name in outputs)
        clauses.append(f"returns {names}" + (f" and {extra} more" if extra > 0 else ""))
    return _sentence_case(_join(clauses)) + "."


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}" if number == 1 else f"{number} {noun}s"


def _dependency_sentence(service: FlowService) -> str | None:
    if service.service_type is ServiceType.OPAQUE:
        return None  # calls are not analysed for opaque services
    inside = outside = platform = 0
    for dependency in service.unique_dependencies:
        if is_builtin_name(dependency.target_service):
            platform += 1
        elif dependency.resolved:
            inside += 1
        else:
            outside += 1
    if not (inside or outside or platform):
        if service.service_type is ServiceType.JAVA:
            return "No statically confirmed service calls."
        return "Calls no other service."
    clauses: list[str] = []
    if inside:
        clauses.append(f"{_count(inside, 'service')} in the analysed packages")
    if outside:
        clauses.append(f"{_count(outside, 'service')} outside the analysed packages")
    if platform:
        clauses.append(_count(platform, "platform service"))
    return "Calls " + _join(clauses) + "."


def error_handling_mechanisms(service: FlowService) -> list[str]:
    """Error-handling constructs observed in a FLOW service, in a fixed order."""
    found: set[str] = set()

    def visit(node: FlowNode) -> None:
        form = (node.form or "").upper()
        if node.type is FlowNodeType.SEQUENCE and form in {"TRY", "CATCH", "FINALLY"}:
            found.add("try")
        elif node.type is FlowNodeType.SEQUENCE and (node.exit_on or "").upper() == "SUCCESS":
            found.add("exit-on-success")
        elif node.type is FlowNodeType.REPEAT:
            if (node.attributes.get("LOOP-ON") or "FAILURE").upper() == "FAILURE":
                found.add("repeat")
        elif node.type is FlowNodeType.EXIT and (node.signal or "").upper() == "FAILURE":
            found.add("exit-failure")
        for child in node.children:
            visit(child)

    if service.flow_tree is not None:
        visit(service.flow_tree)
    for call in service.call_occurrences:
        effect = builtin_effect(call.target)
        if effect is not None and effect.family is BuiltinFamily.ERROR_HANDLING:
            found.add(f"call:{call.target}")
    ordered = [key for key in _MECHANISM_TEXT if key in found]
    ordered.extend(sorted(key for key in found if key.startswith("call:")))
    return [_MECHANISM_TEXT.get(key) or f"`{key.removeprefix('call:')}`" for key in ordered]


def _error_sentence(service: FlowService) -> str:
    if service.service_type is ServiceType.JAVA:
        return "Error handling is not analysed for Java services."
    if service.service_type is not ServiceType.FLOW:
        return "Error handling is not analysed for this service type."
    mechanisms = error_handling_mechanisms(service)
    if not mechanisms:
        return "No error-handling steps found."
    return "Handles errors with " + _join(mechanisms) + "."


def service_effect_families(service: FlowService) -> list[BuiltinFamily]:
    """Return the distinct platform effect families this service touches, ranked."""
    seen: set[BuiltinFamily] = set()
    for call in service.call_occurrences:
        effect = builtin_effect(call.target)
        if effect is not None:
            seen.add(effect.family)
    return [family for family in BuiltinFamily if family in seen]


def derived_layer(service: FlowService) -> str | None:
    """Derive a layer from the platform effects, or None when nothing is known.

    This replaces the ``UNKNOWN`` that pattern-based classification produces for
    almost every service in a real package.
    """
    if service.adapter is not None:
        return "DATA_ACCESS"
    families = set(service_effect_families(service))
    for family in _NOTABLE_FAMILIES:
        if family in families:
            return _FAMILY_LAYER[family]
    for family in families:
        layer = _FAMILY_LAYER.get(family)
        if layer is not None:
            return layer
    return None


def adapter_sentence(service: FlowService) -> str | None:
    """`JDBC adapter service: selects rows from table `x` through connection `y`.`"""
    details = service.adapter
    if details is None:
        return None
    tables = ", ".join(f"`{table}`" for table in details.tables)
    target = f" table{'s' if len(details.tables) > 1 else ''} {tables}" if tables else ""
    through = f" through connection `{details.connection}`" if details.connection else ""
    template = f" (template `{details.operation}`)" if details.operation else ""
    return f"JDBC adapter service{template}: {operation_phrase(details)}{target}{through}."


def _adapter_call_sentence(facts: ServiceFacts | None) -> str | None:
    """Database operations of the adapter services this service calls directly."""
    if facts is None:
        return None
    parts: list[str] = []
    for effect in facts.effects:
        if effect.known_from == ADAPTER_KNOWN_FROM and len(effect.via) == 1:
            text = f"{effect.action} {effect.object}"
            if text not in parts:
                parts.append(text)
    if not parts:
        return None
    sentence = "Through adapter services it " + _join(parts[:3])
    if len(parts) > 3:
        sentence += f", and {len(parts) - 3} more database operation(s)"
    return sentence + "."


def render_service_summary(service: FlowService, facts: ServiceFacts | None = None) -> str:
    """Build the plain-language summary paragraph for one service."""
    sentences = [
        adapter_sentence(service),
        _adapter_call_sentence(facts),
        _effect_sentence(service),
        _signature_sentence(service),
        _dependency_sentence(service),
        _error_sentence(service),
    ]
    return " ".join(sentence for sentence in sentences if sentence)
