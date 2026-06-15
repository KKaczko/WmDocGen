from __future__ import annotations

from wm_doc.discovery import scan_path


def test_scan_reports_missing_flow_xml_for_flow_metadata(tmp_path) -> None:
    service_dir = tmp_path / "Pkg" / "ns" / "foo" / "missingFlow"
    service_dir.mkdir(parents=True)
    (service_dir / "node.ndf").write_text(
        """<Values version="2.0"><value name="svc_type">flow</value></Values>""",
        encoding="utf-8",
    )

    inventory = scan_path(tmp_path)
    package = inventory.packages[0]

    assert package.artifacts[0].probable_type == "flow_service_metadata_without_flow"
    assert any(finding.code == "FLOW_XML_MISSING" for finding in package.findings)


def test_scan_reports_flow_without_node_ndf(tmp_path) -> None:
    service_dir = tmp_path / "Pkg" / "ns" / "foo" / "loneFlow"
    service_dir.mkdir(parents=True)
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )

    inventory = scan_path(tmp_path)
    package = inventory.packages[0]

    assert package.artifacts[0].probable_type == "flow_xml_without_node"
    assert any(finding.code == "NODE_NDF_MISSING" for finding in package.findings)


def test_scan_reports_malformed_node_ndf(tmp_path) -> None:
    service_dir = tmp_path / "Pkg" / "ns" / "foo" / "broken"
    service_dir.mkdir(parents=True)
    (service_dir / "node.ndf").write_text("<Values>", encoding="utf-8")

    inventory = scan_path(tmp_path)
    package = inventory.packages[0]

    assert package.artifacts[0].status == "MALFORMED"
    assert any(finding.code == "XML_MALFORMED" for finding in package.findings)
