from __future__ import annotations

from pathlib import Path

from wm_doc.analysis import analyze_path
from wm_doc.config import (
    DEFAULT_CONFIG,
    AppConfig,
    ExtractionConfig,
    ExtractionMode,
    FreeTextExtractionConfig,
    LiteralExtractionConfig,
)
from wm_doc.discovery import scan_path
from wm_doc.render.analysis_json import render_analysis_json
from wm_doc.render.document_markdown import render_document_markdown
from wm_doc.render.dot import render_dependency_dot, render_document_dot
from wm_doc.render.service_markdown import render_service_markdown


def test_unknown_flow_element_finding(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"><CUSTOMSTEP /></FLOW>""",
        encoding="utf-8",
    )

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]

    assert any(finding.code == "UNSUPPORTED_FLOW_ELEMENT" for finding in service.findings)


def test_malformed_flow_xml_finding(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text("<FLOW>", encoding="utf-8")

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]

    assert any(finding.code == "XML_MALFORMED" for finding in service.findings)


def test_missing_flow_xml_finding_in_analysis(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]

    assert any(finding.code == "FLOW_XML_MISSING" for finding in service.findings)


def test_missing_node_ndf_remains_inventory_finding(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""", encoding="utf-8"
    )

    package = scan_path(tmp_path).packages[0]

    assert package.artifacts[0].probable_type == "flow_xml_without_node"
    assert any(finding.code == "NODE_NDF_MISSING" for finding in package.findings)


def test_unresolved_invocation_target_is_retained(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="external.pkg:missing" />
</FLOW>""",
        encoding="utf-8",
    )

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]

    assert service.call_occurrences[0].target == "external.pkg:missing"
    assert service.call_occurrences[0].resolved is False
    assert service.unique_dependencies[0].target_service == "external.pkg:missing"
    assert service.unique_dependencies[0].resolved is False


def test_literal_redact_include_omit_and_secret_guard(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")
    _write_flow_with_mapset(service_dir / "flow.xml", "/target;1;0", "visible-value")

    default_service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]
    literal = default_service.mapping_operations[0].literal
    assert literal is not None
    assert literal.disclosure == "REDACTED"
    assert literal.length == len("visible-value")
    assert literal.value is None
    assert "visible-value" not in render_analysis_json(analyze_path(tmp_path, DEFAULT_CONFIG))

    include_config = _config(literal_mode=ExtractionMode.INCLUDE)
    include_service = analyze_path(tmp_path, include_config).packages[0].services[0]
    include_literal = include_service.mapping_operations[0].literal
    assert include_literal is not None
    assert include_literal.disclosure == "INCLUDED"
    assert include_literal.value == "visible-value"

    omit_config = _config(literal_mode=ExtractionMode.OMIT)
    omit_service = analyze_path(tmp_path, omit_config).packages[0].services[0]
    omit_literal = omit_service.mapping_operations[0].literal
    assert omit_literal is not None
    assert omit_literal.disclosure == "OMITTED"
    assert omit_literal.length is None
    assert omit_literal.value is None

    _write_flow_with_mapset(service_dir / "flow.xml", "/password;1;0", "dontprintme")
    secret_service = analyze_path(tmp_path, include_config).packages[0].services[0]
    secret_literal = secret_service.mapping_operations[0].literal
    assert secret_literal is not None
    assert secret_literal.disclosure == "BLOCKED_SECRET"
    assert secret_literal.value is None
    assert any(finding.code == "SECRET_LITERAL_REDACTED" for finding in secret_service.findings)
    assert "dontprintme" not in render_analysis_json(analyze_path(tmp_path, include_config))


