"""Disabled steps, legacy REST handlers, trigger details, the JDBC adapter decoder and the
opaque-service prompt, on synthetic packages shaped like real 10.x exports."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.describer import (
    DescribeOptions,
    DescribeOutcome,
    DescribeResult,
    DetailLevel,
    describe_services,
)
from wm_doc.effects import ServiceFacts, compute_service_facts
from wm_doc.external_systems import ExternalSystemCatalog
from wm_doc.ir import AnalysisResult, FlowService
from wm_doc.ollama_provider import (
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.pseudocode import render_pseudocode
from wm_doc.service_docs import doc_path

FLOW_NODE = """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>"""


def _node_dir(root: Path, namespace: str, name: str, package: str = "Orders") -> Path:
    path = root / package / "ns" / Path(*namespace.split(".")) / name
    path.mkdir(parents=True)
    return path


def _flow(root: Path, namespace: str, name: str, body: str) -> None:
    node_dir = _node_dir(root, namespace, name)
    (node_dir / "node.ndf").write_text(FLOW_NODE, encoding="utf-8")
    (node_dir / "flow.xml").write_text(
        f'<FLOW VERSION="3.0" CLEANUP="true">{body}</FLOW>', encoding="utf-8"
    )


def _raw_node(root: Path, namespace: str, name: str, content: str) -> None:
    node_dir = _node_dir(root, namespace, name)
    (node_dir / "node.ndf").write_text(content, encoding="utf-8")


def _analysis(root: Path) -> AnalysisResult:
    return analyze_path(root, load_config(None))


def _facts(analysis: AnalysisResult) -> dict[str, ServiceFacts]:
    return compute_service_facts(analysis, ExternalSystemCatalog())


def _service(analysis: AnalysisResult, name: str) -> FlowService:
    return next(s for p in analysis.packages for s in p.services if s.identity.full_name == name)


def test_disabled_steps_add_no_calls_mappings_or_effects(tmp_path: Path) -> None:
    _flow(
        tmp_path,
        "orders.api",
        "createOrder",
        '<INVOKE SERVICE="orders.api:validate" DISABLED="true"/>'
        '<INVOKE SERVICE="pub.publish:publish" DISABLED="true">'
        '<MAP MODE="INPUT"><MAPCOPY FROM="/a;1;0" TO="/documentTypeName;1;0"/></MAP>'
        "</INVOKE>"
        '<SEQUENCE DISABLED="true"><INVOKE SERVICE="pub.client:http"/></SEQUENCE>'
        '<BRANCH SWITCH="/mode">'
        '<SEQUENCE NAME="a" DISABLED="true"><INVOKE SERVICE="pub.file:getFile"/></SEQUENCE>'
        '<SEQUENCE NAME="b"><INVOKE SERVICE="orders.api:store"/></SEQUENCE>'
        "</BRANCH>"
        '<MAP MODE="STANDALONE">'
        '<MAPCOPY FROM="/x;1;0" TO="/y;1;0"/>'
        '<MAPCOPY FROM="/p;1;0" TO="/q;1;0" DISABLED="true"/>'
        "</MAP>",
    )
    _flow(tmp_path, "orders.api", "store", "")
    _flow(tmp_path, "orders.api", "validate", "")
    analysis = _analysis(tmp_path)
    service = _service(analysis, "orders.api:createOrder")

    assert [call.target for call in service.call_occurrences] == ["orders.api:store"]
    assert [op.technical_attrs["FROM"] for op in service.mapping_operations] == ["/x;1;0"]
    assert service.disabled_steps == 5
    facts = _facts(analysis)
    assert facts["orders.api:createOrder"].effects == ()
    assert facts["orders.api:validate"].callers == ()
    pseudo = render_pseudocode(service, lambda _target: None)
    assert "disabled steps left out: 5" in pseudo
    assert "pub.client:http" not in pseudo


def test_legacy_rest_handlers_are_entry_points(tmp_path: Path) -> None:
    _flow(tmp_path, "orders.api.order", "_post", '<INVOKE SERVICE="orders.impl:create"/>')
    _flow(tmp_path, "orders.api.order", "_default", "")
    _flow(tmp_path, "orders.impl", "create", '<INVOKE SERVICE="pub.flow:setResponse"/>')
    facts = _facts(_analysis(tmp_path))

    handler = facts["orders.api.order:_post"].entry_points
    assert [(e.kind, e.name) for e in handler] == [
        ("REST v1 handler", "`HTTP POST /rest/orders/api/order`")
    ]
    impl = facts["orders.impl:create"].entry_points
    assert [(e.kind, e.name, e.path) for e in impl] == [
        (
            "REST v1 handler",
            "`HTTP POST /rest/orders/api/order`",
            ("orders.api.order:_post", "orders.impl:create"),
        )
    ]
    assert [e.name for e in facts["orders.api.order:_default"].entry_points] == [
        "`/rest/orders/api/order (any other HTTP method)`"
    ]


def test_catalog_covers_services_seen_in_public_packages() -> None:
    from wm_doc.builtins import builtin_effect

    for name in (
        "pub.flow:setResponse",
        "pub.hashtable:get",
        "pub.utils:generateUUID",
        "pub.xml:getNextXMLNode",
        "pub.document:documentToBytes",
        "wm.server.globalvariables:addGlobalVariable",
        "wm.b2b.edi:convertToString",
    ):
        assert builtin_effect(name) is not None, name


# --- JDBC adapter blobs ------------------------------------------------------------------

SECRETS = ("s3cret-Pa55", "dbadmin", "db.internal.example", "jdbc:mysql://db.internal")


def _token(text: str) -> bytes:
    return bytes([0x04, len(text)]) + text.encode("utf-16-be")


def _blob(pairs: list[tuple[str, str]], tables: list[str] | None = None) -> str:
    """Encode properties the way IRTNODE_PROPERTY stores them (see wm_doc.adapters)."""
    raw = bytes.fromhex("0b04000000010501")
    for key, value in pairs:
        raw += _token(key) + _token(value) + b"\x05\x01"
    if tables is not None:
        for key in ("tables.catalogName", "tables.schemaName", "tables.tableName"):
            raw += _token(key) + bytes([0x0A, len(tables), 0x00, 0x0E])
            for table in tables:
                raw += _token(table if key == "tables.tableName" else "<current schema>")
            raw += b"\x05\x01"
    return base64.b64encode(raw).decode("ascii")


def _irt_node(root: Path, namespace: str, name: str, node_type: str, blob: str) -> None:
    _raw_node(
        root,
        namespace,
        name,
        '<Values version="2.0">\n'
        f'  <value name="node_type">{node_type}</value>\n'
        '  <number name="IRTNODE_VERSION" type="Integer">1</number>\n'
        f'  <value name="IRTNODE_PROPERTY">{blob}</value>\n'
        "</Values>",
    )


def _adapter_service(root: Path, namespace: str, name: str, blob: str) -> None:
    _raw_node(
        root,
        namespace,
        name,
        '<Values version="2.0">\n'
        '  <value name="svc_type">AdapterService</value>\n'
        '  <record name="svc_sig">\n'
        '    <record name="sig_in"><array name="rec_fields" type="record" depth="1"/></record>\n'
        '    <record name="sig_out"><array name="rec_fields" type="record" depth="1"/></record>\n'
        "  </record>\n"
        f'  <value name="IRTNODE_PROPERTY">{blob}</value>\n'
        "</Values>",
    )


def _jdbc_server(root: Path) -> Path:
    _irt_node(
        root,
        "orders.db",
        "conn",
        "ConnectionData",
        _blob(
            [
                ("adapterTypeName", "JDBCAdapter"),
                ("transactionType", "LOCAL_TRANSACTION"),
                ("datasourceClass", "com.mysql.cj.jdbc.MysqlDataSource"),
                ("serverName", "db.internal.example"),
                ("user", "dbadmin"),
                ("password", "s3cret-Pa55"),
                ("databaseName", "orders"),
                ("portNumber", "3306"),
                ("otherProperties", "jdbc:mysql://db.internal/orders"),
            ]
        ),
    )
    _adapter_service(
        root,
        "orders.db",
        "selectOrders",
        _blob(
            [
                ("serviceTemplateName", "com.wm.adapter.wmjdbc.services.Select"),
                ("connectionName", "orders.db:conn"),
                ("adapterType", "JDBCAdapter"),
                ("sql", "SELECT * FROM ORDERS WHERE NOTE = 's3cret-Pa55'"),
            ],
            tables=["ORDERS", "ORDER_LINES"],
        ),
    )
    _flow(root, "orders.api", "listOrders", '<INVOKE SERVICE="orders.db:selectOrders"/>')
    return root


def test_jdbc_adapter_decoder_keeps_allow_listed_fields_only(tmp_path: Path) -> None:
    analysis = _analysis(_jdbc_server(tmp_path))
    service = _service(analysis, "orders.db:selectOrders")

    assert service.adapter is not None
    assert service.adapter.operation == "Select"
    assert service.adapter.connection == "orders.db:conn"
    assert service.adapter.tables == ["ORDERS", "ORDER_LINES"]
    connection = next(a for a in analysis.namespace_artifacts if a.full_name == "orders.db:conn")
    assert connection.adapter is not None
    assert connection.adapter.database_product == "MySQL"
    assert connection.adapter.database_name == "orders"
    assert connection.adapter.transaction_type == "LOCAL_TRANSACTION"
    payload = analysis.model_dump_json()
    for secret in SECRETS:
        assert secret not in payload


def test_adapter_tables_reach_callers_as_data_effects(tmp_path: Path) -> None:
    facts = _facts(_analysis(_jdbc_server(tmp_path)))

    own = facts["orders.db:selectOrders"].effects
    assert [(e.action, e.object, e.where, e.known_from) for e in own] == [
        (
            "selects rows from",
            "tables `ORDERS`, `ORDER_LINES`",
            "database: connection `orders.db:conn` (MySQL, database `orders`)",
            "adapter service configuration",
        )
    ]
    caller = facts["orders.api:listOrders"].effects
    assert [(e.action, e.via) for e in caller] == [
        ("selects rows from", ("orders.db:selectOrders",))
    ]


def test_adapter_pages_and_prompt_never_show_credentials(tmp_path: Path) -> None:
    root = _jdbc_server(tmp_path / "packages")
    out = tmp_path / "site"
    result = CliRunner().invoke(app, ["analyze", str(root), "--output", str(out)])
    assert result.exit_code == 0, result.output

    text = "\n".join(path.read_text(encoding="utf-8") for path in out.rglob("*.md"))
    text += (out / "analysis.json").read_text(encoding="utf-8")
    for secret in SECRETS:
        assert secret not in text
    assert "## JDBC connections" in text
    assert "| `orders.db:conn` | MySQL | `orders` | `LOCAL_TRANSACTION` | 1 |" in text
    page = next(out.glob("services/*selectOrders*.md")).read_text(encoding="utf-8")
    assert "## Adapter Configuration" in page
    assert "JDBC adapter service (template `Select`): selects rows from tables" in page
    caller = next(out.glob("services/*listOrders*.md")).read_text(encoding="utf-8")
    assert (
        "Through adapter services it selects rows from tables `ORDERS`, `ORDER_LINES`." in caller
    )
    analysis = _analysis(root)
    pseudo = render_pseudocode(_service(analysis, "orders.db:selectOrders"), lambda _t: None)
    assert "template: Select (selects rows from)" in pseudo
    assert "s3cret" not in pseudo


def test_unreadable_or_suspicious_adapter_values_are_dropped(tmp_path: Path) -> None:
    _irt_node(
        tmp_path,
        "orders.db",
        "conn",
        "ConnectionData",
        _blob(
            [
                ("adapterTypeName", "JDBCAdapter"),
                ("databaseName", "jdbc:mysql://db.internal/orders?user=dbadmin"),
            ]
        ),
    )
    _irt_node(tmp_path, "orders.db", "broken", "ConnectionData", "%%% not base64 %%%")
    analysis = _analysis(tmp_path)

    connection = next(a for a in analysis.namespace_artifacts if a.full_name == "orders.db:conn")
    assert connection.adapter is not None and connection.adapter.database_name is None
    assert "dbadmin" not in analysis.model_dump_json()
    assert any(f.code == "ADAPTER_CONFIGURATION_UNREADABLE" for f in analysis.findings)


# --- Triggers ------------------------------------------------------------------------------

JMS_TRIGGER = """<Values version="2.0">
  <value name="node_type">webMethods/trigger</value>
  <value name="trigger_type">jms-trigger</value>
  <record name="trigger">
    <value name="executeUser">Administrator</value>
    <value name="aliasName">ORDERS_JMS</value>
    <array name="routingRules" type="record" depth="1">
      <record>
        <value name="ruleName">Rule1</value>
        <value name="serviceName">orders.api:handleTransfer</value>
        <value name="filter">%header/JMSType% = "secretCustomer"</value>
      </record>
    </array>
    <array name="destinations" type="record" depth="1">
      <record>
        <value name="destination">internal/TransferInQueue</value>
        <value name="messageSelector">region = 'north'</value>
        <number name="destinationType" type="Integer">0</number>
      </record>
      <record>
        <value name="destination">StatusTopic</value>
        <number name="destinationType" type="Integer">1</number>
      </record>
    </array>
  </record>
