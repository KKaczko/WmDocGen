from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
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
from wm_doc.render.document_markdown import document_markdown_filename, render_document_markdown
from wm_doc.render.dot import (
    render_dependency_dot,
    render_document_dot,
    render_process_dot,
    write_process_dots,
)
from wm_doc.render.index_markdown import render_documentation_index
from wm_doc.render.process_markdown import (
    render_entrypoint_candidates_markdown,
    render_process_markdown,
    write_entrypoint_candidates_markdown,
    write_process_markdown,
)
from wm_doc.render.service_markdown import (
    render_service_markdown,
    service_markdown_filename,
    write_service_markdown,
)

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]\n]*\]\(([^)\n]+)\)")
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


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


def test_opaque_service_common_metadata_is_preserved_without_body_analysis(tmp_path) -> None:
    service_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="selectCustomer")
    _write_opaque_node(
        service_dir / "node.ndf",
        svc_type="customAdapter",
        comment="Adapter service description",
        signature_fields="""\
      <record>
        <value name="field_name">customerId</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
      </record>""",
    )

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]

    assert service.identity.full_name == "pkg.adapter:selectCustomer"
    assert service.service_type == "OPAQUE"
    assert service.source_service_type == "customAdapter"
    assert service.analysis_status == "OPAQUE"
    assert service.description_status == "SOURCE_DESCRIPTION"
    assert service.description is not None
    assert service.description.value == "Adapter service description"
    assert [field.name for field in service.signature.inputs] == ["customerId"]
    assert service.flow_tree is None
    assert service.java_analysis is None
    assert service.call_occurrences == []
    assert service.unique_dependencies == []
    assert any(
        finding.code == "OPAQUE_SERVICE_IMPLEMENTATION_NOT_ANALYZED"
        and finding.severity == "INFO"
        for finding in service.findings
    )


def test_opaque_service_resolves_as_exact_call_target(tmp_path) -> None:
    caller_dir = _service_dir(tmp_path, namespace="pkg.flow", name="caller")
    _write_node(caller_dir / "node.ndf")
    (caller_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="pkg.adapter:sharedName" />
<INVOKE SERVICE="pkg.other:sharedName" />
</FLOW>""",
        encoding="utf-8",
    )
    opaque_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="sharedName")
    _write_opaque_node(opaque_dir / "node.ndf", svc_type="customAdapter")
    other_dir = _service_dir(tmp_path, namespace="pkg.other", name="sharedName")
    _write_node(other_dir / "node.ndf")
    (other_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""", encoding="utf-8"
    )

    caller = next(
        service
        for service in analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services
        if service.identity.full_name == "pkg.flow:caller"
    )
    by_target = {call.target: call for call in caller.call_occurrences}

    assert by_target["pkg.adapter:sharedName"].resolved is True
    assert by_target["pkg.adapter:sharedName"].target_type == "OPAQUE"
    assert by_target["pkg.adapter:sharedName"].target_analysis_status == "OPAQUE"
    assert by_target["pkg.other:sharedName"].resolved is True
    assert by_target["pkg.other:sharedName"].target_type == "FLOW"
    assert {
        dependency.target_service: dependency.target_analysis_status
        for dependency in caller.unique_dependencies
    } == {
        "pkg.adapter:sharedName": "OPAQUE",
        "pkg.other:sharedName": "FULL",
    }
    dot = render_dependency_dot(analyze_path(tmp_path, DEFAULT_CONFIG))
    assert 'kind="opaque_service"' in dot
    assert "pkg.adapter:sharedName" in dot


def test_opaque_service_disclosure_and_secret_guard(tmp_path) -> None:
    marker = "jdbc:wm://host.example:5555 password=hunter2"
    service_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="secretish")
    _write_opaque_node(
        service_dir / "node.ndf",
        svc_type="customAdapter",
        comment=marker,
        extra_values=f"<value name=\"connectionConfig\">{marker}</value>",
    )

    include_analysis = analyze_path(
        tmp_path,
        _config(free_text_mode=ExtractionMode.INCLUDE),
    )
    include_service = include_analysis.packages[0].services[0]
    assert include_service.description_status == "DESCRIPTION_BLOCKED_SECRET"
    assert marker not in render_analysis_json(include_analysis)
    assert marker not in render_service_markdown(include_service)
    assert marker not in render_dependency_dot(include_analysis)

    runner = CliRunner()
    output_dir = tmp_path / "out"
    result = runner.invoke(app, ["analyze", str(tmp_path), "--output", str(output_dir)])
    assert result.exit_code == 0
    assert marker not in result.output

    redacted = analyze_path(
        tmp_path,
        _config(free_text_mode=ExtractionMode.REDACT),
    ).packages[0].services[0]
    omitted = analyze_path(
        tmp_path,
        _config(free_text_mode=ExtractionMode.OMIT),
    ).packages[0].services[0]
    assert redacted.description_status == "DESCRIPTION_BLOCKED_SECRET"
    assert omitted.description_status == "DESCRIPTION_OMITTED"


