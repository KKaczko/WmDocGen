"""Platform service catalog: shipped descriptions, user additions, the page and stats."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.builtins import (
    SHIPPED_SERVICES,
    PlatformServicesError,
    builtin_effect,
    load_platform_services,
    use_platform_catalog,
)
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.effects import compute_service_facts
from wm_doc.external_systems import ExternalSystemCatalog
from wm_doc.stats import render_stats

# Platform services the production `stats` listed as missing (names only).
PRODUCTION_NAMES = (
    "pub.client:restClient",
    "pub.date:getCurrentDate",
    "wm.server.openapi:invoke",
    "pub.math:roundNumber",
    "pub.client.ldap:search",
    "pub.flow:getCallingService",
    "pub.json.schema:validate",
    "pub.date:currentNanoTime",
    "pub.flow:savePipelineToFile",
    "pub.math:absoluteValue",
    "pub.cache.serviceResults:resetServiceCache",
    "pub.math:addObjects",
    "pub.date:dateTimeBuild",
    "pub.io:stringToStream",
    "pub.math:multiplyObjects",
    "pub.soap.utils:getXOPObjectContent",
    "wm.server.ns.dependency:getReferenced",
    "pub.datetime:increment",
    "pub.schema:createXSD",
    "pub.security.outboundPasswords:getPassword",
    "pub.soap.utils:createXOPObject",
    "pub.sync:notify",
    "pub.sync:wait",
    "pub.trigger:resumeProcessing",
    "pub.trigger:suspendProcessing",
    "wm.art.admin.connection:getResourceConfiguration",
    "pub.art.connection:enableConnection",
    "pub.art.connection:getConnectionStatistics",
    "pub.art.connection:listAdapterConnections",
    "pub.art.connection:queryConnectionState",
    "pub.cache.atomic:putIfAbsent",
    "pub.cache.serviceResults:resetServerCache",
    "pub.client.ldap:modify",
    "pub.math:max",
    "pub.math:min",
    "pub.math:randomDouble",
    "pub.scheduler:getTaskIDs",
    "pub.scheduler:getTaskInfo",
    "pub.scheduler:getUserTaskList",
    "pub.scheduler:resumeTask",
    # Second production run.
    "pub.security.outboundPasswords:updatePassword",
    "pub.security.util:convertSecureString",
    "pub.security.util:createSecureString",
    "pub.security.util:destroySecureString",
    "pub.security:encrypt",
    "pub.soap.handler:getSOAPMessage",
    "pub.soap.handler:registerWmConsumer",
    "pub.soap.handler:unregisterConsumer",
    "wm.art.dev.connection:createConnectionNode",
    "wm.monitor.util:getCurrentUser",
    "wm.server.access:userList",
    "wm.server.packages:packageActivate",
    "wm.server.packages:packageCreate",
    "wm.server.packages:packageInfo",
    "wm.server.packages:packageList",
    "wm.server.query:getServiceStats",
    "wm.server.query:getStats",
)

FLOW_NODE = """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>"""


@pytest.fixture(autouse=True)
def shipped_catalog() -> Iterator[None]:
    use_platform_catalog(None)
    yield
    use_platform_catalog(None)


def _flow(root: Path, namespace: str, name: str, body: str) -> None:
    node_dir = root / "Orders" / "ns" / Path(*namespace.split(".")) / name
    node_dir.mkdir(parents=True)
    (node_dir / "node.ndf").write_text(FLOW_NODE, encoding="utf-8")
    (node_dir / "flow.xml").write_text(
        f'<FLOW VERSION="3.0" CLEANUP="true">{body}</FLOW>', encoding="utf-8"
    )


def _set(field: str, value: str) -> str:
    return (
        f'<MAPSET FIELD="/{field};1;0"><DATA ENCODING="XMLValues" I18N="true">'
        f'<Values version="2.0"><value name="xml">{value}</value>'
        f'<record name="type"><value name="field_name">{field}</value>'
        '<value name="field_type">string</value></record></Values></DATA></MAPSET>'
    )


def _invoke(target: str, *input_ops: str) -> str:
    return (
        f'<INVOKE SERVICE="{target}" VALIDATE-IN="$none" VALIDATE-OUT="$none">'
        f'<MAP MODE="INPUT">{"".join(input_ops)}</MAP></INVOKE>'
    )


def test_shipped_catalog_covers_the_production_list() -> None:
    missing = [name for name in PRODUCTION_NAMES if builtin_effect(name) is None]

    assert missing == []
    assert len(SHIPPED_SERVICES) > 650
    assert all(0 < len(effect.label) <= 120 for effect in SHIPPED_SERVICES.values())


@pytest.mark.parametrize(
    "name",
    [
        "pub.alert:emit",
        "pub.cache.admin:clearCache",
        "pub.db:query",
        "pub.jwt:verifyJWT",
        "pub.mime:createMimeData",
        "pub.mqtt:publish",
        "pub.parquet:write",
        "pub.remote.gd:submit",
        "pub.smime:processSignedData",
        "pub.soap.wsrm:createSequence",
        "pub.websocket:send",
        "pub.xmldata:xmlDataToXMLString",
        "pub.xslt.Transformations:transformSerialXML",
    ],
)
def test_catalog_covers_every_reference_folder(name: str) -> None:
    assert builtin_effect(name) is not None


def test_pub_db_query_is_a_database_effect(tmp_path: Path) -> None:
    _flow(
        tmp_path,
        "orders.legacy",
        "readOrders",
        _invoke("pub.db:query", _set("$dbAlias", "ordersDb"), _set("$dbTable", "ORDERS")),
    )
    analysis = analyze_path(tmp_path, load_config(None))

    facts = compute_service_facts(analysis, ExternalSystemCatalog())["orders.legacy:readOrders"]
    assert [(e.action, e.object, e.where) for e in facts.effects] == [
        (
            "selects rows from a database table",
            "table rows `ORDERS`",
            "database: $dbAlias `ordersDb`",
        )
    ]


def test_rest_client_call_becomes_a_data_effect(tmp_path: Path) -> None:
    _flow(
        tmp_path,
        "orders.api",
        "syncCrm",
        _invoke(
            "pub.client:restClient",
            _set("url", "https://crm.example/api/orders"),
            '<MAPCOPY FROM="/httpMethod;1;0" TO="/method;1;0"></MAPCOPY>',
        ),
    )
    analysis = analyze_path(tmp_path, load_config(None))

    effects = compute_service_facts(analysis, ExternalSystemCatalog())["orders.api:syncCrm"]
    assert [(e.action, e.object, e.where, e.known_from) for e in effects.effects] == [
        (
            "calls an external REST endpoint",
            "REST request",
            "HTTP: url `https://crm.example/api/orders`, method from `/httpMethod`",
            "literal and mapped from pipeline",
        )
    ]


def test_user_file_adds_and_overrides_entries(tmp_path: Path) -> None:
    extra = tmp_path / "platform-services.yml"
    extra.write_text(
        "services:\n"
        "  - name: pub.math:min\n"
        "    description: picks the lowest amount\n"
        "    family: NUMERIC\n"
        "  - name: pub.company.audit:write\n"
        "    description: writes an audit record\n"
        "    family: LOGGING\n",
        encoding="utf-8",
    )

    def label(name: str) -> str | None:
        effect = builtin_effect(name)
        return effect.label if effect is not None else None

    assert use_platform_catalog(extra) == 2
    assert label("pub.math:min") == "picks the lowest amount"
    assert label("pub.company.audit:write") == "writes an audit record"
    use_platform_catalog(None)
    assert label("pub.math:min") == "returns the smallest number in a list"
    assert label("pub.company.audit:write") is None


@pytest.mark.parametrize(
    ("content", "message"),
    [
        ("services: [\n", "not valid YAML"),
        ("other: 1\n", "`services:` list"),
        (
            "services:\n  - {name: orders.api:x, description: d, family: NUMERIC}\n",
            "not a platform service name",
        ),
        (
            "services:\n  - {name: pub.a:b, description: d, family: MAGIC}\n",
            "unknown family",
        ),
        (
            "services:\n  - {name: pub.a:b, description: d, family: REMOTE, data: {object: x}}\n",
            "needs an object and a system",
        ),
    ],
)
def test_bad_platform_files_fail_cleanly(tmp_path: Path, content: str, message: str) -> None:
    path = tmp_path / "bad.yml"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(PlatformServicesError, match=message):
        load_platform_services(path)


def test_cli_rejects_a_bad_platform_file(tmp_path: Path) -> None:
    _flow(tmp_path / "packages", "orders.api", "a", "")
    bad = tmp_path / "bad.yml"
    bad.write_text("services: nope\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["stats", str(tmp_path / "packages"), "--platform-services", str(bad)]
    )

    assert result.exit_code == 2
    assert "PLATFORM_SERVICES_INVALID" in result.output


def _server_with_gaps(root: Path) -> Path:
    _flow(
        root,
        "orders.api",
        "createOrder",
        _invoke("pub.math:min")
        + _invoke("pub.unknown.thing:run")
        + _invoke("legacy.adapter:lookup")
        + _invoke("missing.pkg:call"),
    )
    # A node with the called name but no svc_type: discovery cannot treat it as a service.
    node_dir = root / "Orders" / "ns" / "legacy" / "adapter" / "lookup"
    node_dir.mkdir(parents=True)
    (node_dir / "node.ndf").write_text(
        '<Values version="2.0"><value name="node_comment"></value></Values>', encoding="utf-8"
    )
    return root


def test_platform_page_lists_described_and_missing_services(tmp_path: Path) -> None:
    root = _server_with_gaps(tmp_path / "packages")
    out = tmp_path / "site"

    result = CliRunner().invoke(app, ["analyze", str(root), "--output", str(out)])

    assert result.exit_code == 0, result.output
    page = (out / "platform-services.md").read_text(encoding="utf-8")
    assert "| `pub.math:min` | returns the smallest number in a list | `NUMERIC` | 1 |" in page
    assert "## Without a description" in page
    assert "| `pub.unknown.thing:run` | 1 |" in page
    assert "(platform-services.md)" in (out / "index.md").read_text(encoding="utf-8")


def test_stats_lists_every_missing_name_and_why_calls_are_unresolved(tmp_path: Path) -> None:
    report = render_stats(analyze_path(_server_with_gaps(tmp_path), load_config(None)))

    assert "| `pub.unknown.thing:run` | 1 |" in report
    assert "more | |" not in report.split("## Calls leaving")[0]
    assert "## Why calls leave the analysed packages" in report
    assert "| `legacy.adapter` | 1 | 1 `unknown_namespace_artifact` | 0 |" in report
    assert "| `missing.pkg` | 1 | - | 1 |" in report
