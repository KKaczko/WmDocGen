"""Disclosure scan for model-written text before it is cached or written to a file."""

from __future__ import annotations

import re

SECRET_KEY_VALUE_RE = re.compile(
    r"(?P<key_quote>['\"]?)"
    r"(?P<key>[A-Za-z0-9_.-]*(?:password|passwd|pwd|passphrase|token|api[-_]?key|"
    r"client[-_]?secret)[A-Za-z0-9_.-]*)"
    r"(?P=key_quote)\s*(?P<separator>[:=]\s*)"
    r"(?P<value>['\"]?)[^\s,|}\]]+",
    re.IGNORECASE,
)
AUTHORIZATION_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)[^\s,|}\]]+")
BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s,|}\]]+")
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
    if SECRET_KEY_VALUE_RE.search(text):
        return "secret-like key/value"
    if AUTHORIZATION_RE.search(text) or BEARER_RE.search(text):
        return "authorization header or bearer value"
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
