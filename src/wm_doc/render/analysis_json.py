"""`analysis.json`, written piece by piece.

A production server (thousands of services and document types) gives several hundred
megabytes of JSON. Building that text in one string needs several times its size in memory,
so the file is written one top-level list item, and one service or document type of each
package, at a time. The bytes are exactly those of
``json.dumps(analysis.model_dump(mode="json", exclude_none=True), ensure_ascii=False,
indent=2, sort_keys=True) + "\\n"``.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, TextIO

from pydantic import BaseModel

from wm_doc.ir import AnalysisResult

INDENT = 2
# Lists of models are written item by item down to this depth: the top-level lists, then the
# lists inside each item (a package's services and document types). Deeper values are dumped
# whole.
STREAM_DEPTH = 2


def render_analysis_json(analysis: AnalysisResult) -> str:
    buffer = io.StringIO()
    write_analysis_json_to(buffer, analysis)
    return buffer.getvalue()


def write_analysis_json(path: Path, analysis: AnalysisResult) -> None:
    # Same newline handling as Path.write_text, which earlier versions used.
    with path.open("w", encoding="utf-8") as handle:
        write_analysis_json_to(handle, analysis)


def write_analysis_json_to(out: TextIO, analysis: AnalysisResult) -> None:
    _write_model(out, analysis, 0, STREAM_DEPTH)
    out.write("\n")


def _write_model(out: TextIO, model: BaseModel, level: int, stream_depth: int) -> None:
    # exclude_none: a field whose value is None is left out, as model_dump(exclude_none) does.
    names = sorted(name for name in type(model).model_fields if getattr(model, name) is not None)
    if not names:
        out.write("{}")
        return
    pad = " " * (INDENT * (level + 1))
    out.write("{")
    for index, name in enumerate(names):
        out.write(",\n" if index else "\n")
        out.write(f"{pad}{json.dumps(name, ensure_ascii=False)}: ")
        value = getattr(model, name)
        if stream_depth > 0 and _is_model_list(value):
            _write_list(out, value, level + 1, stream_depth - 1)
        else:
            dumped = model.model_dump(mode="json", exclude_none=True, include={name})[name]
            out.write(_dumps(dumped, level + 1))
    out.write(f"\n{' ' * (INDENT * level)}}}")


def _write_list(out: TextIO, items: list[BaseModel], level: int, stream_depth: int) -> None:
    pad = " " * (INDENT * (level + 1))
    out.write("[")
    for index, item in enumerate(items):
        out.write(",\n" if index else "\n")
        out.write(pad)
        if stream_depth > 0:
            _write_model(out, item, level + 1, stream_depth)
        else:
            out.write(_dumps(item.model_dump(mode="json", exclude_none=True), level + 1))
    out.write(f"\n{' ' * (INDENT * level)}]")


def _is_model_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, BaseModel) for item in value)
    )


def _dumps(value: Any, level: int) -> str:
    """A value nested `level` containers deep, as the one-shot json.dumps would print it."""
    text = json.dumps(value, ensure_ascii=False, indent=INDENT, sort_keys=True)
    return text.replace("\n", "\n" + " " * (INDENT * level))