def test_opaque_service_malformed_common_metadata_findings(tmp_path) -> None:
    service_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="broken")
    _write_opaque_node(
        service_dir / "node.ndf",
        svc_type="customAdapter",
        comment_xml="<record name=\"node_comment\" />",
        signature_fields="<value name=\"rec_fields\">not-array</value>",
    )

    service = analyze_path(tmp_path, DEFAULT_CONFIG).packages[0].services[0]
    codes = {finding.code for finding in service.findings}

    assert service.description is None
    assert service.description_status == "DESCRIPTION_MALFORMED"
    assert "SERVICE_DESCRIPTION_MALFORMED" in codes
    assert "SERVICE_SIGNATURE_METADATA_PARTIAL" in codes


def test_opaque_dependency_ids_are_stable_with_unrelated_service_insertion(
    tmp_path,
) -> None:
    caller_dir = _service_dir(tmp_path, namespace="pkg.flow", name="caller")
    _write_node(caller_dir / "node.ndf")
    (caller_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="pkg.adapter:target" />
</FLOW>""",
        encoding="utf-8",
    )
    target_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="target")
    _write_opaque_node(target_dir / "node.ndf", svc_type="customAdapter")

    original = analyze_path(tmp_path, DEFAULT_CONFIG)
    original_dependency = next(
        dependency
        for dependency in original.unique_dependencies
        if dependency.target_service == "pkg.adapter:target"
    )

    unrelated_dir = _service_dir(tmp_path, namespace="pkg.unrelated", name="inserted")
    _write_opaque_node(unrelated_dir / "node.ndf", svc_type="customAdapter")
    updated = analyze_path(tmp_path, DEFAULT_CONFIG)
    updated_dependency = next(
        dependency
        for dependency in updated.unique_dependencies
        if dependency.target_service == "pkg.adapter:target"
    )

    assert updated_dependency.id == original_dependency.id
    assert updated_dependency.occurrence_ids == original_dependency.occurrence_ids


def test_svc_type_normalization_and_false_positive_matrix(tmp_path) -> None:
    flow_dir = _service_dir(tmp_path, namespace="pkg.flow", name="flowService")
    _write_raw_node(
        flow_dir / "node.ndf",
        """<Values version="2.0">
  <value name="svc_type"> flow </value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
    )
    (flow_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    _write_java_service(
        tmp_path,
        class_name="JavaType",
        service_name="javaService",
        body="IDataCursor pc = pipeline.getCursor(); pc.destroy();",
        svc_type=" java ",
    )
    opaque_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="opaqueService")
    _write_opaque_node(opaque_dir / "node.ndf", svc_type=" customAdapter ")

    for namespace, name, body in (
        ("pkg.false", "empty", ""),
        ("pkg.false", "blank", "<value name=\"svc_type\"></value>"),
        ("pkg.false", "spaces", "<value name=\"svc_type\">   </value>"),
        ("pkg.false", "tabs", "<value name=\"svc_type\">\t\n  </value>"),
        ("pkg.false", "commentOnly", "<value name=\"node_comment\">note</value>"),
        ("pkg.false", "arbitrary", "<value name=\"unknownConfig\">secretish</value>"),
        ("pkg.false", "folderNode", "<value name=\"node_type\">folder</value>"),
        ("pkg.false", "recordSvcType", "<record name=\"svc_type\" />"),
        ("pkg.spec", "iface", "<value name=\"svc_type\"> spec </value>"),
    ):
        artifact_dir = _service_dir(tmp_path, namespace=namespace, name=name)
        _write_raw_node(artifact_dir / "node.ndf", f"<Values version=\"2.0\">{body}</Values>")
    malformed_dir = _service_dir(tmp_path, namespace="pkg.false", name="malformed")
    (malformed_dir / "node.ndf").write_text(
        """<Values version="2.0"><value name="svc_type">customAdapter""",
        encoding="utf-8",
    )
    document_dir = _document_dir(tmp_path, "pkg.docs", "Customer")
    _write_document_node(
        document_dir / "node.ndf",
        "pkg.docs:Customer",
        """
      <record javaclass="com.wm.util.Values">
        <value name="field_name">id</value>
        <value name="field_type">string</value>
        <value name="field_dim">0</value>
      </record>""",
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }

    assert set(services) == {
        "pkg.adapter:opaqueService",
        "pkg.flow:flowService",
        "pkg.services.JavaType:javaService",
    }
    assert services["pkg.flow:flowService"].service_type == "FLOW"
    assert services["pkg.flow:flowService"].source_service_type == "flow"
    assert services["pkg.services.JavaType:javaService"].service_type == "JAVA"
    assert services["pkg.services.JavaType:javaService"].source_service_type == "java"
    assert services["pkg.adapter:opaqueService"].service_type == "OPAQUE"
    assert services["pkg.adapter:opaqueService"].source_service_type == "customAdapter"
    assert analysis.metrics.service_type_counts == {"FLOW": 1, "JAVA": 1, "OPAQUE": 1}
    assert analysis.metrics.opaque_service_count == 1
    assert any(
        finding.code == "XML_MALFORMED"
        for package in analysis.packages
        for finding in package.findings
    )

    dot = render_dependency_dot(analysis)
    markdown_paths = write_service_markdown(tmp_path / "markdown", list(services.values()))
    combined_markdown_names = "\n".join(path.name for path in markdown_paths)
    for false_positive in (
        "empty",
        "blank",
        "spaces",
        "tabs",
        "commentOnly",
        "arbitrary",
        "folderNode",
        "recordSvcType",
        "malformed",
    ):
        assert false_positive not in dot
        assert false_positive not in combined_markdown_names


