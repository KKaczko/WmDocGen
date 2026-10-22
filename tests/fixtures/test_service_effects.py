"""M12 phase 3: usage and data-effect facts, artifact references, external systems, shapes."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.effects import ServiceFacts, compute_service_facts
from wm_doc.external_systems import ExternalSystem, ExternalSystemCatalog
from wm_doc.ir import AnalysisResult, ReferenceTargetKind
from wm_doc.render.service_markdown import render_entry_points_table, render_effects_table
from wm_doc.shapes import render_shapes

FLOW_NODE = """<Values version="2.0">
  <value name="svc_type">{svc_type}</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>"""


def _node_dir(root: Path, namespace: str, name: str) -> Path:
    path = root / "Orders" / "ns" / Path(*namespace.split(".")) / name
    path.mkdir(parents=True)
    return path


def _flow(root: Path, namespace: str, name: str, body: str) -> None:
    node_dir = _node_dir(root, namespace, name)
    (node_dir / "node.ndf").write_text(FLOW_NODE.format(svc_type="flow"), encoding="utf-8")
    (node_dir / "flow.xml").write_text(
        f'<FLOW VERSION="3.0" CLEANUP="true">{body}</FLOW>', encoding="utf-8"
    )


def _set(field: str, value: str) -> str:
    return (
        f'<MAPSET FIELD="/{field};1;0"><DATA ENCODING="XMLValues" I18N="true">'
        f'<Values version="2.0"><value name="xml">{value}</value>'
        f'<record name="type"><value name="field_name">{field}</value>'
        "<value name=\"field_type\">string</value></record></Values></DATA></MAPSET>"
    )


def _copy(source: str, target: str) -> str:
    return f'<MAPCOPY FROM="/{source};1;0" TO="/{target};1;0"></MAPCOPY>'


def _invoke(target: str, *input_ops: str) -> str:
    return (
        f'<INVOKE SERVICE="{target}" VALIDATE-IN="$none" VALIDATE-OUT="$none">'
        f'<MAP MODE="INPUT">{"".join(input_ops)}</MAP></INVOKE>'
    )


def _raw_node(root: Path, namespace: str, name: str, content: str) -> None:
    node_dir = _node_dir(root, namespace, name)
    (node_dir / "node.ndf").write_text(content, encoding="utf-8")


def _orders_server(root: Path) -> Path:
    _flow(
        root,
        "orders.api",
        "notifyCrm",
        _invoke("pub.client:http", _set("url", "https://crm.example/api"), _set("method", "post"))
        + _invoke("pub.jms:send", _copy("config/queueName", "destinationName")),
    )
    _flow(
        root,
        "orders.api",
        "createOrder",
        _invoke("orders.api:notifyCrm")
        + _invoke("orders.db:insertOrder")
        + _invoke("billing.core:createInvoice")
        + _invoke("orders.utils:formatDate"),
    )
    # An adapter-like opaque service whose node.ndf names its connection.
    _raw_node(
        root,
        "orders.db",
        "insertOrder",
        '<Values version="2.0">\n'
        '  <value name="svc_type">AdapterService</value>\n'
        '  <record name="adapterData">\n'
        '    <value name="connectionName">orders.connections:ordersDb</value>\n'
        '    <value name="password">s3cret-value</value>\n'
        "  </record>\n"
        "</Values>",
    )
    _raw_node(
        root,
        "orders.connections",
        "ordersDb",
        '<Values version="2.0">\n  <value name="node_type">ConnNode</value>\n</Values>',
    )
    # A trigger naming the service it starts.
    _raw_node(
        root,
        "orders.triggers",
        "onOrderRequested",
        '<Values version="2.0">\n'
        '  <value name="node_type">webMethods/trigger</value>\n'
        '  <array name="conditions" type="record" depth="1">\n'
        '    <record><value name="serviceName">orders.api:createOrder</value></record>\n'
        "  </array>\n"
        "</Values>",
    )
    return root


def _facts(root: Path, catalog: ExternalSystemCatalog | None = None) -> dict[str, ServiceFacts]:
    analysis = analyze_path(root, load_config(None))
    return compute_service_facts(analysis, catalog or ExternalSystemCatalog())


def _analysis(root: Path) -> AnalysisResult:
    return analyze_path(root, load_config(None))


def test_platform_effects_read_location_from_literals_and_mappings(tmp_path: Path) -> None:
    facts = _facts(_orders_server(tmp_path))["orders.api:notifyCrm"]
    rows = {(e.action, e.object, e.where, e.known_from) for e in facts.effects}

    assert (
        "calls an external HTTP endpoint",
        "HTTP request",
        "HTTP: url `https://crm.example/api`, method `post`",
        "literal",
    ) in rows
    assert (
        "sends a JMS message",
        "message",
        "JMS: destinationName from `/config/queueName`",
        "mapped from pipeline",
    ) in rows


def test_effects_propagate_with_via_chain_and_skip_utilities(tmp_path: Path) -> None:
    facts = _facts(_orders_server(tmp_path))["orders.api:createOrder"]
    by_action = {e.action: e for e in facts.effects}

    assert by_action["calls an external HTTP endpoint"].via == ("orders.api:notifyCrm",)
    adapter = by_action["calls a `AdapterService` service"]
    assert adapter.object == "service `orders.db:insertOrder`"
    assert adapter.where == "`orders.connections:ordersDb`"
    assert adapter.known_from == "reference in its node.ndf"
    assert not any("orders.utils" in e.object for e in facts.effects)
    external = next(e for e in facts.effects if "billing.core" in e.object)
    assert external.where == "outside the analysed packages"


def test_declared_external_system_names_the_target(tmp_path: Path) -> None:
    catalog = ExternalSystemCatalog(
        systems=[
            ExternalSystem(
                id="billing", name="Billing core", vendor="SAP", namespaces=["billing.*"]
            )
        ]
    )

    facts = _facts(_orders_server(tmp_path), catalog)["orders.api:createOrder"]

    external = next(e for e in facts.effects if "billing.core" in e.object)
    assert external.where == "Billing core (SAP)"
    assert external.known_from == "external-systems.yml"


def test_artifact_references_are_exact_name_matches_without_values(tmp_path: Path) -> None:
    analysis = _analysis(_orders_server(tmp_path))
    refs = {
        (r.source_name, r.target_name, r.target_kind, r.key_path)
        for r in analysis.artifact_references
    }

    assert (
        "orders.triggers:onOrderRequested",
        "orders.api:createOrder",
        ReferenceTargetKind.SERVICE,
        "conditions[]/serviceName",
    ) in refs
    assert (
        "orders.db:insertOrder",
        "orders.connections:ordersDb",
        ReferenceTargetKind.ARTIFACT,
        "adapterData/connectionName",
    ) in refs
    assert "s3cret-value" not in analysis.model_dump_json()


def test_entry_points_follow_callers_to_the_trigger(tmp_path: Path) -> None:
    facts = _facts(_orders_server(tmp_path))["orders.api:notifyCrm"]

    assert facts.callers == ("orders.api:createOrder",)
    entry = facts.entry_points[0]
    assert (entry.kind, entry.name) == ("webMethods/trigger", "`orders.triggers:onOrderRequested`")
    assert entry.path == ("orders.api:createOrder", "orders.api:notifyCrm")
    table = render_entry_points_table(facts)
    assert "| `orders.triggers:onOrderRequested` | webMethods/trigger |" in table


def test_effects_table_and_facts_text(tmp_path: Path) -> None:
    facts = _facts(_orders_server(tmp_path))["orders.api:createOrder"]

    table = render_effects_table(facts)
    text = facts.text()

    assert "| HTTP request | calls an external HTTP endpoint |" in table
    assert "| `orders.api:notifyCrm` | literal |" in table
    assert text.startswith("used by:\n")
    assert "entry point: webMethods/trigger `orders.triggers:onOrderRequested`" in text
    assert "via orders.api:notifyCrm" in text


def test_analyze_page_shows_facts_sections(tmp_path: Path) -> None:
    root = _orders_server(tmp_path / "packages")
    output = tmp_path / "docs"

    result = CliRunner().invoke(app, ["analyze", str(root), "--output", str(output)])

    assert result.exit_code == 0, result.output
    page = (output / "services" / "orders.api_createOrder.md").read_text(encoding="utf-8")
    assert "## Data and Systems Touched" in page
    assert "## Entry Points" in page
    assert page.index("## Data and Systems Touched") < page.index("## Called By")
    assert page.index("## Processes") < page.index("## Entry Points")


def test_probe_shapes_prints_key_paths_and_no_values(tmp_path: Path) -> None:
    root = _orders_server(tmp_path)

    report = render_shapes(_analysis(root), root)

    assert "## `webMethods/trigger` (1 artifact(s))" in report
    assert "| `conditions[]/serviceName` | 1 | service x1 |" in report
    assert "| `adapterData/password` | 1 |  |" in report
    assert "s3cret-value" not in report
    assert "orders.api:createOrder" not in report
