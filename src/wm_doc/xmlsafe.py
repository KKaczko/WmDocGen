from __future__ import annotations

from pathlib import Path

from lxml import etree


class XmlSecurityError(ValueError):
    """Raised when XML input contains disabled features such as DTD declarations."""


class XmlParseError(ValueError):
    """Raised when XML input cannot be parsed safely."""


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
        raise XmlParseError(f"Malformed XML in {path}: {exc}") from exc


def _reject_unsafe_declarations(raw: bytes, path: Path) -> None:
    lowered = raw.lower()
    if b"<!doctype" in lowered:
        raise XmlSecurityError(f"DTD declarations are disabled for {path}")
    if b"<!entity" in lowered:
        raise XmlSecurityError(f"Entity declarations are disabled for {path}")