def test_service_signature_source_points_to_actual_metadata_shape(tmp_path) -> None:
    record_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="recordSig")
    _write_opaque_node(record_dir / "node.ndf", svc_type="customAdapter")
    scalar_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="scalarSig")
    _write_raw_node(
        scalar_dir / "node.ndf",
        """<Values version="2.0">
  <value name="svc_type">customAdapter</value>
  <value name="svc_sig">not-a-record</value>
</Values>""",
    )
    array_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="arraySig")
    _write_raw_node(
        array_dir / "node.ndf",
        """<Values version="2.0">
  <value name="svc_type">customAdapter</value>
  <array name="svc_sig" type="record" depth="1"><record /></array>
</Values>""",
    )
    missing_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="missingSig")
    _write_raw_node(
        missing_dir / "node.ndf",
        """<Values version="2.0">
  <value name="svc_type">customAdapter</value>
</Values>""",
    )
    malformed_child_dir = _service_dir(
        tmp_path, namespace="pkg.adapter", name="malformedChildSig"
    )
    _write_raw_node(
        malformed_child_dir / "node.ndf",
        """<Values version="2.0">
  <value name="svc_type">customAdapter</value>
  <record name="svc_sig">
    <record name="sig_in"><value name="rec_fields">not-array</value></record>
  </record>
</Values>""",
    )

    services = {
        service.identity.name: service
        for package in analyze_path(tmp_path, DEFAULT_CONFIG).packages
        for service in package.services
    }

    assert services["recordSig"].signature.source.source_node == (
        "/Values/record[@name='svc_sig']"
    )
    assert services["scalarSig"].signature.source.source_node == (
        "/Values/value[@name='svc_sig']"
    )
    assert services["arraySig"].signature.source.source_node == (
        "/Values/array[@name='svc_sig']"
    )
    assert services["missingSig"].signature.source.source_node is None
    for name in ("scalarSig", "arraySig"):
        assert any(
            finding.code == "SERVICE_SIGNATURE_METADATA_PARTIAL"
            for finding in services[name].findings
        )
    malformed_finding = next(
        finding
        for finding in services["malformedChildSig"].findings
        if finding.code == "SERVICE_SIGNATURE_METADATA_PARTIAL"
    )
    assert services["malformedChildSig"].signature.source.source_node == (
        "/Values/record[@name='svc_sig']"
    )
    assert malformed_finding.source.xml_path is not None
    assert "value" in malformed_finding.source.xml_path


def test_flow_and_java_calls_to_opaque_resolve_cli_metrics_and_called_by(
    tmp_path,
) -> None:
    secret_marker = "password=opaque-do-not-render"
    target_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="target")
    _write_opaque_node(
        target_dir / "node.ndf",
        svc_type="customAdapter",
        comment="Opaque target summary",
        extra_values=f"<value name=\"connectionConfig\">{secret_marker}</value>",
    )
    orphan_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="orphan")
    _write_opaque_node(orphan_dir / "node.ndf", svc_type="customAdapter")
    flow_dir = _service_dir(tmp_path, namespace="pkg.flow", name="caller")
    _write_node(flow_dir / "node.ndf")
    (flow_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="pkg.adapter:target" />
<INVOKE SERVICE="pkg.adapter:target" />
</FLOW>""",
        encoding="utf-8",
    )
    _write_java_service(
        tmp_path,
        class_name="JavaCaller",
        service_name="javaCaller",
        body='Service.doInvoke("pkg.adapter", "target", pipeline);',
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }
    flow_caller = services["pkg.flow:caller"]
    java_caller = services["pkg.services.JavaCaller:javaCaller"]

    assert flow_caller.unique_dependencies[0].target_analysis_status == "OPAQUE"
    assert flow_caller.unique_dependencies[0].occurrence_count == 2
    java_call = java_caller.call_occurrences[0]
    assert java_call.target == "pkg.adapter:target"
    assert java_call.target_type == "OPAQUE"
    assert java_call.target_analysis_status == "OPAQUE"
    assert analysis.metrics.service_type_counts == {"FLOW": 1, "JAVA": 1, "OPAQUE": 2}
    assert analysis.metrics.service_analysis_status_counts == {"FULL": 2, "OPAQUE": 2}
    assert analysis.metrics.opaque_service_with_description_count == 1
    assert analysis.metrics.opaque_service_without_description_count == 1
    assert analysis.metrics.resolved_call_occurrence_target_type_counts["OPAQUE"] == 3
    assert analysis.metrics.resolved_unique_dependency_target_type_counts["OPAQUE"] == 2

    output_dir = tmp_path / "cli-out"
    result = CliRunner().invoke(app, ["analyze", str(tmp_path), "--output", str(output_dir)])
    assert result.exit_code == 0
    for expected_line in (
        "- FLOW: 1",
        "- Java: 1",
        "- Opaque: 2",
        "- full: 2",
        "- opaque: 2",
        "- with source descriptions: 1",
        "- without source descriptions: 1",
    ):
        assert expected_line in result.output
    assert secret_marker not in result.output
    assert secret_marker not in render_analysis_json(analysis)
    assert secret_marker not in render_dependency_dot(analysis)

    markdown_paths = write_service_markdown(tmp_path / "service-md", list(services.values()))
    rendered_markdown = {path.name: path.read_text(encoding="utf-8") for path in markdown_paths}
    target_markdown = rendered_markdown["pkg.adapter_target.md"]
    orphan_markdown = rendered_markdown["pkg.adapter_orphan.md"]
    assert "## Called By" in target_markdown
    assert "pkg.flow:caller" in target_markdown
    assert "pkg.services.JavaCaller:javaCaller" in target_markdown
    assert "| 2 | True | `OPAQUE` | `pkg.flow:caller` |" in target_markdown
    assert "| 1 | True | `OPAQUE` | `pkg.services.JavaCaller:javaCaller` |" in target_markdown
    assert "No incoming static service calls target this service." in orphan_markdown
    assert secret_marker not in target_markdown


def test_process_catalog_validation_disclosure_and_cli_output(tmp_path) -> None:
    flow_dir = _service_dir(tmp_path, namespace="pkg.proc", name="start")
    _write_node(flow_dir / "node.ndf")
    (flow_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    processes_file = tmp_path / "processes.yml"
    secret = "password=hunter2"
    processes_file.write_text(
        f"""version: 1
unknownTop: ignored
processes:
  - id: bad/unsafe
    name: Invalid process
    entrypoints:
      - pkg.proc:start
  - id: good-process
    name: Good process
    description: {secret}
    unknownProcessKey: ignored
    entrypoints:
      - pkg.proc:start
      - pkg.proc:start
      - missing.namespace:missingService
  - id: good-process
    name: Duplicate process
    entrypoints:
      - pkg.proc:start
""",
        encoding="utf-8",
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG, processes_file)
    payload = render_analysis_json(analysis)
    process = analysis.processes[0]

    assert process.process_id == "good-process"
    assert process.description_status == "DESCRIPTION_BLOCKED_SECRET"
    assert secret not in payload
    assert analysis.metrics.process_definition_count == 1
    assert analysis.metrics.declared_entrypoint_count == 3
    assert analysis.metrics.resolved_entrypoint_count == 1
    assert analysis.metrics.unresolved_entrypoint_count == 2
    codes = {finding.code for finding in analysis.findings}
    assert {
        "PROCESS_CONFIG_UNKNOWN_KEY",
        "PROCESS_ID_INVALID",
        "PROCESS_ID_DUPLICATE",
        "PROCESS_ENTRYPOINT_DUPLICATE",
        "PROCESS_ENTRYPOINT_NOT_FOUND",
    }.issubset(codes)
    assert all(":\\" not in finding.source.path for finding in analysis.findings)

    rendered = (
        render_process_markdown(analysis, process)
        + render_documentation_index(analysis)
        + render_entrypoint_candidates_markdown(analysis)
    )
    assert secret not in rendered
    assert "Technical root candidate; not confirmed" in rendered
    process_markdown = render_process_markdown(analysis, process)
    assert "## Declared Entrypoints" in process_markdown
    assert "## Entrypoint Validation" in process_markdown
    assert (
        f"[`pkg.proc:start`](../services/{service_markdown_filename('pkg.proc:start')})"
        in process_markdown
    )
    assert "`missing.namespace:missingService` |  |" in process_markdown
    assert "(../services/missing.namespace_missingService.md)" not in process_markdown
    assert "`DUPLICATE`" in process_markdown
    assert "`NOT_FOUND`" in process_markdown

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(tmp_path),
            "--output",
            str(tmp_path / "out"),
            "--processes-file",
            str(processes_file),
        ],
    )
    assert result.exit_code == 0
    assert str(tmp_path) not in result.output
    assert "process definitions" not in result.output.lower()
    assert "- definitions: 1" in result.output
    assert "- Processes with findings: 1" in result.output
    assert "- process findings:" not in result.output


def test_process_entrypoint_validation_renders_all_statuses(tmp_path) -> None:
    root = tmp_path / "catalog"
    start_dir = _service_dir(root, namespace="pkg.proc", name="start")
    _write_node(start_dir / "node.ndf")
    (start_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    ambiguous_a = _service_dir(
        root, package="PkgA", namespace="pkg.proc", name="ambiguous"
    )
    _write_node(ambiguous_a / "node.ndf")
    (ambiguous_a / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    ambiguous_b = _service_dir(
        root, package="PkgB", namespace="pkg.proc", name="ambiguous"
    )
    _write_node(ambiguous_b / "node.ndf")
    (ambiguous_b / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: validation-process
    name: Validation process
    entrypoints:
      - pkg.proc:start
      - pkg.proc:start
      - pkg.proc:missing
      - pkg.proc:ambiguous
""",
        encoding="utf-8",
    )

    analysis = analyze_path(root, DEFAULT_CONFIG, processes_file)
    process = analysis.processes[0]
    statuses = {
        (entrypoint.declared_target, entrypoint.status.value)
        for entrypoint in analysis.process_entrypoints
    }
    markdown = render_process_markdown(analysis, process)
    declared = markdown.split("## Declared Entrypoints", 1)[1].split(
        "## Entrypoint Validation", 1
    )[0]
    validation = markdown.split("## Entrypoint Validation", 1)[1].split(
        "## Technical Summary", 1
    )[0]

    assert statuses == {
        ("pkg.proc:start", "RESOLVED"),
        ("pkg.proc:start", "DUPLICATE"),
        ("pkg.proc:missing", "NOT_FOUND"),
        ("pkg.proc:ambiguous", "AMBIGUOUS"),
    }
    assert declared.count("pkg.proc:start") == 2
    assert (
        f"[`pkg.proc:start`](../services/{service_markdown_filename('pkg.proc:start')})"
        in validation
    )
    assert "`DUPLICATE`" in validation
    assert "`NOT_FOUND`" in validation
    assert "`AMBIGUOUS`" in validation
    assert "(../services/pkg.proc_missing.md)" not in validation
    assert "(../services/pkg.proc_ambiguous.md)" not in validation
    assert validation.index("pkg.proc:ambiguous") < validation.index("pkg.proc:missing")
    assert validation.index("pkg.proc:missing") < validation.index("pkg.proc:start")


def test_process_document_links_distinguish_resolved_and_unresolved(tmp_path) -> None:
    root = tmp_path / "catalog"
    doc_dir = _document_dir(root, namespace="docs", name="Known")
    _write_document_node(doc_dir / "node.ndf", "docs:Known", "")
    service_dir = _service_dir(root, namespace="pkg.proc", name="start")
    _write_node_with_signature(
        service_dir / "node.ndf",
        input_fields="""
      <record>
        <value name="field_name">known</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
        <value name="rec_ref">docs:Known</value>
      </record>
      <record>
        <value name="field_name">missingOne</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
        <value name="rec_ref">docs:Missing</value>
      </record>
      <record>
        <value name="field_name">missingTwo</value>
        <value name="field_type">recref</value>
        <value name="field_dim">0</value>
        <value name="rec_ref">docs:Missing</value>
      </record>""",
    )
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: doc-process
    name: Document process
    entrypoints:
      - pkg.proc:start
""",
        encoding="utf-8",
    )

    analysis = analyze_path(root, DEFAULT_CONFIG, processes_file)
    process = analysis.processes[0]
    rendered = render_process_markdown(analysis, process)

    assert len(analysis.process_document_relationships) == 2
    assert (
        f"[`docs:Known`](../documents/{document_markdown_filename('docs:Known')})"
        in rendered
    )
    assert "`docs:Missing` | `UNRESOLVED` | `ENTRYPOINT_INPUT` | `pkg.proc:start` | 2 |" in (
        rendered
    )
    assert f"../documents/{document_markdown_filename('docs:Missing')}" not in rendered

    output = tmp_path / "out"
    _run_cli_analyze(root, output, processes_file=processes_file)
    process_markdown = (output / "processes" / "doc-process.md").read_text(encoding="utf-8")
    assert (output / "documents" / document_markdown_filename("docs:Known")).exists()
    assert len(list((output / "documents").glob("*.md"))) == 1
    assert (
        f"[`docs:Known`](../documents/{document_markdown_filename('docs:Known')})"
        in process_markdown
    )
    assert "`docs:Missing` | `UNRESOLVED`" in process_markdown
    assert f"../documents/{document_markdown_filename('docs:Missing')}" not in process_markdown
    _assert_generated_markdown_links_valid(output)


def test_cli_processes_with_findings_label_matches_json_for_global_config_cases(
    tmp_path,
) -> None:
    root = tmp_path / "catalog"
    service_dir = _service_dir(root, namespace="pkg.proc", name="start")
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )
    valid_catalog = tmp_path / "valid-processes.yml"
    valid_catalog.write_text(
        """version: 1
processes:
  - id: valid-process
    name: Valid process
    entrypoints:
      - pkg.proc:start
