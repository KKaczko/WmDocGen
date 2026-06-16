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
from wm_doc.render.dot import render_dependency_dot
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
        ("password", "secret", "credential", "token", "private-key", "private key"), start=1
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
        assert marker not in _combined_outputs(analysis, service)

        _write_flow_with_mapset(service_dir / "flow.xml", f"/{term};1;0", marker)
        literal_analysis = analyze_path(case_root, config)
        literal_service = literal_analysis.packages[0].services[0]
        assert marker not in _combined_outputs(literal_analysis, literal_service)
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

    assert analysis.schema_version == "analysis.v4"
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


def _service_dir(tmp_path: Path) -> Path:
    service_dir = tmp_path / "Pkg" / "ns" / "foo" / "bar"
    service_dir.mkdir(parents=True)
    return service_dir


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
