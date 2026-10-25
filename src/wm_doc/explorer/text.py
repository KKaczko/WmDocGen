"""Text that leaves the tool for the explorer: inert, bounded and disclosure-checked.

Everything the explorer shows is treated as untrusted. Identifiers (service names, paths) are
stripped of control and direction-override characters and capped. Free text (finding
messages, description text) is also run through the disclosure scan; text that fails it is
withheld and counted, never shown. The app renders all of it as plain text.
"""

from __future__ import annotations

import re

from wm_doc.disclosure import unsafe_disclosure_label

MAX_TEXT_CHARS = 4_000
MAX_NAME_CHARS = 512
# C0/C1 controls, zero-width and bidirectional formatting characters, line/paragraph separators.
_INVISIBLE_RE = re.compile(
    "[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2028-\u2029"
    "\u2060-\u2069\ufeff]"
)
_ABSOLUTE_PATH_RE = re.compile(r"^(?:[A-Za-z]:|/|\\\\|~)")


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
        flat = " ".join(_INVISIBLE_RE.sub(" ", text).split())
        if not flat:
            return None
        label = unsafe_disclosure_label(flat)
        if label is not None:
            self.withheld += 1
            return f"[withheld: {label}]"
        return cap(flat, limit)


def cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
