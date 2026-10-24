"""M12 phase 2: package selection, per-package index, artifact inventory and stats."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import ANALYZE_ALL_PACKAGES, PackageSelectionConfig, load_config
from wm_doc.discovery import scan_path
from wm_doc.render.artifact_markdown import render_artifact_inventory
from wm_doc.stats import render_stats

FLOW_NODE = """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>"""


def _flow_service(root: Path, package: str, namespace: str, name: str, body: str = "") -> None:
    service_dir = root / package / "ns" / Path(*namespace.split(".")) / name
    service_dir.mkdir(parents=True)
    (service_dir / "node.ndf").write_text(FLOW_NODE, encoding="utf-8")
    (service_dir / "flow.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<FLOW VERSION="3.0">{body}</FLOW>',
        encoding="utf-8",
    )


def _manifest(root: Path, package: str, system: bool) -> None:
    (root / package).mkdir(parents=True, exist_ok=True)
    (root / package / "manifest.v3").write_text(
        '<Values version="2.0">\n'
        f'  <value name="system_package">{"yes" if system else "no"}</value>\n'
        "</Values>",
        encoding="utf-8",
    )


def _trigger_node(root: Path, package: str, namespace: str, name: str) -> None:
    node_dir = root / package / "ns" / Path(*namespace.split(".")) / name
    node_dir.mkdir(parents=True)
    (node_dir / "node.ndf").write_text(
        '<Values version="2.0">\n'
        '  <value name="node_type">webMethods/trigger</value>\n'
        "</Values>",
        encoding="utf-8",
    )


def _server(root: Path) -> Path:
    """A packages/ directory with product, Default, system and custom packages."""
    _flow_service(root, "WmPublicLike", "pub.like", "svc")
    _flow_service(root, "Default", "default.ns", "svc")
    _manifest(root, "SysPkg", system=True)
    _flow_service(root, "SysPkg", "sys.ns", "svc")
    _manifest(root, "Orders", system=False)
    _flow_service(root, "Orders", "orders.api", "createOrder", '<INVOKE SERVICE="pub.foo:bar"/>')
    _flow_service(root, "Billing", "billing.api", "createInvoice")
    _trigger_node(root, "Orders", "orders.triggers", "onOrderCreated")
    return root


def test_default_selection_skips_product_default_and_system_packages(tmp_path: Path) -> None:
    inventory = scan_path(_server(tmp_path))

    assert [package.name for package in inventory.packages] == ["Billing", "Orders"]
    reasons = {package.name: package.reason for package in inventory.excluded_packages}
    assert reasons == {
        "Default": "matches exclude pattern `Default`",
        "SysPkg": "system package (manifest.v3 system_package=yes)",
        "WmPublicLike": "matches exclude pattern `Wm*`",
    }


def test_include_and_all_packages_selection(tmp_path: Path) -> None:
    root = _server(tmp_path)

    only_orders = scan_path(root, PackageSelectionConfig(include=["Ord*"]))
    everything = scan_path(root, ANALYZE_ALL_PACKAGES)

    assert [package.name for package in only_orders.packages] == ["Orders"]
    assert len(everything.packages) == 5
    assert everything.excluded_packages == []


def test_package_service_index_lists_only_its_own_services(tmp_path: Path) -> None:
    analysis = analyze_path(_server(tmp_path), load_config(None))

    for package in analysis.packages:
        assert {item.identity.package for item in package.service_index} == {package.name}


def test_non_service_artifacts_are_listed_by_node_type(tmp_path: Path) -> None:
    analysis = analyze_path(_server(tmp_path), load_config(None))

    triggers = [a for a in analysis.namespace_artifacts if a.node_type == "webMethods/trigger"]
    assert [(a.full_name, a.package) for a in triggers] == [
        ("orders.triggers:onOrderCreated", "Orders")
    ]
    page = render_artifact_inventory(analysis)
    assert "| `webMethods/trigger` | 1 |" in page
    assert "| `orders.triggers:onOrderCreated` | `Orders` |" in page
    assert "| `WmPublicLike` | matches exclude pattern `Wm*` |" in page


def test_analyze_cli_writes_artifact_page_and_respects_package_flags(tmp_path: Path) -> None:
    root = _server(tmp_path / "packages")
    output = tmp_path / "docs"

    result = CliRunner().invoke(
        app, ["analyze", str(root), "--output", str(output), "--exclude-package", "Billing"]
    )

    assert result.exit_code == 0, result.output
    assert "Packages: 1 analysed, 4 skipped" in result.output
    index = (output / "index.md").read_text(encoding="utf-8")
    assert "[Other artifacts and skipped packages](artifacts.md)" in index
    assert "| Packages skipped | 4 |" in index
    assert (output / "artifacts.md").exists()
    assert not (output / "services" / "billing.api_createInvoice.md").exists()


def test_stats_reports_types_unsupported_elements_and_external_calls(tmp_path: Path) -> None:
    root = _server(tmp_path)
    _flow_service(
        root, "Orders", "orders.api", "retryLater",
        '<FUTURESTEP/><INVOKE SERVICE="crm.core.customers:find"/>',
    )

    report = render_stats(analyze_path(root, load_config(None)))

    assert "- Analysed: 2" in report
    assert "  - 1 x system package (manifest.v3 system_package=yes)" in report
    assert "| `webMethods/trigger` | 1 |" in report
    assert "| `FUTURESTEP` | 1 |" in report
    assert "| `pub.foo:bar` | 1 |" in report
    assert "| `crm.core` | 1 | 1 |" in report
    assert "orders.api:retryLater" in report


def test_stats_cli_writes_report(tmp_path: Path) -> None:
    root = _server(tmp_path / "packages")
    report_path = tmp_path / "stats.md"

    result = CliRunner().invoke(app, ["stats", str(root), "--output", str(report_path)])

    assert result.exit_code == 0, result.output
    assert report_path.read_text(encoding="utf-8").startswith("# wm-doc server statistics")
