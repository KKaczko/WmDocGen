"""Synthetic Integration Server packages for explorer demos and tests.

Everything here is invented: package, service, table and queue names, and the fake secrets
that tests use to prove nothing secret reaches the explorer. The packages are shaped like
real 10.x exports (the same files the reader tests use) and are analysed by the normal
pipeline, so a demo shows real analysis output without any real data.

The core set is a small order-handling server:

- OrdersApi: REST v1 handlers, FLOW services with TRY/CATCH, a JMS trigger, document types,
  a Java router with a static and a dynamic `Service.doInvoke`, and calls to a billing
  service that is not among the packages.
- OrdersDb: a JDBC connection and three JDBC adapter services.
- CommonUtils: logging and an error handler that many services call, and an XSLT service.
- CustomerApi: services calling a CRM service that is not among the packages.

`filler_services` adds packages of generated services that call each other and the common
ones, for larger demos and scale tests. Output is deterministic.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from wm_doc.config import AppConfig
from wm_doc.describer import current_facts_hashes, render_facts_block
from wm_doc.effects import compute_service_facts
from wm_doc.ir import AnalysisResult
from wm_doc.overviews import (
    OverviewNarrative,
    facts_markdown_block,
    package_facts_text,
    server_facts_text,
    summarize_packages,
)
from wm_doc.service_docs import (
    DETAIL_KEY,
    UNVERIFIED_KEY,
    DocStatus,
    Narrative,
    ServiceDoc,
    doc_path,
    facts_hash,
    overview_doc_path,
    text_hash,
    write_doc,
)

# Fake values a reader must never publish (see tests/fixtures/test_explorer.py).
FAKE_SECRETS = (
    "Sup3r-S3cret-Demo",
    "demo-db-admin",
    "db.synthetic.invalid",
    "jdbc:oracle:thin:@db.synthetic.invalid:1521/ORDERS",
    "https://billing.synthetic.invalid/api",
)
FILLER_PACKAGE_SIZE = 25
FILLER_DOCUMENTS_PER_PACKAGE = 400


@dataclass(frozen=True)
class _Field:
    name: str
    type: str = "string"
    dim: int = 0
    ref: str | None = None


def write_demo_packages(root: Path, filler_services: int = 0, filler_documents: int = 0) -> int:
    """Write the synthetic packages under *root*; return the number of services written.

    `filler_services` and `filler_documents` add generated services and document types for
    larger demos and scale tests (the services take the documents as inputs).
    """
    writer = _Writer(root)
    _orders_api(writer)
    _orders_db(writer)
    _common_utils(writer)
    _customer_api(writer)
    _filler(writer, filler_services, filler_documents)
    return writer.services


class _Writer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.services = 0
        self._manifests: set[str] = set()

    def node_dir(self, package: str, full_name: str) -> Path:
        self._manifest(package)
        namespace, name = full_name.split(":", 1)
        path = self.root / package / "ns" / Path(*namespace.split(".")) / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def flow(
        self,
        package: str,
        full_name: str,
        body: str,
        *,
        inputs: tuple[_Field, ...] = (),
        outputs: tuple[_Field, ...] = (),
        comment: str = "",
    ) -> None:
        path = self.node_dir(package, full_name)
        (path / "node.ndf").write_text(_service_node("flow", inputs, outputs), encoding="utf-8")
        flow_comment = f"<COMMENT>{escape(comment)}</COMMENT>\n" if comment else ""
        (path / "flow.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<FLOW VERSION="3.0" CLEANUP="true">\n{flow_comment}{body}\n</FLOW>\n',
            encoding="utf-8",
        )
        self.services += 1

    def opaque(self, package: str, full_name: str, svc_type: str, extra: str = "") -> None:
        path = self.node_dir(package, full_name)
        (path / "node.ndf").write_text(_service_node(svc_type, (), (), extra), encoding="utf-8")
        self.services += 1

    def raw(self, package: str, full_name: str, content: str) -> None:
        path = self.node_dir(package, full_name)
        (path / "node.ndf").write_text(content, encoding="utf-8")

    def document(self, package: str, full_name: str, fields: tuple[_Field, ...]) -> None:
        path = self.node_dir(package, full_name)
        (path / "node.ndf").write_text(
            '<Values version="2.0">\n'
            '  <record name="record" javaclass="com.wm.util.Values">\n'
            '    <value name="node_type">record</value>\n'
            f'    <value name="node_nsName">{escape(full_name)}</value>\n'
            f'    <value name="node_pkg">{escape(package)}</value>\n'
            '    <value name="field_type">record</value>\n'
            '    <value name="field_dim">0</value>\n'
            '    <array name="rec_fields" type="record" depth="1">\n'
            f"{_fields_xml(fields)}"
            "    </array>\n"
            "  </record>\n"
            "</Values>\n",
            encoding="utf-8",
        )

    def java(self, package: str, full_name: str, body: str) -> None:
        namespace, name = full_name.split(":", 1)
        *java_package, class_name = namespace.split(".")
        path = self.node_dir(package, full_name)
        (path / "node.ndf").write_text(
            '<Values version="2.0">\n'
            '  <value name="svc_type">java</value>\n'
            '  <value name="svc_sigtype">java 3.5</value>\n'
            "</Values>\n",
            encoding="utf-8",
        )
        encoded = base64.b64encode(body.encode("utf-8")).decode("ascii")
        (path / "java.frag").write_text(
            '<Values version="2.0">\n'
            f'  <value name="name">{name}</value>\n'
            f'  <value name="body">{encoded}</value>\n'
            "</Values>\n",
            encoding="utf-8",
        )
        source_dir = self.root / package / "code" / "source" / Path(*java_package)
        source = source_dir / f"{class_name}.java"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            f"package {'.'.join(java_package)};\n\n"
            "import com.wm.data.*;\n"
            "import com.wm.app.b2b.server.Service;\n"
            "import com.wm.app.b2b.server.ServiceException;\n\n"
            f"public final class {class_name} {{\n"
            f"public static final void {name} (IData pipeline) throws ServiceException\n"
            f"{{\n{body}\n}}\n}}\n",
            encoding="utf-8",
        )
        self.services += 1

    def _manifest(self, package: str) -> None:
        if package in self._manifests:
            return
        self._manifests.add(package)
        package_root = self.root / package
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "manifest.v3").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Values version="2.0">\n'
            '  <value name="enabled">yes</value>\n'
            '  <value name="system_package">no</value>\n'
            '  <value name="version">1.0</value>\n'
            "</Values>\n",
            encoding="utf-8",
        )


def _service_node(
    svc_type: str, inputs: tuple[_Field, ...], outputs: tuple[_Field, ...], extra: str = ""
) -> str:
    return (
        '<Values version="2.0">\n'
        f'  <value name="svc_type">{escape(svc_type)}</value>\n'
        f"{extra}"
        '  <record name="svc_sig">\n'
        '    <record name="sig_in">\n'
        '      <array name="rec_fields" type="record" depth="1">\n'
        f"{_fields_xml(inputs)}"
        "      </array>\n"
        "    </record>\n"
        '    <record name="sig_out">\n'
        '      <array name="rec_fields" type="record" depth="1">\n'
        f"{_fields_xml(outputs)}"
        "      </array>\n"
        "    </record>\n"
        "  </record>\n"
        "</Values>\n"
    )


def _fields_xml(fields: tuple[_Field, ...]) -> str:
    out = ""
    for field in fields:
        out += "        <record>\n"
        out += f'          <value name="field_name">{escape(field.name)}</value>\n'
        out += f'          <value name="field_type">{field.type}</value>\n'
        out += f'          <value name="field_dim">{field.dim}</value>\n'
        if field.ref:
            out += f'          <value name="rec_ref">{escape(field.ref)}</value>\n'
        out += "        </record>\n"
    return out


def _invoke(target: str, *, disabled: bool = False, input_map: str = "") -> str:
    flag = ' DISABLED="true"' if disabled else ""
    return (
        f'<INVOKE TIMEOUT="" SERVICE={quoteattr(target)} VALIDATE-IN="$none" '
        f'VALIDATE-OUT="$none"{flag}>{input_map}</INVOKE>'
    )


def _try_catch(try_steps: list[str], catch_steps: list[str]) -> str:
    return (
        '<SEQUENCE TIMEOUT="" EXIT-ON="SUCCESS">\n'
        '  <SEQUENCE TIMEOUT="" EXIT-ON="FAILURE" FORM="TRY">\n    '
        + "\n    ".join(try_steps)
        + "\n  </SEQUENCE>\n"
        '  <SEQUENCE TIMEOUT="" EXIT-ON="DONE" FORM="CATCH">\n    '
        + "\n    ".join(catch_steps)
        + "\n  </SEQUENCE>\n</SEQUENCE>"
    )


def _mapset(field: str, value: str) -> str:
    return _map("STANDALONE", {field: value})


def _map(mode: str, values: dict[str, str]) -> str:
    """A MAP step setting literal string values on top-level fields."""
    sets = "".join(_set(field, value) for field, value in values.items())
    return f'<MAP MODE="{mode}">\n{sets}</MAP>'


def _set(field: str, value: str) -> str:
    return (
        f"  <MAPSET FIELD={quoteattr(f'/{field};1;0')}>\n"
        '    <DATA ENCODING="XMLValues" I18N="true">\n'
        '      <Values version="2.0">\n'
        f'        <value name="xml">{escape(value)}</value>\n'
        '        <record name="type">\n'
        f'          <value name="field_name">{escape(field)}</value>\n'
        '          <value name="field_type">string</value>\n'
        "        </record>\n"
        "      </Values>\n"
        "    </DATA>\n"
        "  </MAPSET>\n"
    )


# --- JDBC adapter nodes (see wm_doc.adapters for the encoding) ------------------------------


def _token(text: str) -> bytes:
    return bytes([0x04, len(text)]) + text.encode("utf-16-be")


def _blob(pairs: list[tuple[str, str]], tables: list[str] | None = None) -> str:
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


def _adapter_service(
    writer: _Writer, package: str, full_name: str, template: str, tables: list[str]
) -> None:
    blob = _blob(
        [
            ("serviceTemplateName", f"com.wm.adapter.wmjdbc.services.{template}"),
            ("connectionName", "orders.db:conn"),
            ("adapterType", "JDBCAdapter"),
            ("sql", f"SELECT * FROM {tables[0]} WHERE NOTE = '{FAKE_SECRETS[0]}'"),
        ],
        tables=tables,
    )
    writer.opaque(
        package,
        full_name,
        "AdapterService",
        f'  <value name="IRTNODE_PROPERTY">{blob}</value>\n',
    )


# --- The order-handling server ----------------------------------------------------------------

ORDER = _Field("order", "recref", ref="orders.docs:Order")


def _orders_api(writer: _Writer) -> None:
    package = "OrdersApi"
    writer.document(
        package,
        "orders.docs:Order",
        (
            _Field("orderId"),
            _Field("customerId"),
            _Field("lines", "recref", 1, "orders.docs:OrderLine"),
            _Field("total"),
        ),
    )
    writer.document(
        package,
        "orders.docs:OrderLine",
        (_Field("productId"), _Field("quantity"), _Field("price")),
    )
    writer.flow(
        package,
        "orders.rest.order:_post",
        _invoke("orders.api:createOrder"),
        inputs=(ORDER,),
        outputs=(_Field("orderId"),),
    )
    writer.flow(
        package,
        "orders.rest.order:_get",
        _invoke("orders.api:getOrder"),
        inputs=(_Field("orderId"),),
        outputs=(ORDER,),
    )
    writer.flow(
        package,
        "orders.api:createOrder",
        _mapset("billingEndpoint", FAKE_SECRETS[4])
        + "\n"
        + _try_catch(
            [
                _invoke("orders.api:validateOrder"),
                _invoke("orders.api.routing:routeOrder"),
                _invoke("orders.db:insertOrder"),
                _invoke(
                    "pub.client:http",
                    input_map=_map("INPUT", {"url": FAKE_SECRETS[4], "method": "POST"}),
                ),
                _invoke("billing.api:postInvoice"),
                _invoke("pub.flow:debugLog", disabled=True),
                _invoke("common.log:logEvent"),
            ],
            [_invoke("pub.flow:getLastError"), _invoke("common.error:handleError")],
        ),
        inputs=(ORDER,),
        outputs=(_Field("orderId"),),
        comment=f"Creates the order. Test password={FAKE_SECRETS[0]} must never be shown.",
    )
    writer.flow(
        package,
        "orders.api:getOrder",
        _try_catch(
            [_invoke("orders.db:selectOrder"), _invoke("common.log:logEvent")],
            [_invoke("common.error:handleError")],
        ),
        inputs=(_Field("orderId"),),
        outputs=(ORDER,),
    )
    writer.flow(
        package,
        "orders.api:validateOrder",
        _invoke("pub.date:getCurrentDate") + "\n" + _invoke("common.util:transformOrder"),
        inputs=(ORDER,),
        outputs=(_Field("valid"),),
    )
    writer.flow(
        package,
        "orders.api:cancelOrder",
        _try_catch(
            [_invoke("orders.db:deleteOrder"), _invoke("common.log:logEvent")],
            [_invoke("common.error:handleError")],
        ),
        inputs=(_Field("orderId"),),
    )
    writer.java(
        package,
        "orders.api.routing:routeOrder",
        "IDataCursor cursor = pipeline.getCursor();\n"
        'String channel = IDataUtil.getString(cursor, "channel");\n'
        "cursor.destroy();\n"
        'Service.doInvoke("orders.api", "validateOrder", pipeline);\n'
        'Service.doInvoke("orders.channels", channel, pipeline);',
    )
    writer.raw(
        package,
        "orders.triggers:onOrderCancelled",
        '<Values version="2.0">\n'
        '  <value name="node_type">webMethods/trigger</value>\n'
        '  <value name="trigger_type">jms-trigger</value>\n'
        '  <record name="trigger">\n'
        f'    <value name="executeUser">{FAKE_SECRETS[1]}</value>\n'
        '    <value name="aliasName">ORDERS_JMS</value>\n'
        '    <array name="routingRules" type="record" depth="1">\n'
        "      <record>\n"
        '        <value name="ruleName">Rule1</value>\n'
        '        <value name="serviceName">orders.api:cancelOrder</value>\n'
        "      </record>\n"
        "    </array>\n"
        '    <array name="destinations" type="record" depth="1">\n'
        "      <record>\n"
        '        <value name="destination">orders/CancelQueue</value>\n'
        '        <number name="destinationType" type="Integer">0</number>\n'
        "      </record>\n"
        "    </array>\n"
        "  </record>\n"
        "</Values>\n",
    )


def _orders_db(writer: _Writer) -> None:
    package = "OrdersDb"
    writer.raw(
        package,
        "orders.db:conn",
        '<Values version="2.0">\n'
        '  <value name="node_type">ConnectionData</value>\n'
        '  <number name="IRTNODE_VERSION" type="Integer">1</number>\n'
        '  <value name="IRTNODE_PROPERTY">'
        + _blob(
            [
                ("adapterTypeName", "JDBCAdapter"),
                ("transactionType", "LOCAL_TRANSACTION"),
                ("datasourceClass", "oracle.jdbc.pool.OracleDataSource"),
                ("serverName", FAKE_SECRETS[2]),
                ("user", FAKE_SECRETS[1]),
                ("password", FAKE_SECRETS[0]),
                ("databaseName", "ORDERS"),
                ("portNumber", "1521"),
                ("otherProperties", FAKE_SECRETS[3]),
            ]
        )
        + "</value>\n</Values>\n",
    )
    _adapter_service(writer, package, "orders.db:insertOrder", "Insert", ["ORDERS", "ORDER_LINES"])
    _adapter_service(writer, package, "orders.db:selectOrder", "Select", ["ORDERS"])
    _adapter_service(writer, package, "orders.db:deleteOrder", "Delete", ["ORDERS"])


def _common_utils(writer: _Writer) -> None:
    package = "CommonUtils"
    writer.flow(
        package,
        "common.log:logEvent",
        _invoke("pub.flow:debugLog"),
        inputs=(_Field("message"), _Field("level")),
    )
    writer.flow(
        package,
        "common.error:handleError",
        _invoke("pub.flow:getLastError") + "\n" + _invoke("common.log:logEvent"),
        outputs=(_Field("errorMessage"),),
    )
    writer.opaque(package, "common.util:transformOrder", "xslt")


def _customer_api(writer: _Writer) -> None:
    package = "CustomerApi"
    writer.flow(
        package,
        "customers.api:getCustomer",
        _try_catch(
            [_invoke("crm.api:lookupCustomer"), _invoke("common.log:logEvent")],
            [_invoke("common.error:handleError")],
        ),
        inputs=(_Field("customerId"),),
        outputs=(_Field("customer", "record"),),
    )
    writer.flow(
        package,
        "customers.api:updateCustomer",
        _invoke("customers.api:getCustomer") + "\n" + _invoke("crm.api:updateCustomer"),
        inputs=(_Field("customerId"), _Field("customer", "record")),
    )


def _filler(writer: _Writer, count: int, documents: int) -> None:
    for index in range(documents):
        package_index, position = divmod(index, FILLER_DOCUMENTS_PER_PACKAGE)
        fields: tuple[_Field, ...] = (
            _Field("id"),
            _Field("name"),
            _Field("amount"),
            _Field("status"),
            _Field("created"),
        )
        if position > 0 and position % 4 == 0:
            previous = _document_name(package_index, position - 1)
            fields += (_Field("parent", "recref", ref=previous),)
            fields += (_Field("history", "recref", 1, previous),)
        writer.document(
            f"DemoDocs{package_index + 1:03d}", _document_name(package_index, position), fields
        )
    for index in range(count):
        package_index, position = divmod(index, FILLER_PACKAGE_SIZE)
        package = f"Demo{package_index + 1:03d}"
        namespace = f"demo{package_index + 1:03d}.flows"
        steps = [_invoke("common.log:logEvent")]
        if position + 1 < FILLER_PACKAGE_SIZE and index + 1 < count:
            steps.append(_invoke(f"{namespace}:step{position + 1:03d}"))
        if position % 5 == 0:
            steps.append(_invoke("orders.api:getOrder"))
        if position % 7 == 3:
            steps.append(_invoke("pub.client:http"))
        inputs: tuple[_Field, ...] = (_Field("requestId"),)
        if documents:
            document = index % documents
            inputs += (
                _Field(
                    "record",
                    "recref",
                    ref=_document_name(*divmod(document, FILLER_DOCUMENTS_PER_PACKAGE)),
                ),
            )
        writer.flow(
            package,
            f"{namespace}:step{position:03d}",
            _try_catch(steps, [_invoke("common.error:handleError")]),
            inputs=inputs,
        )


def _document_name(package_index: int, position: int) -> str:
    return f"demodocs{package_index + 1:03d}.records:Record{position:04d}"


# --- Description files ------------------------------------------------------------------------
# Synthetic narratives in every review state, written through the real description-file code
# with the real facts hashes, so the explorer shows them exactly as it would show yours. One of
# them carries hostile and secret-like text to prove it is shown inert or withheld.

_HOSTILE_PURPOSE = (
    "Updates a customer in the CRM. Inert text test: </b> javascript:window.__pwned=1 "
    "onerror=window.__pwned=1 &lt;b&gt; {{constructor.constructor('window.__pwned=1')()}} "
    "and a direction override:" + chr(0x202E) + "txet."
)
HOSTILE_VISIBLE = ("</b> javascript:window.__pwned=1", "&lt;b&gt;")
NOTES_MARKER = "NOTES-MARKER reviewer note that is never exported"


@dataclass(frozen=True)
class _Demo:
    state: str  # approved | stale | draft | edited
    purpose: str
    usage: str
    data_effects: str
    steps: tuple[str, ...]
    error_handling: str
    detailed: tuple[str, ...] = ()
    unverified: tuple[str, ...] = ()


_DEMOS: dict[str, _Demo] = {
    "orders.api:createOrder": _Demo(
        "approved",
        "Creates an order from a REST request, stores it with `orders.db:insertOrder` and sends "
        "the invoice to the billing service.",
        "Called by the REST v1 handler `orders.rest.order:_post` (POST /rest/orders/rest/order).",
        "Inserts rows into `ORDERS` and `ORDER_LINES` and calls the billing service "
        "`billing.api:postInvoice`, which is outside the analysed packages.",
        (
            "Validates the order with `orders.api:validateOrder`.",
            "Routes it with `orders.api.routing:routeOrder`.",
            "Stores it with `orders.db:insertOrder`.",
            "Sends it over HTTP and posts the invoice with `billing.api:postInvoice`.",
            "Logs the result with `common.log:logEvent`.",
        ),
        "On any failure the CATCH block reads the last error with `pub.flow:getLastError` and "
        "calls `common.error:handleError`.",
        detailed=(
            "`orders.api:validateOrder` receives `order` and returns `valid`.",
            "`orders.db:insertOrder` inserts the order into `ORDERS` and `ORDER_LINES`.",
            "`pub.client:http` posts to the billing endpoint; its URL is a literal in the FLOW.",
        ),
    ),
    "orders.db:insertOrder": _Demo(
        "approved",
        "Inserts an order and its lines into the orders database.",
        "Called by `orders.api:createOrder`.",
        "Inserts rows into `ORDERS` and `ORDER_LINES` through the JDBC connection "
        "`orders.db:conn`.",
        ("Runs the configured JDBC Insert operation on `ORDERS` and `ORDER_LINES`.",),
        "Not analysed: adapter services are configured, not programmed.",
    ),
    "orders.api:getOrder": _Demo(
        "stale",
        "Reads one order by its ID.",
        "Called by the REST v1 handler `orders.rest.order:_get` and by the demo flows.",
        "Selects rows from `ORDERS`.",
        ("Selects the order with `orders.db:selectOrder`.", "Logs the read."),
        "Errors go to `common.error:handleError`.",
    ),
    "orders.api:validateOrder": _Demo(
        "draft",
        "Checks an order before it is stored.",
        "Called by `orders.api:createOrder` and `orders.api.routing:routeOrder`.",
        "Reads the current date and transforms the order with an XSLT service.",
        ("Gets the current date.", "Transforms the order with `common.util:transformOrder`."),
        "No error handling of its own.",
    ),
    "orders.api:cancelOrder": _Demo(
        "edited",
        "Cancels an order when a cancellation message arrives.",
        "Started by the JMS trigger `orders.triggers:onOrderCancelled`.",
        "Deletes rows from `ORDERS`.",
        ("Deletes the order with `orders.db:deleteOrder`.", "Logs the cancellation."),
        "Errors go to `common.error:handleError`.",
    ),
    "customers.api:getCustomer": _Demo(
        "draft",
        "Looks a customer up in the CRM.",
        "Called by `customers.api:updateCustomer`.",
        "Calls `crm.api:lookupCustomer`, which is outside the analysed packages.",
        ("Calls `crm.api:lookupCustomer`.", "Falls back to `crm.legacy:findCustomer`."),
        "Errors go to `common.error:handleError`.",
        unverified=("crm.legacy:findCustomer",),
    ),
    "customers.api:updateCustomer": _Demo(
        "approved",
        _HOSTILE_PURPOSE,
        "Hostile markup test: <img src=x onerror=window.__pwned=1> must be withheld.",
        "Writes to the CRM. password=hunter2-demo must be withheld.",
        (
            "Reads the customer with `customers.api:getCustomer`.",
            "Then [click here](javascript:window.__pwned=1) must be withheld.",
            "Updates it with `crm.api:updateCustomer`.",
        ),
        "None.",
    ),
}


def write_demo_descriptions(
    docs_dir: Path, analysis: AnalysisResult, packages_root: Path, config: AppConfig
) -> int:
    """Write the synthetic description files for the services that exist; return how many."""
    services = {service.identity.full_name: service for service in analysis.services}
    signatures = {name: service.signature for name, service in services.items()}
    names = [name for name in _DEMOS if name in services]
    facts = compute_service_facts(analysis)
    hashes = current_facts_hashes(analysis, packages_root, config, facts=facts, only=set(names))
    for name in names:
        demo = _DEMOS[name]
        service = services[name]
        narrative = Narrative(
            purpose=demo.purpose,
            usage=demo.usage,
            data_effects=demo.data_effects,
            steps=demo.steps,
            error_handling=demo.error_handling,
            designer_comment=f"Demo comment. password={FAKE_SECRETS[0]} is never exported.",
            detailed_steps=demo.detailed,
        ).markdown()
        current = hashes[name]
        written_text = narrative
        if demo.state == "edited":
            narrative = narrative.replace("Cancels an order", "Cancels an order (edited)")
        extra: dict[str, object] = {DETAIL_KEY: "standard"}
        if demo.unverified:
            extra[UNVERIFIED_KEY] = list(demo.unverified)
        doc = ServiceDoc(
            service=name,
            package=service.identity.package,
            status=DocStatus.APPROVED if demo.state in ("approved", "stale") else DocStatus.DRAFT,
            model="synthetic-demo-model",
            facts_hash=current if demo.state != "stale" else "0" * len(current),
            text_hash=text_hash(written_text),
            narrative=narrative,
            notes=NOTES_MARKER,
            facts_markdown=render_facts_block(service, facts[name], signatures),
            current_facts_hash=current,
            extra_front_matter=extra,
        )
        write_doc(doc_path(docs_dir, service.identity.package, name), doc)
    return len(names)


# --- Overview files --------------------------------------------------------------------------

_PACKAGE_OVERVIEWS: dict[str, tuple[str, OverviewNarrative]] = {
    "OrdersApi": (
        "approved",
        OverviewNarrative(
            kind="package",
            purpose="Takes orders over REST, stores them and sends invoices to billing.",
            items=(
                "Order intake through `orders.rest.order:_post` and `orders.api:createOrder`.",
                "Order lookup through `orders.rest.order:_get`.",
                "Cancellation from the JMS queue `orders/CancelQueue`.",
            ),
            entry_points="REST v1 handlers and one JMS trigger.",
            systems_and_data="The orders database through OrdersDb, and the billing service.",
        ),
    ),
    "OrdersDb": (
        "draft",
        OverviewNarrative(
            kind="package",
            purpose="Holds the JDBC adapter services for the orders database.",
            items=("Insert, select and delete on `ORDERS` and `ORDER_LINES`.",),
            entry_points="Called by OrdersApi only.",
            systems_and_data="An Oracle database through the connection `orders.db:conn`.",
        ),
    ),
}

_SERVER_OVERVIEW = OverviewNarrative(
    kind="server",
    purpose="A synthetic order-handling server: orders come in over REST and JMS, are stored "
    "in an Oracle database and invoiced through an external billing service.",
    items=(
        "Orders: OrdersApi and OrdersDb.",
        "Customers: CustomerApi, backed by an external CRM.",
        "Shared logging and error handling: CommonUtils.",
        "Generated demo flows: the Demo packages.",
    ),
    entry_points="REST v1 handlers, a JMS trigger, and services with no callers.",
    systems_and_data="An Oracle orders database, a billing service and a CRM outside the packages.",
)


def write_demo_overviews(docs_dir: Path, analysis: AnalysisResult) -> int:
    """Write synthetic package and server overview files; return how many."""
    summaries = summarize_packages(analysis, compute_service_facts(analysis))
    written = 0
    for package, (state, narrative) in _PACKAGE_OVERVIEWS.items():
        if package not in summaries:
            continue
        facts = package_facts_text(summaries[package])
        _write_overview(
            overview_doc_path(docs_dir, package),
            f"package:{package}",
            package,
            state,
            narrative,
            facts,
            "package",
        )
        written += 1
    _write_overview(
        overview_doc_path(docs_dir, None),
        "server",
        "",
        "approved",
        _SERVER_OVERVIEW,
        server_facts_text(summaries),
        "server",
    )
    return written + 1


def _write_overview(
    path: Path,
    service: str,
    package: str,
    state: str,
    narrative: OverviewNarrative,
    facts: str,
    kind: str,
) -> None:
    markdown = narrative.markdown()
    current = facts_hash(facts)
    write_doc(
        path,
        ServiceDoc(
            service=service,
            package=package,
            status=DocStatus.APPROVED if state == "approved" else DocStatus.DRAFT,
            model="synthetic-demo-model",
            facts_hash=current,
            text_hash=text_hash(markdown),
            narrative=markdown,
            notes=NOTES_MARKER,
            facts_markdown=facts_markdown_block(kind, facts),
            current_facts_hash=current,
        ),
    )
