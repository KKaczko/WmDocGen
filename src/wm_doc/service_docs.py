"""Per-service description files: one reviewed Markdown file per service.

Layout of `<docs-dir>/<Package>/<namespace folders>/<service>.md`::

    ---
    service: orders.api:createOrder
    package: Orders
    status: draft            # draft | approved
    model: qwen3.8:27b
    facts_hash: 3f9c...      # facts the narrative was written from or approved against
    text_hash: a81b...       # narrative as generated; a different hash means it was edited
    ---
    # createOrder
    ## Purpose ... ## Designer comment     <- narrative: AI draft, yours once edited/approved
    ## Notes                               <- yours only; never written by the tool
    <!-- wm-doc:facts:start hash=... -->   <- refreshed on every run, even when approved
    ...
    <!-- wm-doc:facts:end -->

Rules: a narrative that is approved, or that differs from what was generated, is never
overwritten. The facts block always shows the current facts; its marker carries their
hash, which `approve` copies into `facts_hash` so later changes are reported as
"approved, facts changed". Files contain no timestamps, so unchanged inputs give
byte-identical files.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

FACTS_START_RE = re.compile(r"<!-- wm-doc:facts:start(?: hash=([0-9a-f]+))? -->")
FACTS_END = "<!-- wm-doc:facts:end -->"
NOTES_HEADING = "## Notes"
NOTES_PLACEHOLDER = "<!-- Your notes. wm-doc never changes this section. -->"
COMMENT_HEADING = "## Designer comment"
PURPOSE_HEADING = "## Purpose"
MAX_DESIGNER_COMMENT_CHARS = 600
HASH_LENGTH = 16


class DocStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class DocState(StrEnum):
    """What the status report and `describe` see for one service."""

    MISSING = "missing"
    DRAFT = "draft"
    EDITED = "edited"  # a draft whose narrative was changed by hand
    APPROVED = "approved"
    STALE = "approved, facts changed"


@dataclass(frozen=True)
class Narrative:
    """The parts of a description the model drafts and a person owns afterwards."""

    purpose: str
    usage: str
    data_effects: str
    steps: tuple[str, ...]
    error_handling: str
    designer_comment: str

    def markdown(self) -> str:
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(self.steps, 1))
        return (
            f"{PURPOSE_HEADING}\n\n{self.purpose}\n\n"
            f"## Usage\n\n{self.usage}\n\n"
            f"## What it does to data\n\n{self.data_effects}\n\n"
            f"## Main steps\n\n{steps or '-'}\n\n"
            f"## Error handling\n\n{self.error_handling}\n\n"
            f"{COMMENT_HEADING}\n\n```text\n{self.designer_comment}\n```\n"
        )


@dataclass
class ServiceDoc:
    service: str
    package: str
    status: DocStatus
    model: str
    facts_hash: str
    text_hash: str
    narrative: str  # Markdown from "## Purpose" up to "## Notes"
    notes: str = NOTES_PLACEHOLDER
    facts_markdown: str = ""
    current_facts_hash: str = ""
    extra_front_matter: dict[str, Any] = field(default_factory=dict)

    @property
    def edited(self) -> bool:
        return text_hash(self.narrative) != self.text_hash

    @property
    def protected(self) -> bool:
        """True when the narrative belongs to a person and must not be regenerated."""
        return self.status is DocStatus.APPROVED or self.edited

    def state(self, facts_hash: str | None = None) -> DocState:
        current = facts_hash or self.current_facts_hash
        if self.status is DocStatus.APPROVED:
            return DocState.STALE if current and current != self.facts_hash else DocState.APPROVED
        return DocState.EDITED if self.edited else DocState.DRAFT

    def purpose_line(self) -> str | None:
        """First sentence of the Purpose section, used as context for callers' prompts."""
        section = _section(self.narrative, PURPOSE_HEADING)
        if not section:
            return None
        flat = " ".join(section.split())
        end = flat.find(". ")
        return flat[: end + 1] if end > 0 else flat

    def designer_comment(self) -> str:
        section = _section(self.narrative, COMMENT_HEADING)
        fenced = re.search(r"```(?:text)?\n(.*?)\n```", section, re.DOTALL)
        text = fenced.group(1) if fenced else section
        return " ".join(text.split())

    def render(self) -> str:
        front = {
            "service": self.service,
            "package": self.package,
            "status": self.status.value,
            "model": self.model,
            "facts_hash": self.facts_hash,
            "text_hash": self.text_hash,
            **self.extra_front_matter,
        }
        header = yaml.safe_dump(front, sort_keys=False, allow_unicode=True).strip()
        title = self.service.rsplit(":", 1)[-1]
        start = f"<!-- wm-doc:facts:start hash={self.current_facts_hash} -->"
        return (
            f"---\n{header}\n---\n# {title}\n\n`{self.service}`\n\n"
            f"{self.narrative.strip()}\n\n"
            f"{NOTES_HEADING}\n\n{self.notes.strip() or NOTES_PLACEHOLDER}\n\n"
            f"{start}\n{self.facts_markdown.strip()}\n{FACTS_END}\n"
        )