""",
        encoding="utf-8",
    )
    malformed_catalog = tmp_path / "malformed-processes.yml"
    malformed_catalog.write_text("version: 1\nprocesses: [", encoding="utf-8")
    missing_catalog = tmp_path / "missing-processes.yml"

    cases = [
        ("valid", valid_catalog, 0, set()),
        ("malformed", malformed_catalog, 0, {"PROCESS_CONFIG_MALFORMED"}),
        ("missing", missing_catalog, 0, {"PROCESS_CONFIG_MISSING"}),
    ]
    for label, catalog, processes_with_findings, expected_codes in cases:
        output = tmp_path / f"out-{label}"
        cli_output = _run_cli_analyze(root, output, processes_file=catalog)
        payload = json.loads((output / "analysis.json").read_text(encoding="utf-8"))

        assert f"- Processes with findings: {processes_with_findings}" in cli_output
        assert "- process findings:" not in cli_output
        assert payload["metrics"]["processes_with_findings_count"] == processes_with_findings
        codes = {finding["code"] for finding in payload["findings"]}
        assert expected_codes.issubset(codes)


def test_generated_markdown_links_are_valid_without_process_catalog(tmp_path) -> None:
    output = tmp_path / "no-process-catalog"

    _run_cli_analyze(_samples(), output)

    assert _generated_file_count(output) == 47
    assert not (output / "processes").exists()
    _assert_generated_markdown_links_valid(output)


def test_generated_markdown_links_are_valid_for_fixture_catalog_modes(tmp_path) -> None:
    for mode in ExtractionMode:
        processes_file = tmp_path / f"processes-{mode.value}.yml"
        _write_fixture_process_catalog(processes_file)
        output = tmp_path / f"fixture-processes-{mode.value}"

        _run_cli_analyze(
            _samples(),
            output,
            processes_file=processes_file,
            free_text_mode=mode,
        )

        assert _generated_file_count(output) == 52
        assert len(list((output / "processes").glob("*.md"))) == 3
        assert len(list((output / "graphs" / "processes").glob("*.dot"))) == 2
        _assert_generated_markdown_links_valid(output)
        geographic_page = (
            output / "processes" / "geographic-address-validation.md"
        ).read_text(encoding="utf-8")
        assert (
            "`oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:"
            "docCreateGeographicAddressValidationInput` | `UNRESOLVED`"
        ) in geographic_page
        assert (
            "../documents/oa.adapter.doc.geographicAddressManagement."
            "geographicAddressValidation_docCreateGeographicAddressValidationInput.md"
            not in geographic_page
        )
        assert (
            "../documents/oa.adapter.doc.geographicAddressManagement."
            "geographicAddressValidation_docCreateGeographicAddressValidationOutput.md"
            not in geographic_page
        )


def test_process_traversal_handles_cycle_opaque_unresolved_and_docs(tmp_path) -> None:
    start_dir = _service_dir(tmp_path, namespace="pkg.proc", name="start")
    _write_node(start_dir / "node.ndf")
    (start_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="pkg.proc:middle" />
<INVOKE SERVICE="pkg.proc:middle" />
<INVOKE SERVICE="pkg.opaque:target" />
</FLOW>""",
        encoding="utf-8",
    )
    middle_dir = _service_dir(tmp_path, namespace="pkg.proc", name="middle")
    _write_node(middle_dir / "node.ndf")
    (middle_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="pkg.proc:end" />
</FLOW>""",
        encoding="utf-8",
    )
    end_dir = _service_dir(tmp_path, namespace="pkg.proc", name="end")
    _write_node(end_dir / "node.ndf")
    (end_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true">
<INVOKE SERVICE="pkg.proc:middle" />
<INVOKE SERVICE="external.pkg:missing" />
</FLOW>""",
        encoding="utf-8",
    )
    opaque_dir = _service_dir(tmp_path, namespace="pkg.opaque", name="target")
    _write_opaque_node(opaque_dir / "node.ndf", svc_type="customAdapter")
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: cycle-process
    name: Cycle process
    entrypoints:
      - pkg.proc:start
""",
        encoding="utf-8",
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG, processes_file)
    process = analysis.processes[0]
    memberships = {
        membership.service: membership
        for membership in analysis.process_service_memberships
    }
    edge_by_target = {
        (edge.source_service, edge.target_service): edge
        for edge in analysis.process_dependency_edges
    }

    assert set(memberships) == {
        "pkg.proc:start",
        "pkg.proc:middle",
        "pkg.proc:end",
        "pkg.opaque:target",
    }
    assert memberships["pkg.proc:start"].entrypoint is True
    assert memberships["pkg.proc:middle"].minimum_depth == 1
    assert memberships["pkg.proc:end"].minimum_depth == 2
    assert memberships["pkg.opaque:target"].service_type == "OPAQUE"
    assert edge_by_target[("pkg.proc:start", "pkg.proc:middle")].occurrence_count == 2
    assert ("pkg.proc:end", "pkg.proc:middle") in edge_by_target
    assert len(analysis.process_unresolved_calls) == 1
    assert analysis.process_unresolved_calls[0].target_service == "external.pkg:missing"

    dot = render_process_dot(analysis, process)
    assert 'kind="opaque_service"' in dot
    assert 'kind="unresolved_target"' in dot
    assert "external.pkg:missing" in dot

    out = tmp_path / "docs"
    process_paths = write_process_markdown(out, analysis)
    candidate_path = write_entrypoint_candidates_markdown(out, analysis)
    dot_paths = write_process_dots(out, analysis)
    assert (out / "processes" / "cycle-process.md").exists()
    assert candidate_path.exists()
    assert dot_paths[0].name == "cycle-process.dot"
    assert any(path.name == "index.md" for path in process_paths)


def test_process_catalog_rejects_unsafe_yaml(tmp_path) -> None:
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
shared: &shared
  id: shared-process
  name: Shared
  entrypoints: [pkg.proc:start]
processes:
  - *shared
""",
        encoding="utf-8",
    )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG, processes_file)

    assert analysis.processes == []
    malformed_findings = [
        finding
        for finding in analysis.findings
        if finding.code == "PROCESS_CONFIG_MALFORMED"
    ]
    assert malformed_findings
    assert all(finding.source.path == "processes.yml" for finding in malformed_findings)