def test_free_text_disclosure_policy(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf", comment="operator note")
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""", encoding="utf-8"
    )

    included = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]
    redacted = analyze_path(
        tmp_path, _config(free_text_mode=ExtractionMode.REDACT)
    ).packages[0].services[0]
    omitted = analyze_path(
        tmp_path, _config(free_text_mode=ExtractionMode.OMIT)
    ).packages[0].services[0]

    assert included.description is not None
    assert included.description.value == "operator note"
    assert redacted.description is not None
    assert redacted.description.marker == "<redacted:free-text>"
    assert omitted.description is not None
    assert omitted.description.disclosure == "OMITTED"


def test_free_text_policy_covers_flow_labels_and_attributes(tmp_path) -> None:
    markers = {
        "description": "SAFE_DESCRIPTION_MARKER",
        "sequence": "SAFE_SEQUENCE_MARKER",
        "branch_case": "SAFE_BRANCH_CASE_MARKER",
        "loop": "SAFE_LOOP_MARKER",
        "map": "SAFE_MAP_MARKER",
        "operation": "SAFE_OPERATION_MARKER",
        "display": "SAFE_DISPLAY_MARKER",
        "comment": "SAFE_COMMENT_MARKER",
        "unknown": "SAFE_UNKNOWN_MARKER",
    }
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf", comment=markers["description"])
    _write_flow_with_text_markers(service_dir / "flow.xml", markers)

    include_analysis = analyze_path(tmp_path, _config(free_text_mode=ExtractionMode.INCLUDE))
    include_service = include_analysis.packages[0].services[0]
    include_payload = _combined_outputs(include_analysis, include_service)

    for key in ("description", "sequence", "branch_case", "loop", "map", "operation", "display"):
        assert markers[key] in include_payload
    assert markers["comment"] not in include_payload
    assert markers["unknown"] not in include_payload

    redact_analysis = analyze_path(tmp_path, _config(free_text_mode=ExtractionMode.REDACT))
    redact_service = redact_analysis.packages[0].services[0]
    redact_payload = _combined_outputs(redact_analysis, redact_service)
    for marker in markers.values():
        assert marker not in redact_payload
    assert "<redacted:free-text>" in redact_payload
    assert "<redacted:attribute>" in redact_payload

    omit_analysis = analyze_path(tmp_path, _config(free_text_mode=ExtractionMode.OMIT))
    omit_service = omit_analysis.packages[0].services[0]
    omit_payload = _combined_outputs(omit_analysis, omit_service)
    for marker in markers.values():
        assert marker not in omit_payload
    assert "<redacted:free-text>" not in omit_payload
    assert "<redacted:attribute>" not in omit_payload

    sequence = omit_service.flow_tree.children[0] if omit_service.flow_tree else None
    assert sequence is not None
    assert sequence.label is not None
    assert sequence.label.disclosure == "OMITTED"
    mapping_operation = omit_service.mapping_operations[0]
    assert "NAME" not in mapping_operation.raw_attrs
    assert "X-UNKNOWN" not in mapping_operation.raw_attrs
    assert "FROM" in mapping_operation.raw_attrs
    assert "TO" in mapping_operation.raw_attrs


def test_secret_guard_covers_free_text_and_literals_under_include(tmp_path) -> None:
    for index, term in enumerate(
        (
            "password",
            "secret",
            "credential",
            "token",
            "private key",
            "private-key",
            "private_key",
            "privatekey",
        ),
        start=1,
    ):
        marker = f"SAFE_{term.replace(' ', '_').replace('-', '_').upper()}_MARKER"
        case_root = tmp_path / f"{index}_{term.replace(' ', '_').replace('-', '_')}"
        service_dir = _service_dir(case_root)
        _write_node(service_dir / "node.ndf", comment=marker)
        _write_flow_with_text_markers(
            service_dir / "flow.xml",
            {
                "description": marker,
                "sequence": marker,
                "branch_case": marker,
                "loop": marker,
                "map": marker,
                "operation": marker,
                "display": marker,
                "comment": marker,
                "unknown": marker,
            },
        )
        config = _config(
            literal_mode=ExtractionMode.INCLUDE, free_text_mode=ExtractionMode.INCLUDE
        )
        analysis = analyze_path(case_root, config)
        service = analysis.packages[0].services[0]
        _assert_marker_absent_from_disclosure_surfaces(analysis, service, marker)
        _assert_marker_absent_from_raw_attribute_collections(service, marker)

        _write_flow_with_mapset(service_dir / "flow.xml", f"/{term};1;0", marker)
        literal_analysis = analyze_path(case_root, config)
        literal_service = literal_analysis.packages[0].services[0]
        _assert_marker_absent_from_disclosure_surfaces(
            literal_analysis, literal_service, marker
        )
        _assert_marker_absent_from_raw_attribute_collections(literal_service, marker)
        literal = literal_service.mapping_operations[0].literal
        assert literal is not None
        assert literal.disclosure == "BLOCKED_SECRET"


def test_policy_snapshot_records_secret_guard(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""", encoding="utf-8"
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    payload = render_analysis_json(analysis)

    assert analysis.schema_version == "analysis.v5"
    assert analysis.extraction_policy.literal_mode == "redact"
    assert analysis.extraction_policy.free_text_mode == "include"
    assert analysis.extraction_policy.secret_guard.enabled is True
    assert analysis.extraction_policy.secret_guard.strategy_version == "secret-guard.v1"
    assert "D:/Dev" not in payload
    assert "D:\\Dev" not in payload


def test_mapping_error_findings_are_explicit(tmp_path) -> None:
    service_dir = _service_dir(tmp_path)
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<MAP MODE="STANDALONE">
  <MAPCOPY TO="/target;1;0" />
  <MAPCOPY FROM="relativePath" TO="/target;1;0" />
  <MAPSET FIELD="/target;1;0" />
  <MAPSET FIELD="/other;1;0">
    <DATA ENCODING="plain"><Values version="2.0"><value name="xml">x</value></Values></DATA>
  </MAPSET>
  <MAPDELETE />
</MAP>
</FLOW>""",
        encoding="utf-8",
    )

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]
    codes = {finding.code for finding in service.findings}

    assert "MISSING_MAPPING_ENDPOINT" in codes
    assert "MALFORMED_PIPELINE_PATH" in codes
    assert "MISSING_LITERAL_DATA" in codes
    assert "UNSUPPORTED_LITERAL_ENCODING" in codes


def test_document_type_edge_findings_are_explicit(tmp_path) -> None:
    doc_a = _document_dir(tmp_path, "docs", "A")
    doc_b = _document_dir(tmp_path, "docs", "B")
    _write_document_node(
        doc_a / "node.ndf",
        "docs:A",
        """
      <record javaclass="com.wm.util.Values">
        <value name="field_name">toB</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
        <value name="rec_ref">docs:B</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">missingTarget</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
        <value name="rec_ref">docs:Missing</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">noTarget</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">mystery</value>
        <value name="field_type">mystery</value>
        <value name="field_dim">x</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">toB</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
      </record>
""",
    )
    _write_document_node(
        doc_b / "node.ndf",
        "docs:B",
        """
      <record javaclass="com.wm.util.Values">
        <value name="field_name">toA</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
        <value name="rec_ref">docs:A</value>
      </record>
""",
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    codes = {finding.code for finding in analysis.findings}

    assert analysis.metrics.document_type_count == 2
    assert analysis.metrics.document_reference_occurrence_count == 3
    assert analysis.metrics.resolved_document_reference_count == 2
    assert analysis.metrics.unresolved_document_reference_count == 1
    assert "UNKNOWN_FIELD_TYPE" in codes
    assert "INVALID_DIMENSION" in codes
    assert "MISSING_FIELD_NAME" in codes
    assert "MISSING_DOCUMENT_REFERENCE_TARGET" in codes
    assert "DUPLICATE_FIELD_NAME" in codes
    assert "UNRESOLVED_DOCUMENT_REFERENCE" in codes
    assert "CYCLIC_DOCUMENT_REFERENCE" in codes
    assert any(
        dependency.target_document == "docs:Missing" and not dependency.resolved
        for dependency in analysis.document_dependencies
    )


def test_document_free_text_and_unknown_metadata_follow_disclosure_policy(tmp_path) -> None:
    marker = "SAFE_DOCUMENT_TEXT_MARKER"
    unknown_marker = "SAFE_DOCUMENT_UNKNOWN_MARKER"
    doc_dir = _document_dir(tmp_path, "docs", "SafeDoc")
    _write_document_node(
        doc_dir / "node.ndf",
        "docs:SafeDoc",
        f"""
      <record javaclass="com.wm.util.Values">
        <value name="field_name">field</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
        <value name="node_comment">{marker}</value>
        <value name="x_unknown">{unknown_marker}</value>
      </record>
""",
        comment=marker,
    )

    include_analysis = analyze_path(
        tmp_path, _config(free_text_mode=ExtractionMode.INCLUDE)
    )
    include_payload = render_analysis_json(include_analysis)
    assert marker in include_payload
    assert unknown_marker not in include_payload

    redact_analysis = analyze_path(
        tmp_path, _config(free_text_mode=ExtractionMode.REDACT)
    )
    redact_payload = render_analysis_json(redact_analysis)
    assert marker not in redact_payload
    assert unknown_marker not in redact_payload
    assert "<redacted:free-text>" in redact_payload
    assert "<redacted:attribute>" in redact_payload

    omit_analysis = analyze_path(tmp_path, _config(free_text_mode=ExtractionMode.OMIT))
    omit_payload = render_analysis_json(omit_analysis)
    assert marker not in omit_payload
    assert unknown_marker not in omit_payload
    assert "<redacted:free-text>" not in omit_payload


def test_document_markdown_renders_disclosure_policy_modes(tmp_path) -> None:
    cases = [
        ("include-redact", ExtractionMode.INCLUDE, ExtractionMode.REDACT),
        ("redact-redact", ExtractionMode.REDACT, ExtractionMode.REDACT),
        ("omit-redact", ExtractionMode.OMIT, ExtractionMode.REDACT),
        ("include-include", ExtractionMode.INCLUDE, ExtractionMode.INCLUDE),
        ("include-omit", ExtractionMode.INCLUDE, ExtractionMode.OMIT),
    ]
    for name, free_text_mode, literal_mode in cases:
        case_root = tmp_path / name
        doc_dir = _document_dir(case_root, "docs", "PolicyDoc")
        _write_document_node(
            doc_dir / "node.ndf",
            "docs:PolicyDoc",
            """
      <record javaclass="com.wm.util.Values">
        <value name="field_name">field</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
      </record>
""",
        )
        config = _config(literal_mode=literal_mode, free_text_mode=free_text_mode)
        analysis = analyze_path(case_root, config)
        markdown = _render_first_document_markdown(analysis)

        assert "## Disclosure Policies" in markdown
        assert f"- Free text mode: {free_text_mode.value}" in markdown
        assert f"- Literal mode: {literal_mode.value}" in markdown
        assert "- Secret guard: enabled" in markdown
        assert "- Secret guard strategy: secret-guard.v1" in markdown


def test_malformed_nested_record_findings_are_explicit(tmp_path) -> None:
    doc_dir = _document_dir(tmp_path, "docs", "MalformedNested")
    _write_document_node(
        doc_dir / "node.ndf",
        "docs:MalformedNested",
        """
      <record javaclass="com.wm.util.Values">
        <value name="field_name">badShape</value>
        <value name="field_type">record</value>
        <value name="field_dim">0</value>
        <record name="rec_fields">
          <value name="notAnArray">x</value>
        </record>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">badChild</value>
        <value name="field_type">record</value>
        <value name="field_dim">0</value>
        <array name="rec_fields" type="record" depth="1">
          <value name="notARecord">x</value>
        </array>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">outer</value>
        <value name="field_type">record</value>
        <value name="field_dim">0</value>
        <array name="rec_fields" type="record" depth="1">
          <record javaclass="com.wm.util.Values">
            <value name="field_name">innerBad</value>
            <value name="field_type">record</value>
            <value name="field_dim">0</value>
            <array name="rec_fields" type="record" depth="1">
              <value name="notARecord">x</value>
            </array>
          </record>
        </array>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">validEmpty</value>
        <value name="field_type">record</value>
        <value name="field_dim">0</value>
        <array name="rec_fields" type="record" depth="1" />
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">validParent</value>
        <value name="field_type">record</value>
        <value name="field_dim">0</value>
        <array name="rec_fields" type="record" depth="1">
          <record javaclass="com.wm.util.Values">
            <value name="field_name">child</value>
            <value name="field_type">string</value>
            <value name="field_dim">0</value>
          </record>
        </array>
      </record>
""",
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    document = analysis.document_types[0]
    malformed = [
        finding for finding in document.findings if finding.code == "MALFORMED_NESTED_RECORD"
    ]
    payload = render_analysis_json(analysis)

    assert analysis.metrics.document_type_count == 1
    assert len(document.fields) == 5
    assert {field.name for field in document.fields} == {
        "badShape",
        "badChild",
        "outer",
        "validEmpty",
        "validParent",
    }
    assert len(malformed) == 3
    assert all(finding.severity == "WARNING" for finding in malformed)
    assert all(finding.confidence == "PARTIALLY_INTERPRETED" for finding in malformed)
    assert all(finding.source.line is not None for finding in malformed)
    assert any(finding.source.source_node == "badShape" for finding in malformed)
    assert any(finding.source.source_node == "badChild" for finding in malformed)
    assert any(finding.source.source_node == "outer/innerBad" for finding in malformed)
    assert not any("validEmpty" in finding.message for finding in malformed)
    assert not any("validParent" in finding.message for finding in malformed)
    assert "<record" not in payload
    assert "<array" not in payload


def test_unsupported_document_metadata_findings_are_policy_safe(tmp_path) -> None:
    marker = "SAFE_UNSUPPORTED_METADATA_MARKER"
    secret_marker = "SAFE_SECRET_TOKEN_MARKER"
    for name, free_text_mode, literal_mode in (
        ("default", ExtractionMode.INCLUDE, ExtractionMode.REDACT),
        ("redact", ExtractionMode.REDACT, ExtractionMode.REDACT),
        ("omit", ExtractionMode.OMIT, ExtractionMode.REDACT),
        ("literal-include", ExtractionMode.REDACT, ExtractionMode.INCLUDE),
    ):
        case_root = tmp_path / name
        doc_dir = _document_dir(case_root, "docs", "UnsupportedMetadata")
        _write_document_node(
            doc_dir / "node.ndf",
            "docs:UnsupportedMetadata",
            f"""
      <record javaclass="com.wm.util.Values">
        <value name="field_name">first</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
        <value name="field_content_type">record</value>
        <value name="x_extra">{marker}</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">second</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
        <value name="x_extra">{secret_marker}</value>
      </record>
      <record javaclass="com.wm.util.Values">
        <value name="field_name">nested</value>
        <value name="field_type">record</value>
        <value name="field_dim">0</value>
        <value name="x_extra">{marker}</value>
        <array name="rec_fields" type="record" depth="1">
          <record javaclass="com.wm.util.Values">
            <value name="field_name">child</value>
            <value name="field_type">string</value>
            <value name="field_dim">0</value>
          </record>
        </array>
      </record>
""",
            extra_document_metadata=f'<value name="x_doc_extra">{marker}</value>',
        )
        config = _config(literal_mode=literal_mode, free_text_mode=free_text_mode)
        analysis = analyze_path(case_root, config)
        document = analysis.document_types[0]
        findings = [
            finding
            for finding in document.findings
            if finding.code == "UNSUPPORTED_DOCUMENT_METADATA"
        ]
        combined = _document_outputs(analysis)

        assert all(finding.severity == "INFO" for finding in findings)
        assert all(finding.confidence == "PARTIALLY_INTERPRETED" for finding in findings)
        if free_text_mode == ExtractionMode.OMIT:
            assert len(findings) == 2
            field_finding = next(
                finding for finding in findings if "field metadata" in finding.message
            )
            assert field_finding.occurrence_count == 3
            assert len(field_finding.sample_source_references) == 3
        else:
            assert len(findings) == 3
            redacted_field_finding = next(
                finding
                for finding in findings
                if "field metadata" in finding.message
                and "value disclosure: REDACTED" in finding.message
            )
            blocked_field_finding = next(
                finding
                for finding in findings
                if "field metadata" in finding.message
                and "value disclosure: BLOCKED_SECRET" in finding.message
            )
            assert redacted_field_finding.occurrence_count == 2
            assert len(redacted_field_finding.sample_source_references) == 2
            assert blocked_field_finding.occurrence_count == 1
        assert "field_content_type" not in "".join(finding.message for finding in findings)
        assert marker not in combined
        assert secret_marker not in combined
        assert "<Values" not in combined
        assert "<record" not in combined
        assert "x_extra" in combined
        assert "x_doc_extra" in combined


def _service_dir(tmp_path: Path) -> Path:
    service_dir = tmp_path / "Pkg" / "ns" / "foo" / "bar"
    service_dir.mkdir(parents=True)
    return service_dir


def _document_dir(tmp_path: Path, namespace: str, name: str) -> Path:
    document_dir = tmp_path / "Pkg" / "ns" / namespace / name
    document_dir.mkdir(parents=True)
    return document_dir


def _write_node(path: Path, comment: str = "") -> None:
    path.write_text(
        f"""<Values version="2.0">
  <value name="svc_type">flow</value>
  <value name="node_comment">{comment}</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )


