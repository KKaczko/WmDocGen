"""Pipeline paths in one normalised form.

FLOW files spell the same pipeline field differently depending on where it appears:

- mapping endpoints carry type suffixes: `/request;2;0/status;1;0` (and document references:
  `/input;4;0;pkg.doc:Order/id;1;0`); BRANCH switches may carry them or not (`/verified`);
- LOOP arrays are plain: `/orders`;
- label expressions use percent references relative to the pipeline: `%orders/status%`.

`PipelineRef` holds the segments without suffixes. Indexes written in a path (`/orders[0]`)
are kept, because they name one element, but `base()` drops them for "may refer to the same
field" checks. Nothing here guesses between fields with similar names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_INDEX_RE = re.compile(r"\[[^\]]*\]")


def clean_path(raw: str | None) -> str | None:
    """Strip webMethods type suffixes: ``/key;4;0;doc:Type/userId;1;0`` -> ``/key/userId``."""
    if not raw:
        return None
    parts = [segment.split(";", 1)[0] for segment in raw.split("/")]
    return "/".join(parts)


@dataclass(frozen=True, slots=True, order=True)
class PipelineRef:
    segments: tuple[str, ...]

    def text(self) -> str:
        return "/" + "/".join(self.segments)

    def base(self) -> tuple[str, ...]:
        """Segments without written indexes, for checks that may refer to the same field."""
        return tuple(_INDEX_RE.sub("", segment) for segment in self.segments)

    def overlaps(self, other: PipelineRef) -> bool:
        """True when one path is the other or lies inside it (a record and its fields)."""
        mine, theirs = self.base(), other.base()
        shorter = min(len(mine), len(theirs))
        return mine[:shorter] == theirs[:shorter]


def path_ref(raw: str | None) -> PipelineRef | None:
    """A reference for an endpoint, switch or LOOP array path; None when it names nothing."""
    cleaned = clean_path(raw)
    if cleaned is None:
        return None
    segments = tuple(segment.strip() for segment in cleaned.split("/") if segment.strip())
    return PipelineRef(segments) if segments else None


def expression_refs(label: str) -> tuple[PipelineRef, ...] | None:
    """Pipeline fields referenced as `%name%` in a label expression, in order, without repeats.

    Percent signs inside double-quoted strings are text, not references. Returns None when the
    expression cannot be split reliably (an unterminated reference or string), so callers
    report the expression as not interpreted instead of guessing.
    """
    found: list[PipelineRef] = []
    index = 0
    in_string = False
    while index < len(label):
        char = label[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "%":
            end = label.find("%", index + 1)
            if end < 0:
                return None
            name = label[index + 1 : end].strip()
            if not name or "\n" in name:
                return None
            ref = path_ref("/" + name.lstrip("/"))
            if ref is not None and ref not in found:
                found.append(ref)
            index = end + 1
            continue
        index += 1
    if in_string:
        return None
    return tuple(found)
