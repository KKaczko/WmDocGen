from __future__ import annotations

from pathlib import Path

import pytest

from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file


def test_parse_xml_file_rejects_doctype(tmp_path) -> None:
    unsafe = tmp_path / "unsafe.xml"
    unsafe.write_text(
        """<?xml version="1.0"?>
<!DOCTYPE Values [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<Values version="2.0"><value name="x">&xxe;</value></Values>
""",
        encoding="utf-8",
    )

    with pytest.raises(XmlSecurityError):
        parse_xml_file(unsafe)


def test_parse_xml_file_rejects_external_dtd(tmp_path) -> None:
    unsafe = tmp_path / "external-dtd.xml"
    unsafe.write_text(
        """<?xml version="1.0"?>
<!DOCTYPE Values SYSTEM "http://example.invalid/evil.dtd">
<Values version="2.0"><value name="x">safe</value></Values>
""",
        encoding="utf-8",
    )

    with pytest.raises(XmlSecurityError):
        parse_xml_file(unsafe)


def test_parse_xml_file_rejects_entity_expansion(tmp_path) -> None:
    unsafe = tmp_path / "entity-expansion.xml"
    unsafe.write_text(
        """<?xml version="1.0"?>
<!DOCTYPE Values [
<!ENTITY a "1234567890">
<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
]>
<Values version="2.0"><value name="x">&b;</value></Values>
""",
        encoding="utf-8",
    )

    with pytest.raises(XmlSecurityError):
        parse_xml_file(unsafe)


def test_parse_xml_file_rejects_late_prohibited_declaration(tmp_path) -> None:
    unsafe = tmp_path / "late-doctype.xml"
    unsafe.write_text(
        "<?xml version=\"1.0\"?>\n<!--" + ("x" * 5000) + "-->\n"
        "<!DOCTYPE Values [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>\n"
        "<Values version=\"2.0\"><value name=\"x\">safe</value></Values>",
        encoding="utf-8",
    )

    with pytest.raises(XmlSecurityError):
        parse_xml_file(unsafe)


def test_parse_xml_file_rejects_malformed_xml(tmp_path) -> None:
    malformed = tmp_path / "malformed.xml"
    malformed.write_text("<Values>", encoding="utf-8")

    with pytest.raises(XmlParseError):
        parse_xml_file(malformed)


def test_parse_xml_file_accepts_normal_webmethods_xml() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "samples"
        / "OriginalSmall"
        / "OAAdapter"
        / "ns"
        / "oa"
        / "adapter"
        / "geographicAddressManagement"
        / "createGeographicAddressValidation"
        / "node.ndf"
    )

    root = parse_xml_file(path)

    assert root.tag == "Values"