def _write_document_node(
    path: Path,
    full_name: str,
    fields_xml: str,
    comment: str = "",
    extra_document_metadata: str = "",
) -> None:
    path.write_text(
        f"""<Values version="2.0">
  <record name="record" javaclass="com.wm.util.Values">
    <value name="node_type">record</value>
    <value name="node_nsName">{full_name}</value>
    <value name="node_pkg">Pkg</value>
    <value name="node_comment">{comment}</value>
    <value name="field_type">record</value>
    <value name="field_dim">0</value>
{extra_document_metadata}
    <array name="rec_fields" type="record" depth="1">
{fields_xml}
    </array>
  </record>
</Values>""",
        encoding="utf-8",
    )


def _write_flow_with_mapset(path: Path, field: str, value: str) -> None:
    path.write_text(
        f"""<FLOW VERSION="3.0" CLEANUP="true">
<MAP MODE="STANDALONE">
  <MAPSET FIELD="{field}">
    <DATA ENCODING="XMLValues" I18N="true">
      <Values version="2.0">
        <value name="xml">{value}</value>
        <record name="type">
          <value name="field_name">{field.strip('/').split(';', 1)[0]}</value>
          <value name="field_type">string</value>
        </record>
      </Values>
    </DATA>
  </MAPSET>
</MAP>
</FLOW>""",
        encoding="utf-8",
    )


