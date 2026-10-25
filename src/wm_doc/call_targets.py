"""How a call from one service ends: the shared classification behind scope boundaries.

Focused publication (`scope_analysis`) and the explorer (`wm_doc.explorer`) both need to say
whether a call reaches an analysed service, the platform, a named service outside the analysed
packages, or something the static analysis cannot follow. The rules live here once.
"""

from __future__ import annotations

import re
from enum import StrEnum

from wm_doc.builtins import is_builtin_name
from wm_doc.ir import AnalysisFinding, JavaInvocationOccurrence, JavaInvocationTargetStatus

NAMESPACE_SEGMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Java analysis reports each non-static `Service.doInvoke` twice: as an invocation record
# (`classify_java_invocation`) and as one of these findings.
JAVA_TARGET_FINDING_CODES = frozenset({"DYNAMIC_SERVICE_TARGET", "PARTIALLY_STATIC_SERVICE_TARGET"})
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class TargetStatus(StrEnum):
    RESOLVED = "resolved"  # an analysed service
    PLATFORM = "platform"  # a built-in service (pub.*, wm.*)
    OUTSIDE = "outside"  # a well-formed service name that is not in the analysed packages
    UNRESOLVED = "unresolved"  # a target that is not even a well-formed service name
    DYNAMIC = "dynamic"  # the target is computed at run time
    UNSUPPORTED = "unsupported"  # a call-like construct the analysis does not interpret


def classify_target(target: str, resolved: bool) -> TargetStatus:
    """Classify the target of a static call (FLOW INVOKE/MAPINVOKE or static Java invoke)."""
    if resolved:
        return TargetStatus.RESOLVED
    if is_builtin_name(target):
        return TargetStatus.PLATFORM
    if valid_service_full_name(target):
        return TargetStatus.OUTSIDE
    return TargetStatus.UNRESOLVED


def classify_finding(finding: AnalysisFinding) -> TargetStatus | None:
    """DYNAMIC or UNSUPPORTED when a finding reports a call the analysis cannot follow."""
    code = finding.code.upper()
    message = finding.message.upper()
    if "DYNAMIC" in code and ("SERVICE" in code or "INVOKE" in code or "CALL" in code):
        return TargetStatus.DYNAMIC
    if "UNSUPPORTED" in code and ("SERVICE" in code or "INVOKE" in code or "CALL" in code):
        return TargetStatus.UNSUPPORTED
    if "PARTIALLY_STATIC_SERVICE_TARGET" in code:
        return TargetStatus.DYNAMIC
    if "DYNAMIC" in message and ("SERVICE" in message or "INVOK" in message):
        return TargetStatus.DYNAMIC
    return None


def classify_java_invocation(invocation: JavaInvocationOccurrence) -> TargetStatus | None:
    """DYNAMIC or UNRESOLVED for Java invocations that did not become dependencies.

    Static targets are None: they are unique dependencies and classified with
    `classify_target`.
    """
    if invocation.target_status == JavaInvocationTargetStatus.STATIC_TARGET:
        return None
    if invocation.target_status == JavaInvocationTargetStatus.MALFORMED_TARGET:
        return TargetStatus.UNRESOLVED
    return TargetStatus.DYNAMIC


def placeholder_target(status: TargetStatus) -> str:
    """The name shown for a call whose target is not known statically."""
    if status is TargetStatus.DYNAMIC:
        return "<dynamic-target>"
    if status is TargetStatus.UNSUPPORTED:
        return "<unsupported-call-like-construct>"
    return "<unresolved-target>"


def valid_service_full_name(value: str) -> bool:
    if CONTROL_RE.search(value) or value.count(":") != 1:
        return False
    namespace, service = value.split(":", 1)
    return valid_namespace(namespace) and valid_name_segment(service)


def valid_namespace(value: str) -> bool:
    if not value or CONTROL_RE.search(value):
        return False
    if any(char in value for char in "/\\:"):
        return False
    return all(valid_name_segment(segment) for segment in value.split("."))


def valid_name_segment(value: str) -> bool:
    return bool(value) and NAMESPACE_SEGMENT_RE.match(value) is not None