</Values>"""

MESSAGING_TRIGGER = """<Values version="2.0">
  <value name="node_type">webMethods/trigger</value>
  <value name="trigger_type">broker-trigger</value>
  <record name="trigger">
    <array name="conditions" type="record" depth="1">
      <record>
        <value name="type">simple</value>
        <record name="data">
          <record name="messageTypeFilterPair">
            <value name="messageType">orders.events:orderInsertedPublishDocument</value>
            <value name="filter">%amount% &gt; 1000</value>
          </record>
          <value name="serviceName">orders.api:onInsert</value>
        </record>
      </record>
    </array>
  </record>
</Values>"""


def test_jms_trigger_details_without_filters_or_selectors(tmp_path: Path) -> None:
    _raw_node(tmp_path, "orders.triggers", "onTransfer", JMS_TRIGGER)
    _flow(tmp_path, "orders.api", "handleTransfer", '<INVOKE SERVICE="orders.api:store"/>')
    _flow(tmp_path, "orders.api", "store", "")
    analysis = _analysis(tmp_path)

    trigger = next(a.trigger for a in analysis.namespace_artifacts if a.trigger is not None)
    assert trigger.kind == "JMS trigger"
    assert trigger.connection_alias == "ORDERS_JMS"
    assert [(d.name, d.kind) for d in trigger.destinations] == [
        ("internal/TransferInQueue", "queue"),
        ("StatusTopic", "topic"),
    ]
    assert [(s.handler, s.document_type) for s in trigger.subscriptions] == [
        ("orders.api:handleTransfer", None)
    ]
    payload = analysis.model_dump_json()
    assert "secretCustomer" not in payload and "north" not in payload
    assert "Administrator" not in payload
    entry = _facts(analysis)["orders.api:store"].entry_points[0]
    assert entry.kind == "JMS trigger"
    assert entry.name == (
        "`orders.triggers:onTransfer` (queue `internal/TransferInQueue`, topic `StatusTopic`; "
        "JMS alias `ORDERS_JMS`)"
    )


def test_messaging_trigger_links_adapter_notification_to_handler(tmp_path: Path) -> None:
    _irt_node(
        tmp_path,
        "orders.events",
        "orderInserted",
        "AdapterRuntimeNotification",
        _blob(
            [
                (
                    "notificationClassName",
                    "com.wm.adapter.wmjdbc.notifications.InsertNotification",
                ),
                ("adapterTypeName", "JDBCAdapter"),
                ("connDataNodeName", "orders.db:conn"),
                ("publishableDocumentName", "orderInsertedPublishDocument"),
            ],
            tables=["ORDERS"],
        ),
    )
    _raw_node(tmp_path, "orders.events", "onOrderInserted", MESSAGING_TRIGGER)
    _flow(tmp_path, "orders.api", "onInsert", "")
    analysis = _analysis(tmp_path)

    notification = next(
        a.adapter for a in analysis.namespace_artifacts if a.full_name.endswith("orderInserted")
    )
    assert notification is not None
    assert notification.published_document == "orders.events:orderInsertedPublishDocument"
    assert notification.tables == ["ORDERS"]
    entry = _facts(analysis)["orders.api:onInsert"].entry_points[0]
    assert entry.kind == "webMethods messaging trigger"
    assert "document `orders.events:orderInsertedPublishDocument`" in entry.name
    assert (
        "published by JDBC adapter notification `orders.events:orderInserted` "
        "(InsertNotification on table `ORDERS`)"
    ) in entry.name
    assert "1000" not in analysis.model_dump_json()


# --- Opaque-service prompt -----------------------------------------------------------------


class _InventingProvider:
    """Answers with steps and error handling the facts do not contain."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def check(self, model: str) -> ProviderCheckResult:
        return ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version="test",
            model_digest="sha256:test",
            model_found=True,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.prompts.append(request.messages[1]["content"])
        payload = {
            "purpose": "Reads orders for `orders.db:selectOrders` callers.",
            "usage": "Used by the callers listed in the facts.",
            "data_effects": "Reads the tables named in the facts.",
            "steps": ["Opens a cursor.", "Runs a join with retries."],
            "error_handling": "Retries three times on deadlock.",
            "designer_comment": "Reads orders from the orders database.",
        }
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )


