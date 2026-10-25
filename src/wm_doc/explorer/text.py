"""Text that leaves the tool for the explorer: inert, bounded and disclosure-checked.

Everything the explorer shows is treated as untrusted. Identifiers (service names, paths) are
stripped of control and direction-override characters and capped. Prose (finding messages,
description text) is also run through the disclosure scan; text that fails it is withheld
and counted, never shown. Nothing is HTML or Markdown: text with `code` spans becomes a list
of plain segments, and the app renders all of it as text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from wm_doc.disclosure import unsafe_disclosure_label
from wm_doc.explorer.contract import CodeSegment, SectionKey, Segment, TextSegment

MAX_TEXT_CHARS = 4_000
MAX_NAME_CHARS = 512
MAX_SECTION_BLOCKS = 200
# C0/C1 controls, zero-width and bidirectional formatting characters, line/paragraph separators.
_INVISIBLE_RE = re.compile(
    "[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2028-\u2029"
    "\u2060-\u2069\ufeff]"
)
_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:|/|\\\\|~)")
_CODE_SPAN_RE = re.compile(r"`([^`]+)`")
# describe escapes a leading Markdown character with a backslash (describer.clean_text).
_ESCAPED_MARKDOWN_RE = re.compile(r"\\([#>\-*+|])")
_ITEM_RE = re.compile(r"^\s*(?:\d+[.)]|[-*+])\s+")

# Narrative headings shown by the explorer. Anything else in a description file (the Designer
# comment, Notes, the facts block, headings people added) is never exported.
SECTION_KEYS: dict[str, SectionKey] = {
    "Purpose": "purpose",
    "Usage": "usage",
    "What it does to data": "dataEffects",
    "Main steps": "mainSteps",
    "Detailed flow": "detailedFlow",
    "Error handling": "errorHandling",
}
# Package and server overview files (`_package.md`, `_server.md`).
OVERVIEW_SECTION_KEYS: dict[str, SectionKey] = {
    "Purpose": "purpose",
    "Main capabilities": "capabilities",
    "Business areas": "areas",
    "Entry points": "entryPoints",
    "Systems and data": "systemsAndData",
}


class TextGuard:
    """Cleans strings for the explorer and counts what it had to withhold."""

    def __init__(self) -> None:
        self.withheld = 0

    def name(self, text: str) -> str:
        """An identifier: kept as written, minus invisible characters, capped."""
        cleaned = _INVISIBLE_RE.sub("", text)
        return cleaned[:MAX_NAME_CHARS]

    def path(self, text: str) -> str:
        """A source path relative to the scanned folder; never an absolute path."""
        cleaned = self.name(text).replace("\\", "/")
        if _ABSOLUTE_PATH_RE.match(cleaned) or ".." in cleaned.split("/"):
            self.withheld += 1
            return "[withheld: absolute path]"
        return cleaned

    def free_text(self, text: str | None, limit: int = MAX_TEXT_CHARS) -> str | None:
        """Prose: whitespace collapsed, disclosure-scanned, capped. None when empty."""
        if text is None:
            return None
        flat = _flatten(text)
        if not flat:
            return None
        label = unsafe_disclosure_label(flat)
        if label is not None:
            self.withheld += 1
            return f"[withheld: {label}]"
        return cap(flat, limit)

    def segments(
        self,
        text: str | None,
        refs: Mapping[str, str],
        *,
        prose: bool,
        limit: int = MAX_TEXT_CHARS,
    ) -> list[Segment]:
        """Text with `code` spans as segments; a span exactly naming a service gets its ID.

        `prose` (model or human text) is disclosure-scanned as a whole and withheld when it
        fails. Facts the tool wrote are only cleaned and capped.
        """
        if text is None:
            return []
        flat = _flatten(text)
        if not flat:
            return []
        if prose:
            label = unsafe_disclosure_label(flat)
            if label is not None:
                self.withheld += 1
                return [TextSegment(text=f"[withheld: {label}]")]
        flat = cap(flat, limit)
        found: list[Segment] = []
        position = 0
        for match in _CODE_SPAN_RE.finditer(flat):
            if match.start() > position:
                found.append(TextSegment(text=_unescape(flat[position : match.start()])))
            code = match.group(1).strip()
            found.append(CodeSegment(code=code, ref=refs.get(code)))
            position = match.end()
        if position < len(flat):
            found.append(TextSegment(text=_unescape(flat[position:])))
        return found


def narrative_blocks(
    narrative: str, keys: Mapping[str, SectionKey] = SECTION_KEYS
) -> list[tuple[SectionKey, list[str], list[str]]]:
    """The known sections of a description narrative: (key, paragraphs, list items)."""
    sections: list[tuple[SectionKey, list[str], list[str]]] = []
    key: SectionKey | None = None
    lines: list[str] = []

    def flush() -> None:
        if key is not None:
            paragraphs, items = _blocks(lines)
            if paragraphs or items:
                sections.append((key, paragraphs, items))

    for line in narrative.splitlines():
        if line.startswith("## "):
            flush()
            key = keys.get(line[3:].strip())
            lines = []
        elif key is not None:
            lines.append(line)
    flush()
    return sections


def _blocks(lines: list[str]) -> tuple[list[str], list[str]]:
    paragraphs: list[str] = []
    items: list[str] = []
    current: list[str] = []
    in_item = False
    in_fence = False

    def end_paragraph() -> None:
        text = " ".join(current).strip()
        if text and text != "-":
            paragraphs.append(text)
        current.clear()

    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _ITEM_RE.match(line):
            end_paragraph()
            items.append(_ITEM_RE.sub("", line, count=1).strip())
            in_item = True
        elif not line.strip():
            end_paragraph()
            in_item = False
        elif in_item and items:
            items[-1] = f"{items[-1]} {line.strip()}"
        else:
            current.append(line.strip())
    end_paragraph()
    return paragraphs[:MAX_SECTION_BLOCKS], items[:MAX_SECTION_BLOCKS]


def _flatten(text: str) -> str:
    return " ".join(_INVISIBLE_RE.sub(" ", text).split())


def _unescape(text: str) -> str:
    return _ESCAPED_MARKDOWN_RE.sub(r"\1", text)


def cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
