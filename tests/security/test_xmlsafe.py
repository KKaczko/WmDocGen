from __future__ import annotations

from pathlib import Path

import pytest

from wm_doc.xmlsafe import (
    XmlParseError,
    XmlSecurityError,
    parse_xml_file,
    sanitize_xml_error_reason,
)


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

    with pytest.raises(XmlSecurityError) as exc_info:
        parse_xml_file(unsafe)

    assert str(unsafe) not in str(exc_info.value)
    assert "XML input" in str(exc_info.value)


def test_parse_xml_file_rejects_external_dtd(tmp_path) -> None:
    unsafe = tmp_path / "external-dtd.xml"
    unsafe.write_text(
        """<?xml version="1.0"?>
<!DOCTYPE Values SYSTEM "http://example.invalid/evil.dtd">
<Values version="2.0"><value name="x">safe</value></Values>
""",
        encoding="utf-8",
    )

    with pytest.raises(XmlSecurityError) as exc_info:
        parse_xml_file(unsafe)

    assert str(unsafe) not in str(exc_info.value)
    assert "XML input" in str(exc_info.value)


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

    with pytest.raises(XmlSecurityError) as exc_info:
        parse_xml_file(unsafe)

    assert str(unsafe) not in str(exc_info.value)
    assert "XML input" in str(exc_info.value)


def test_parse_xml_file_rejects_late_prohibited_declaration(tmp_path) -> None:
    unsafe = tmp_path / "late-doctype.xml"
    unsafe.write_text(
        "<?xml version=\"1.0\"?>\n<!--" + ("x" * 5000) + "-->\n"
        "<!DOCTYPE Values [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]>\n"
        "<Values version=\"2.0\"><value name=\"x\">safe</value></Values>",
        encoding="utf-8",
    )

    with pytest.raises(XmlSecurityError) as exc_info:
        parse_xml_file(unsafe)

    assert str(unsafe) not in str(exc_info.value)
    assert "XML input" in str(exc_info.value)


def test_parse_xml_file_rejects_malformed_xml(tmp_path) -> None:
    malformed = tmp_path / "malformed.xml"
    malformed.write_text("<Values>", encoding="utf-8")

    with pytest.raises(XmlParseError) as exc_info:
        parse_xml_file(malformed)

    message = str(exc_info.value)
    assert str(malformed) not in message
    assert "Malformed XML:" in message
    assert "line" in message
    assert "column" in message


def test_xml_error_sanitizer_removes_cross_platform_absolute_paths() -> None:
    cases = [
        (
            r"Malformed XML in C:\Users\SecretUser\AppData\Local\Temp\pkg\node.ndf: "
            "mismatched tag, line 12, column 8",
            ["SecretUser", "AppData", "Local", "Temp", r"C:\\"],
        ),
        (
            "D:/private/workspace/flow.xml: invalid token, line 7, column 3",
            ["private", "workspace", "D:/"],
        ),
        (
            "/tmp/secret-user/pkg/node.ndf: expected closing element, line 4, column 2",
            ["secret-user", "/tmp/"],
        ),
        (
            "/home/private-user/project/flow.xml: unclosed element, line 9, column 1",
            ["private-user", "/home/"],
        ),
        (
            "file:///C:/Users/SecretUser/node.ndf: invalid token, line 5, column 6",
            ["SecretUser", "file://", "C:/"],
        ),
    ]

    for raw_message, forbidden in cases:
        sanitized = sanitize_xml_error_reason(raw_message)
        for marker in forbidden:
            assert marker not in sanitized
        assert "line" in sanitized
        assert "column" in sanitized
        assert any(
            phrase in sanitized
            for phrase in (
                "mismatched tag",
                "invalid token",
                "expected closing element",
                "unclosed element",
            )
        )


def test_xml_error_sanitizer_preserves_already_safe_messages() -> None:
    message = "mismatched tag, line 12, column 8"

    assert sanitize_xml_error_reason(message) == message


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
