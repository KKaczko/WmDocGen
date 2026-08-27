"""Deterministic one-paragraph summary of what a service does.

Everything here is derived from facts already in ``analysis.v8`` -- the signature,
the ordered call occurrences, the resolved dependencies and the platform effect
catalog in :mod:`wm_doc.builtins`. No model is involved, so a summary can restate
the analysis but can never invent a fact that the analysis does not contain.

``analysis.json`` stays frozen at ``analysis.v8``; summaries are produced at render
time and are not written back into the canonical snapshot.
"""

from __future__ import annotations

from wm_doc.builtins import BuiltinFamily, builtin_effect, is_builtin_name
from wm_doc.ir import FlowService, SignatureField

# Families that describe what a service does to the outside world, ranked by how
# much they matter to a reader deciding whether this service is business-critical.
_NOTABLE_FAMILIES: tuple[BuiltinFamily, ...] = (
    BuiltinFamily.TRANSACTION,
    BuiltinFamily.MESSAGING,
    BuiltinFamily.REMOTE,
    BuiltinFamily.FILE,
    BuiltinFamily.SECURITY,
)

_FAMILY_LAYER: dict[BuiltinFamily, str] = {
    BuiltinFamily.TRANSACTION: "DATA_ACCESS",
    BuiltinFamily.MESSAGING: "MESSAGING",
    BuiltinFamily.REMOTE: "INTEGRATION",
    BuiltinFamily.FILE: "FILE_IO",
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
    """Describe the platform effects in the order the FLOW performs them."""
    labels: list[str] = []
    for call in service.call_occurrences:
        effect = builtin_effect(call.target)
        if effect is None or effect.family is BuiltinFamily.ERROR_HANDLING:
            continue
        if effect.label not in labels:
            labels.append(effect.label)
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


def _dependency_sentence(service: FlowService) -> str | None:
    local = [
        dependency
        for dependency in service.unique_dependencies
        if not is_builtin_name(dependency.target_service)
    ]
    platform = [
        dependency
        for dependency in service.unique_dependencies
        if is_builtin_name(dependency.target_service)
    ]
    if not local and not platform:
        return "Calls no other service."
    clauses: list[str] = []
    if local:
        clauses.append(f"{len(local)} local service(s)")
    if platform:
        clauses.append(f"{len(platform)} platform service(s)")
    return "Calls " + _join(clauses) + "."


def _error_sentence(service: FlowService) -> str:
    handles = any(
        (effect := builtin_effect(call.target)) is not None
        and effect.family is BuiltinFamily.ERROR_HANDLING
        for call in service.call_occurrences
    )
    return "Handles errors explicitly." if handles else "No explicit error handling."


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
    families = set(service_effect_families(service))
    for family in _NOTABLE_FAMILIES:
        if family in families:
            return _FAMILY_LAYER[family]
    for family in families:
        layer = _FAMILY_LAYER.get(family)
        if layer is not None:
            return layer
    return None


def render_service_summary(service: FlowService) -> str:
    """Build the plain-language summary paragraph for one service."""
    sentences = [
        _effect_sentence(service),
        _signature_sentence(service),
        _dependency_sentence(service),
        _error_sentence(service),
    ]
    return " ".join(sentence for sentence in sentences if sentence)