def test_malformed_xml_findings_are_disclosure_safe_across_outputs(tmp_path) -> None:
    marker_root = tmp_path / "SecretUserName-private-workspace" / "sensitive-temp-root"
    flow_dir = _service_dir(marker_root, namespace="pkg.flow", name="badFlowXml")
    _write_node(flow_dir / "node.ndf")
    (flow_dir / "flow.xml").write_text("<FLOW>", encoding="utf-8")

    for namespace, name, xml in (
        (
            "pkg.flow",
            "badNode",
            """<Values version="2.0"><value name="svc_type">flow""",
        ),
        (
            "pkg.adapter",
            "badOpaque",
            """<Values version="2.0"><value name="svc_type">customAdapter""",
        ),
        (
            "pkg.docs",
            "BadDocument",
            """<Values version="2.0"><record name="record">""",
        ),
    ):
        artifact_dir = _service_dir(marker_root, namespace=namespace, name=name)
        (artifact_dir / "node.ndf").write_text(xml, encoding="utf-8")

    manifest = marker_root / "Pkg" / "manifest.v3"
    manifest.write_text("""<Values version="2.0"><value name="enabled">true""", encoding="utf-8")

    analysis = analyze_path(marker_root, DEFAULT_CONFIG)
    services = [service for package in analysis.packages for service in package.services]
    service_markdown = "".join(render_service_markdown(service) for service in services)
    result = CliRunner().invoke(
        app,
        ["analyze", str(marker_root), "--output", str(tmp_path / "safe-cli-out")],
    )

    assert result.exit_code == 0
    combined = (
        render_analysis_json(analysis)
        + service_markdown
        + render_dependency_dot(analysis)
        + render_document_dot(analysis)
        + result.output
    )
    for forbidden in (
        "SecretUserName",
        "private-workspace",
        "sensitive-temp-root",
        str(marker_root),
        "<Values",
        "<record",
    ):
        assert forbidden not in combined

    xml_findings = [
        finding
        for package in analysis.packages
        for finding in [
            *package.findings,
            *(
                service_finding
                for service in package.services
                for service_finding in service.findings
            ),
        ]
        if finding.code == "XML_MALFORMED"
    ]
    assert len(xml_findings) >= 4
    assert any(
        "line" in finding.message and "column" in finding.message
        for finding in xml_findings
    )
    for finding in xml_findings:
        assert finding.message.startswith("Malformed XML:")
        assert "SecretUserName" not in finding.message
        assert "private-workspace" not in finding.message
        assert "sensitive-temp-root" not in finding.message
        assert not Path(finding.source.path).is_absolute()
        assert "\\" not in finding.source.path
        assert finding.source.source_node is None