def _write_flow_with_text_markers(path: Path, markers: dict[str, str]) -> None:
    path.write_text(
        f"""<FLOW VERSION="3.0" CLEANUP="true">
<COMMENT>{markers["comment"]}</COMMENT>
<SEQUENCE NAME="{markers["sequence"]}" DISPLAY-NAME="{markers["display"]}">
  <BRANCH SWITCH="/status;1;0">
    <SEQUENCE NAME="{markers["branch_case"]}">
      <LOOP NAME="{markers["loop"]}" IN-ARRAY="/items;4;1">
        <MAP NAME="{markers["map"]}" MODE="STANDALONE">
          <MAPCOPY NAME="{markers["operation"]}" DISPLAY-LABEL="{markers["display"]}"
            X-UNKNOWN="{markers["unknown"]}" FROM="/source;1;0" TO="/target;1;0" />
        </MAP>
      </LOOP>
    </SEQUENCE>
  </BRANCH>
</SEQUENCE>
</FLOW>""",
        encoding="utf-8",
    )


def _combined_outputs(analysis, service) -> str:
    return (
        render_analysis_json(analysis)
        + render_service_markdown(service)
        + render_dependency_dot(analysis)
        + "".join(finding.message for finding in service.findings)
    )


def _render_first_document_markdown(analysis) -> str:
    return render_document_markdown(
        analysis.document_types[0],
        analysis.document_reference_occurrences,
        analysis.document_dependencies,
        analysis.service_document_dependencies,
        analysis.extraction_policy,
    )


