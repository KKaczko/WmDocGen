from __future__ import annotations

import re
from pathlib import Path

from lxml import etree


class XmlSecurityError(ValueError):
    """Raised when XML input contains disabled features such as DTD declarations."""


class XmlParseError(ValueError):
    """Raised when XML input cannot be parsed safely."""


_FILE_URI_RE = re.compile(r"\bfile:///[^\s'\"<>),]+")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w])(?:[A-Za-z]:[\\/](?:[^\s:'\"<>\[\](),]+[\\/]?)+)"
)
_POSIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w])/(?:[^\s:'\"<>\[\](),]+/)+[^\s:'\"<>\[\](),]+"
)


def parse_xml_file(path: Path) -> etree._Element:
    raw = path.read_bytes()
    _reject_unsafe_declarations(raw, path)
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        recover=False,
        huge_tree=False,
        remove_blank_text=False,
    )
    try:
        return etree.fromstring(raw, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise XmlParseError(safe_xml_error_message("Malformed XML", exc)) from exc


def safe_xml_error_message(prefix: str, exc: Exception | str) -> str:
    reason = sanitize_xml_error_reason(str(exc))
    if not reason:
        return f"{prefix}."
    if reason == prefix or reason.startswith(f"{prefix}:"):
        return reason
    return f"{prefix}: {reason}"


def sanitize_xml_error_reason(message: str) -> str:
    text = " ".join(message.replace("\r", " ").replace("\n", " ").split())
    if not text:
        return ""
    for pattern in (
        _FILE_URI_RE,
        _WINDOWS_ABSOLUTE_PATH_RE,
        _POSIX_ABSOLUTE_PATH_RE,
    ):
        text = pattern.sub("<local-path>", text)
    text = text.replace("<string>", "XML input")
    text = re.sub(r"\bMalformed XML in\s+<local-path>\s*:\s*", "", text)
    text = text.replace(
        "DTD declarations are disabled for <local-path>",
        "DTD declarations are disabled for XML input.",
    )
    text = text.replace(
        "Entity declarations are disabled for <local-path>",
        "Entity declarations are disabled for XML input.",
    )
    return text.strip()


def _reject_unsafe_declarations(raw: bytes, path: Path) -> None:
    del path
    lowered = raw.lower()
    if b"<!doctype" in lowered:
        raise XmlSecurityError("DTD declarations are disabled for XML input.")
    if b"<!entity" in lowered:
        raise XmlSecurityError("Entity declarations are disabled for XML input.")