def test_adapter_description_steps_come_from_facts_not_the_model(tmp_path: Path) -> None:
    root = _jdbc_server(tmp_path / "packages")
    analysis = _analysis(root)
    provider = _InventingProvider()
    options = DescribeOptions(
        model="fake-model",
        scan_root=root,
        config=load_config(None),
        docs_dir=tmp_path / "service-docs",
        cache_dir=tmp_path / "cache",
    )

    describe_services(analysis, ["orders.db:selectOrders"], provider, options)

    assert "This service has no FLOW or Java steps" in provider.prompts[0]
    text = doc_path(tmp_path / "service-docs", "Orders", "orders.db:selectOrders").read_text(
        encoding="utf-8"
    )
    assert (
        "1. Selects rows from tables `ORDERS`, `ORDER_LINES` through connection "
        "`orders.db:conn`."
    ) in text
    assert "Error handling is not analysed for this service type." in text
    assert "cursor" not in text and "deadlock" not in text


def test_connection_in_a_jdbc_folder_is_not_mistaken_for_a_jdbc_url(tmp_path: Path) -> None:
    from wm_doc.disclosure import unsafe_disclosure_label

    root = tmp_path / "packages"
    _irt_node(
        root,
        "orders.jdbc",
        "ordersConn",
        "ConnectionData",
        _blob([("adapterTypeName", "JDBCAdapter"), ("databaseName", "orders")]),
    )
    _adapter_service(
        root,
        "orders.db",
        "selectOrders",
        _blob(
            [
                ("serviceTemplateName", "com.wm.adapter.wmjdbc.services.Select"),
                ("connectionName", "orders.jdbc:ordersConn"),
                ("adapterType", "JDBCAdapter"),
            ],
            tables=["ORDERS"],
        ),
    )
    facts = _facts(_analysis(root))["orders.db:selectOrders"]

    where = facts.effects[0].where
    assert "orders.jdbc:ordersConn" in where
    assert unsafe_disclosure_label(f"It reads ORDERS through {where}.") is None
    assert unsafe_disclosure_label("It uses jdbc:oracle:thin:@db:1521:X.") == "connection string"