def test_service_description_source_uses_actual_node_comment_shape(tmp_path) -> None:
    scalar_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="scalarComment")
    _write_opaque_node(
        scalar_dir / "node.ndf",
        svc_type="customAdapter",
        comment="operator note",
    )
    empty_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="emptyComment")
    _write_opaque_node(empty_dir / "node.ndf", svc_type="customAdapter", comment="")
    missing_dir = _service_dir(tmp_path, namespace="pkg.adapter", name="missingComment")
    _write_raw_node(
        missing_dir / "node.ndf",
        """<Values version="2.0">
  <value name="svc_type">customAdapter</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
    )

    malformed_cases = {
        "recordComment": (
            """<record name="node_comment"><value name="note">record-secret</value></record>""",
            "/Values/record[@name='node_comment']",
            "record-secret",
        ),
        "arrayComment": (
            """<array name="node_comment" type="value" depth="1">"""
            """<value>array-secret</value></array>""",
            "/Values/array[@name='node_comment']",
            "array-secret",
        ),
        "recordArrayComment": (
            """<array name="node_comment" type="record" depth="1"><record /></array>""",
            "/Values/array[@name='node_comment']",
            "recordArray-secret",
        ),
        "duplicateComment": (
            """<value name="node_comment">first-secret</value>
  <value name="node_comment">second-secret</value>""",
            "/Values/value[@name='node_comment']",
            "first-secret",
        ),
    }
    for name, (comment_xml, _source_node, _secret) in malformed_cases.items():
        service_dir = _service_dir(tmp_path, namespace="pkg.adapter", name=name)
        _write_opaque_node(
            service_dir / "node.ndf",
            svc_type="customAdapter",
            comment_xml=comment_xml,
        )

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    services = {
        service.identity.name: service
        for package in analysis.packages
        for service in package.services
    }

    scalar = services["scalarComment"]
    assert scalar.description is not None
    assert scalar.description.value == "operator note"
    assert scalar.description.source is not None
    assert scalar.description.source.source_node == "/Values/value[@name='node_comment']"
    assert services["emptyComment"].description is None
    assert services["emptyComment"].description_status == "NO_DESCRIPTION"
    assert services["missingComment"].description is None
    assert services["missingComment"].description_status == "NO_DESCRIPTION"

    payload = render_analysis_json(analysis) + "".join(
        render_service_markdown(service) for service in services.values()
    )
    for name, (_comment_xml, source_node, secret) in malformed_cases.items():
        service = services[name]
        finding = next(
            finding
            for finding in service.findings
            if finding.code == "SERVICE_DESCRIPTION_MALFORMED"
        )
        assert service.description is None
        assert service.description_status == "DESCRIPTION_MALFORMED"
        assert finding.source.source_node == source_node
        assert secret not in payload

    redacted = analyze_path(
        tmp_path, _config(free_text_mode=ExtractionMode.REDACT)
    ).packages[0].services
    omitted = analyze_path(
        tmp_path, _config(free_text_mode=ExtractionMode.OMIT)
    ).packages[0].services
    redacted_scalar = next(
        service for service in redacted if service.identity.name == "scalarComment"
    )
    omitted_scalar = next(
        service for service in omitted if service.identity.name == "scalarComment"
    )
    assert redacted_scalar.description is not None
    assert redacted_scalar.description.marker == "<redacted:free-text>"
    assert omitted_scalar.description is not None
    assert omitted_scalar.description.disclosure == "OMITTED"


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

    assert analysis.schema_version == "analysis.v8"
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


def _assert_generated_markdown_links_valid(output_root: Path) -> None:
    """Validate generated inline Markdown links without parsing arbitrary Markdown.

    The extractor covers wm-doc generated inline links, skips fenced code blocks and image
    links, ignores external schemes and pure fragments, and checks local targets remain under
    the generated output root.
    """
    root = output_root.resolve()
    for markdown_path in sorted(root.rglob("*.md")):
        text = markdown_path.read_text(encoding="utf-8")
        for raw_target in _iter_generated_markdown_links(text):
            target = raw_target.strip()
            if not target:
                continue
            if WINDOWS_ABSOLUTE_RE.match(target) or Path(target).is_absolute():
                raise AssertionError(f"{markdown_path} contains absolute link {target!r}")
            if URL_SCHEME_RE.match(target):
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            if WINDOWS_ABSOLUTE_RE.match(path_part) or Path(path_part).is_absolute():
                raise AssertionError(f"{markdown_path} contains absolute link {target!r}")
            resolved = (markdown_path.parent / path_part).resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise AssertionError(
                    f"{markdown_path} contains link escaping output root: {target!r}"
                ) from exc
            assert resolved.exists(), f"{markdown_path} links to missing target {target!r}"


def _iter_generated_markdown_links(text: str) -> list[str]:
    links: list[str] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        links.extend(match.group(1) for match in MARKDOWN_LINK_RE.finditer(line))
    return links


def _run_cli_analyze(
    packages_path: Path,
    output: Path,
    *,
    processes_file: Path | None = None,
    free_text_mode: ExtractionMode = ExtractionMode.INCLUDE,
) -> str:
    args = ["analyze", str(packages_path), "--output", str(output)]
    config_path = output.parent / f"{output.name}-config.yml"
    _write_cli_config(config_path, free_text_mode)
    args.extend(["--config", str(config_path)])
    if processes_file is not None:
        args.extend(["--processes-file", str(processes_file)])
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return result.output


def _write_cli_config(path: Path, free_text_mode: ExtractionMode) -> None:
    path.write_text(
        f"""extraction:
  freeText:
    mode: {free_text_mode.value}
""",
        encoding="utf-8",
    )


def _write_fixture_process_catalog(path: Path) -> None:
    path.write_text(
        """version: 1
processes:
  - id: geographic-address-validation
    name: Geographic address validation
    description: Validates and prepares geographic address information.
    entrypoints:
      - oa.adapter.geographicAddressManagement:createGeographicAddressValidation
  - id: pgp-key-lookup
    name: PGP key lookup
    entrypoints:
      - pgp.services.registry:getPubKey
      - pgp.services.registry:getSecKey
""",
        encoding="utf-8",
    )


def _generated_file_count(output_root: Path) -> int:
    return sum(1 for path in output_root.rglob("*") if path.is_file())


def _samples() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"


def _service_dir(
    tmp_path: Path, namespace: str = "foo", name: str = "bar", package: str = "Pkg"
) -> Path:
    service_dir = tmp_path / package / "ns"
    for part in namespace.split("."):
        service_dir /= part
    service_dir /= name
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


def _write_node_with_signature(
    path: Path, *, input_fields: str = "", output_fields: str = "", comment: str = ""
) -> None:
    path.write_text(
        f"""<Values version="2.0">
  <value name="svc_type">flow</value>
  <value name="node_comment">{comment}</value>
  <record name="svc_sig">
    <record name="sig_in">
      <array name="rec_fields" type="record" depth="1">
{input_fields}
      </array>
    </record>
    <record name="sig_out">
      <array name="rec_fields" type="record" depth="1">
{output_fields}
      </array>
    </record>
  </record>
</Values>""",
        encoding="utf-8",
    )


def _write_raw_node(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _write_opaque_node(
    path: Path,
    *,
    svc_type: str,
    comment: str = "",
    comment_xml: str | None = None,
    signature_fields: str = "",
    extra_values: str = "",
) -> None:
    comment_fragment = (
        comment_xml
        if comment_xml is not None
        else f"<value name=\"node_comment\">{comment}</value>"
    )
    path.write_text(
        f"""<Values version="2.0">
  <value name="svc_type">{svc_type}</value>
  {comment_fragment}
  {extra_values}
  <record name="svc_sig">
    <record name="sig_in">
      <array name="rec_fields" type="record" depth="1">
{signature_fields}
      </array>
    </record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )


def _write_java_service(
    root: Path,
    *,
    class_name: str,
    service_name: str,
    body: str,
    svc_type: str = "java",
) -> None:
    service_dir = root / "Pkg" / "ns" / "pkg" / "services" / class_name / service_name
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "node.ndf").write_text(
        f"""<Values version="2.0">
  <value name="svc_type">{svc_type}</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )
    encoded_body = base64.b64encode(body.encode("utf-8")).decode("ascii")
    (service_dir / "java.frag").write_text(
        f"""<Values version="2.0">
  <value name="name">{service_name}</value>
  <value name="body">{encoded_body}</value>
</Values>""",
        encoding="utf-8",
    )
    source_path = (
        root
        / "Pkg"
        / "code"
        / "source"
        / "pkg"
        / "services"
        / f"{class_name}.java"
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        f"""package pkg.services;
public final class {class_name} {{
public static final void {service_name} (IData pipeline) throws ServiceException
{{
{body}
}}
}}
""",
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