def _document_outputs(analysis) -> str:
    document_markdown = "".join(
        render_document_markdown(
            document,
            analysis.document_reference_occurrences,
            analysis.document_dependencies,
            analysis.service_document_dependencies,
            analysis.extraction_policy,
        )
        for document in analysis.document_types
    )
    finding_messages = "".join(finding.message for finding in analysis.findings)
    finding_messages += "".join(
        finding.message
        for document in analysis.document_types
        for finding in document.findings
    )
    return (
        render_analysis_json(analysis)
        + document_markdown
        + render_document_dot(analysis)
        + render_dependency_dot(analysis)
        + finding_messages
    )


def _assert_marker_absent_from_disclosure_surfaces(analysis, service, marker: str) -> None:
    assert marker not in render_analysis_json(analysis)
    assert marker not in render_service_markdown(service)
    assert marker not in render_dependency_dot(analysis)
    assert marker not in "".join(finding.message for finding in service.findings)


def _assert_marker_absent_from_raw_attribute_collections(service, marker: str) -> None:
    collections: list[dict[str, str]] = []
    collections.extend(flow_map.raw_attrs for flow_map in service.flow_maps)
    collections.extend(flow_map.technical_attrs for flow_map in service.flow_maps)
    collections.extend(operation.raw_attrs for operation in service.mapping_operations)
    collections.extend(operation.technical_attrs for operation in service.mapping_operations)

    def visit(node) -> None:
        collections.append(node.attributes)
        for child in node.children:
            visit(child)

    if service.flow_tree is not None:
        visit(service.flow_tree)

    for attributes in collections:
        assert marker not in "".join(attributes.values())


def _config(
    *,
    literal_mode: ExtractionMode = ExtractionMode.REDACT,
    free_text_mode: ExtractionMode = ExtractionMode.INCLUDE,
) -> AppConfig:
    return AppConfig(
        classification=DEFAULT_CONFIG.classification,
        extraction=ExtractionConfig(
            literals=LiteralExtractionConfig(mode=literal_mode),
            freeText=FreeTextExtractionConfig(mode=free_text_mode),
        ),
    )