# --- Detailed flow -------------------------------------------------------------------------

NODE_WITH_OUTPUT = """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out">
      <array name="rec_fields" type="record" depth="1">
        <record>
          <value name="node_type">record</value>
          <value name="field_name">links</value>
          <value name="field_type">string</value>
          <value name="field_dim">1</value>
        </record>
      </array>
    </record>
  </record>
</Values>"""


def _flow_with_output(root: Path, namespace: str, name: str, body: str) -> None:
    node_dir = _node_dir(root, namespace, name)
    (node_dir / "node.ndf").write_text(NODE_WITH_OUTPUT, encoding="utf-8")
    (node_dir / "flow.xml").write_text(
        f'<FLOW VERSION="3.0" CLEANUP="true">{body}</FLOW>', encoding="utf-8"
    )


def _flow_server(root: Path) -> Path:
    _flow_with_output(root, "orders.links", "findLinks", "")
    _flow(
        root,
        "orders.api",
        "getContracts",
        '<INVOKE SERVICE="orders.links:findLinks"/>'
        '<INVOKE SERVICE="orders.db:selectOrders">'
        '<MAP MODE="INPUT"><MAPCOPY FROM="/links;1;1" TO="/ids;1;1"/></MAP></INVOKE>',
    )
    _adapter_service(
        root,
        "orders.db",
        "selectOrders",
        _blob(
            [
                ("serviceTemplateName", "com.wm.adapter.wmjdbc.services.Select"),
                ("connectionName", "orders.jdbc:ordersConn"),
                ("adapterType", "JDBCAdapter"),
            ],
            tables=["ORDERS"],
        ),
    )
    return root


