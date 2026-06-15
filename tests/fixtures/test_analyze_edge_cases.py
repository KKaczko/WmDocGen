from __future__ import annotations

from pathlib import Path

from wm_doc.analysis import analyze_path
from wm_doc.config import DEFAULT_CONFIG
from wm_doc.discovery import scan_path


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

    assert service.dependencies[0].target_service == "external.pkg:missing"
    assert service.dependencies[0].resolved is False
    assert service.unresolved_dependencies[0].target_service == "external.pkg:missing"


def _service_dir(tmp_path: Path) -> Path:
    service_dir = tmp_path / "Pkg" / "ns" / "foo" / "bar"
    service_dir.mkdir(parents=True)
    return service_dir


def _write_node(path: Path) -> None:
    path.write_text(
        """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )
