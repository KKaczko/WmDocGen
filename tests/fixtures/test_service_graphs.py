"""Per-service call graphs."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_analyze_edge_cases import FakeGraphvizRunner
from test_service_effects import _orders_server
from typer.testing import CliRunner

import wm_doc.cli as cli_module
from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.effects import compute_service_facts
from wm_doc.external_systems import ExternalSystem, ExternalSystemCatalog
from wm_doc.render.service_graph import ServiceGraphContext, render_service_graph_dot

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _graph(root: Path, name: str, catalog: ExternalSystemCatalog | None = None) -> str:
    analysis = analyze_path(root, load_config(None))
    catalog = catalog or ExternalSystemCatalog()
    facts = compute_service_facts(analysis, catalog)
    service = next(s for s in analysis.services if s.identity.full_name == name)
    return render_service_graph_dot(service, facts[name], ServiceGraphContext(analysis, catalog))


def test_graph_shows_callers_platform_effects_and_folds_helpers() -> None:
    dot = _graph(SAMPLES, "pgp.services.common:readConfig")

    assert 'label="pgp.services.registry:getPubKey", kind="caller"' in dot
    assert 'label="reads a file\\nfile system", shape=note' in dot
    assert 'label="3 helper call(s)", style=dotted' in dot
    # Literal locations stay in the page table, never in the image.
    assert "config.xml" not in dot


def test_graph_shows_trigger_adapter_connection_and_external_system(tmp_path: Path) -> None:
    root = _orders_server(tmp_path)
    catalog = ExternalSystemCatalog(
        systems=[ExternalSystem(id="billing", name="Billing core", namespaces=["billing.*"])]
    )

    entry = _graph(root, "orders.api:createOrder", catalog)
    notify = _graph(root, "orders.api:notifyCrm", catalog)

    assert 'orders.triggers:onOrderRequested\\n(webMethods/trigger)", shape=cds' in entry
    assert 'orders.db:insertOrder\\n(AdapterService)", shape=component' in entry
    assert 'label="orders.connections:ordersDb", shape=cylinder' in entry
    assert 'billing.core:createInvoice\\nBilling core", style=dashed' in entry
    assert "orders.utils:formatDate" not in entry
    assert 'label="1 helper call(s)"' in entry
    assert 'label="calls an external HTTP endpoint\\nHTTP", shape=note' in notify
    assert "crm.example" not in notify


def test_data_moving_calls_are_listed_before_other_callees(tmp_path: Path) -> None:
    dot = _graph(_orders_server(tmp_path), "orders.api:createOrder")

    assert dot.index("orders.db:insertOrder") < dot.index("orders.api:notifyCrm")
    assert dot.index("orders.api:notifyCrm") < dot.index("billing.core:createInvoice")


def test_analyze_renders_service_graphs_only_when_images_are_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli_module, "GRAPHVIZ_RUNNER", FakeGraphvizRunner())
    runner = CliRunner()
    plain = tmp_path / "plain"
    images = tmp_path / "images"

    without = runner.invoke(app, ["analyze", str(SAMPLES), "--output", str(plain)])
    with_svg = runner.invoke(
        app, ["analyze", str(SAMPLES), "--output", str(images), "--render-graphs", "svg"]
    )

    assert without.exit_code == 0 and with_svg.exit_code == 0, with_svg.output
    assert not (plain / "graphs" / "services").exists()
    plain_page = (plain / "services" / "pgp.services.common_readConfig.md").read_text("utf-8")
    assert "## Call Graph" not in plain_page
    page = (images / "services" / "pgp.services.common_readConfig.md").read_text("utf-8")
    assert (
        "![Call graph of pgp.services.common:readConfig]"
        "(../graphs/services/pgp.services.common_readConfig.svg)" in page
    )
    assert "[DOT source](../graphs/services/pgp.services.common_readConfig.dot)" in page
    index = (images / "graphs" / "index.md").read_text("utf-8")
    assert "Per-service call graphs: 35 DOT files in `services/`, 35 rendered." in index
    assert "Service call graph:" not in index