def test_calls_show_what_the_called_service_returns(tmp_path: Path) -> None:
    from wm_doc.pseudocode import callee_outputs_lookup

    analysis = _analysis(_flow_server(tmp_path))
    services = {service.identity.full_name: service for service in analysis.services}

    pseudo = render_pseudocode(
        services["orders.api:getContracts"],
        lambda _target: None,
        callee_outputs=callee_outputs_lookup(services),
    )

    lines = pseudo.splitlines()
    call = next(i for i, line in enumerate(lines) if "CALL orders.links:findLinks" in line)
    assert lines[call + 1].strip() == "returns: links: string list"


class _FlowProvider(_InventingProvider):
    """Answers with a detailed flow; the first answer names a field that is not in the facts."""

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.prompts.append(request.messages[1]["content"])
        unknown = "`customerIds`" if len(self.prompts) == 1 else "`ids`"
        payload = {
            "purpose": "Returns orders for `orders.api:getContracts` callers.",
            "usage": "Used by the callers listed in the facts.",
            "data_effects": "Reads table `ORDERS`.",
            "steps": ["Finds links.", "Selects orders."],
            "detailed_steps": [
                "Calls `orders.links:findLinks`, which returns `links`.",
                f"Calls `orders.db:selectOrders` with {unknown} copied from `links`; it "
                "selects rows from table `ORDERS` through connection `orders.jdbc:ordersConn`.",
            ],
            "error_handling": "Not shown in the facts.",
            "designer_comment": "Returns orders.",
        }
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )


def test_description_gets_a_detailed_flow_checked_like_the_rest(tmp_path: Path) -> None:
    root = _flow_server(tmp_path / "packages")
    provider = _FlowProvider()
    options = DescribeOptions(
        model="fake-model",
        scan_root=root,
        config=load_config(None),
        docs_dir=tmp_path / "service-docs",
        cache_dir=tmp_path / "cache",
    )

    describe_services(_analysis(root), ["orders.api:getContracts"], provider, options)

    prompt = provider.prompts[0]
    assert "returns: links: string list" in prompt
    assert "JDBC adapter service (template `Select`): selects rows from table `ORDERS`" in prompt
    assert "detailed_steps" in prompt
    # The first answer named `customerIds`, which is not in the facts: one retry fixed it.
    assert len(provider.prompts) == 2
    text = doc_path(tmp_path / "service-docs", "Orders", "orders.api:getContracts").read_text(
        encoding="utf-8"
    )
    assert "## Detailed flow\n\n1. Calls `orders.links:findLinks`, which returns `links`." in text
    assert "2. Calls `orders.db:selectOrders` with `ids` copied from `links`" in text


# --- Thorough level: completeness pass -----------------------------------------------------


class _CoverageProvider(_InventingProvider):
    """First answer leaves out `orders.db:selectOrders`; later answers follow `steps`."""

    def __init__(self, later_steps: list[str]) -> None:
        super().__init__()
        self.later_steps = later_steps
        self.messages: list[list[dict[str, str]]] = []

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.prompts.append(request.messages[1]["content"])
        self.messages.append(request.messages)
        first = ["Calls `orders.links:findLinks`, which returns `links`."]
        payload = {
            "purpose": "Returns orders for `orders.api:getContracts` callers.",
            "usage": "Used by the callers listed in the facts.",
            "data_effects": "Reads table `ORDERS`.",
            "steps": ["Finds links.", "Selects orders."],
            "detailed_steps": first if len(self.prompts) == 1 else self.later_steps,
            "error_handling": "Not shown in the facts.",
            "designer_comment": "Returns orders.",
        }
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )


