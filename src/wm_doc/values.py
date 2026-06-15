from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from wm_doc.xmlsafe import parse_xml_file

ValuesData = dict[str, Any]


def parse_values_file(path: Path) -> ValuesData:
    root = parse_xml_file(path)
    if root.tag != "Values":
        return {}
    return _parse_children(root)


def scalar_value(data: ValuesData, name: str) -> str | None:
    value = data.get(name)
    if isinstance(value, str):
        return value
    return None


def record_value(data: ValuesData, name: str) -> ValuesData | None:
    value = data.get(name)
    if isinstance(value, dict):
        return value
    return None


def _parse_children(element: etree._Element) -> ValuesData:
    parsed: ValuesData = {}
    for child in element:
        name = child.get("name")
        value = _parse_node(child)
        if name is None:
            continue
        if name in parsed:
            existing = parsed[name]
            if isinstance(existing, list):
                existing.append(value)
            else:
                parsed[name] = [existing, value]
        else:
            parsed[name] = value
    return parsed


def _parse_node(element: etree._Element) -> Any:
    if element.tag == "value":
        return element.text or ""
    if element.tag == "null":
        return None
    if element.tag == "record":
        return _parse_children(element)
    if element.tag == "array":
        return [_parse_node(child) for child in element]
    return _parse_children(element)
