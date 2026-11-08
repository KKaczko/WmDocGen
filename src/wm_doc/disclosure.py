"""Disclosure scan for model-written text before it is cached or written to a file."""

from __future__ import annotations

import re

from wm_doc.secret_guard import secret_value_label

# A JDBC URL: `jdbc:<driver>:...` (jdbc:oracle:thin:@host, jdbc:mysql://host, jdbc:wm://host).
# A namespace name such as `orders.jdbc:OrdersConnection` is not one.
JDBC_RE = re.compile(r"(?i)(?<![\w.])jdbc:[a-z][\w+.-]*:[^\s,|}\]]*")
WINDOWS_ABSOLUTE_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s|}\]]+")
POSIX_ABSOLUTE_RE = re.compile(r"(?<![\w.])/(?:Users|home|tmp|var|etc|mnt|opt)/[^\s|}\]]*")
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
HTML_TAG_RE = re.compile(r"<[A-Za-z][^>]*>")
PROMPT_DISCLOSURE_RE = re.compile(
    r"(?i)\b(system prompt|hidden prompt|developer message|chain[- ]of[- ]thought)\b"
)


def unsafe_disclosure_label(text: str) -> str | None:
    """Name the first kind of content that must not be published, or None when clean."""
    secret = secret_value_label(text)
    if secret is not None:
        return secret
    if JDBC_RE.search(text):
        return "connection string"
    if WINDOWS_ABSOLUTE_RE.search(text) or POSIX_ABSOLUTE_RE.search(text):
        return "absolute path"
    if "Traceback (most recent call last)" in text:
        return "traceback"
    if MARKDOWN_LINK_RE.search(text):
        return "unsafe Markdown link"
    if HTML_TAG_RE.search(text):
        return "raw HTML"
    if PROMPT_DISCLOSURE_RE.search(text):
        return "prompt disclosure"
    if "<FLOW" in text or "<Values" in text or "public static" in text:
        return "raw package code or XML"
    return None