def _describe_get_contracts(
    tmp_path: Path, provider: _CoverageProvider, detail: DetailLevel
) -> tuple[str, list[DescribeResult]]:
    root = _flow_server(tmp_path / "packages")
    options = DescribeOptions(
        model="fake-model",
        scan_root=root,
        config=load_config(None),
        docs_dir=tmp_path / "service-docs",
        cache_dir=tmp_path / "cache",
        detail=detail,
    )
    results, _ = describe_services(
        _analysis(root), ["orders.api:getContracts"], provider, options
    )
    text = doc_path(tmp_path / "service-docs", "Orders", "orders.api:getContracts").read_text(
        encoding="utf-8"
    )
    return text, results


def test_thorough_asks_once_more_for_calls_the_flow_left_out(tmp_path: Path) -> None:
    provider = _CoverageProvider(
        [
            "Calls `orders.links:findLinks`, which returns `links`.",
            "Calls `orders.db:selectOrders` with `ids` copied from `links`.",
        ]
    )

    text, results = _describe_get_contracts(tmp_path, provider, DetailLevel.THOROUGH)

    assert results[0].outcome is DescribeOutcome.GENERATED
    assert len(provider.messages) == 2
    follow_up = provider.messages[1][-1]["content"]
    assert "do not mention these calls the service makes: `orders.db:selectOrders`" in follow_up
    assert "2. Calls `orders.db:selectOrders` with `ids` copied from `links`." in text
    assert "detail: thorough" in text


def test_thorough_keeps_the_first_answer_when_the_second_is_no_better(tmp_path: Path) -> None:
    provider = _CoverageProvider(["Calls `orders.links:findLinks` again."])

    text, _ = _describe_get_contracts(tmp_path, provider, DetailLevel.THOROUGH)

    assert len(provider.messages) == 2
    assert "1. Calls `orders.links:findLinks`, which returns `links`." in text


def test_standard_does_not_check_completeness(tmp_path: Path) -> None:
    provider = _CoverageProvider([])

    _describe_get_contracts(tmp_path, provider, DetailLevel.STANDARD)

    assert len(provider.messages) == 1