def text_hash(narrative: str) -> str:
    normalized = "\n".join(line.rstrip() for line in narrative.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def facts_hash(facts: str) -> str:
    return hashlib.sha256(facts.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def doc_path(docs_dir: Path, package: str, service: str) -> Path:
    namespace, _, name = service.rpartition(":")
    parts = [_safe(part) for part in namespace.split(".") if part]
    return docs_dir / _safe(package) / Path(*parts) / f"{_safe(name or service)}.md"


def new_doc(
    service: str,
    package: str,
    narrative: Narrative,
    *,
    model: str,
    facts: str,
    facts_markdown: str,
) -> ServiceDoc:
    markdown = narrative.markdown()
    current = facts_hash(facts)
    return ServiceDoc(
        service=service,
        package=package,
        status=DocStatus.DRAFT,
        model=model,
        facts_hash=current,
        text_hash=text_hash(markdown),
        narrative=markdown,
        facts_markdown=facts_markdown,
        current_facts_hash=current,
    )


def read_doc(path: Path) -> ServiceDoc | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return parse_doc(text)


def parse_doc(text: str) -> ServiceDoc | None:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    try:
        front = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(front, dict) or "service" not in front:
        return None
    body = text[end + len("\n---\n") :]
    facts_markdown = ""
    current = ""
    start = FACTS_START_RE.search(body)
    if start is not None:
        current = start.group(1) or ""
        stop = body.find(FACTS_END, start.end())
        facts_markdown = body[start.end() : stop if stop >= 0 else len(body)].strip()
        body = body[: start.start()]
    notes = NOTES_PLACEHOLDER
    notes_at = body.find(f"\n{NOTES_HEADING}\n")
    if notes_at >= 0:
        notes = body[notes_at + len(NOTES_HEADING) + 2 :].strip()
        body = body[:notes_at]
    purpose_at = body.find(PURPOSE_HEADING)
    narrative = body[purpose_at:].strip() if purpose_at >= 0 else ""
    known = {"service", "package", "status", "model", "facts_hash", "text_hash"}
    try:
        status = DocStatus(str(front.get("status", "draft")).strip().lower())
    except ValueError:
        status = DocStatus.DRAFT
    return ServiceDoc(
        service=str(front["service"]),
        package=str(front.get("package", "")),
        status=status,
        model=str(front.get("model", "")),
        facts_hash=str(front.get("facts_hash", "")),
        text_hash=str(front.get("text_hash", "")),
        narrative=narrative,
        notes=notes,
        facts_markdown=facts_markdown,
        current_facts_hash=current,
        extra_front_matter={k: v for k, v in front.items() if k not in known},
    )


def write_doc(path: Path, doc: ServiceDoc) -> bool:
    """Write the file only when its content changes; return whether it was written."""
    content = doc.render()
    try:
        if path.read_text(encoding="utf-8").replace("\r\n", "\n") == content:
            return False
    except OSError:
        pass
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".md.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)
    return True


def iter_docs(docs_dir: Path) -> list[tuple[Path, ServiceDoc]]:
    found: list[tuple[Path, ServiceDoc]] = []
    if not docs_dir.is_dir():
        return found
    for path in sorted(docs_dir.rglob("*.md"), key=lambda item: item.as_posix().casefold()):
        doc = read_doc(path)
        if doc is not None:
            found.append((path, doc))
    return found


def _section(markdown: str, heading: str) -> str:
    start = markdown.find(heading)
    if start < 0:
        return ""
    start += len(heading)
    following = markdown.find("\n## ", start)
    return markdown[start : following if following >= 0 else len(markdown)].strip()


def _safe(part: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.$-]+", "_", part) or "_"
