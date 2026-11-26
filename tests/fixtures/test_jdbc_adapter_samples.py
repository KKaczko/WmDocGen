"""JDBC DynamicSQL and CustomSQL adapter services, from the real IS 10.15 samples to the outputs.

The samples (`samples/jdbcadapter/`, read-only) are copied into a temporary package next to
FLOW callers built with `flowxml`. Synthetic adapter documents are written with
`idata_binary.encode_idata`, in the confirmed layout only.
"""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

import pytest
from flowxml import FlowPackage, copy, extraction_config, invoke, loop, record, set_, string
from jdbc_samples import NAMESPACE, install_samples, property_blob, reference_json, sample_dirs

from wm_doc.adapters import SUPPORTED_TEMPLATES, decode_adapter_service
from wm_doc.analysis import analyze_path
from wm_doc.config import ExtractionMode, load_config
from wm_doc.describer import DescribeOptions, current_facts_hashes, describe_services
from wm_doc.effects import ADAPTER_SQL_KNOWN_FROM, call_inputs, compute_service_facts
from wm_doc.explorer.build import ExplorerOptions, build_bundle
from wm_doc.explorer.inputs import explorer_inputs
from wm_doc.explorer.write import render_data_files
from wm_doc.idata_binary import BinaryArray, BinaryDocument, Value, encode_idata
from wm_doc.ir import AdapterDecoding, AnalysisResult, FlowService, TextDisclosure
from wm_doc.jdbc_facts import adapter_findings, adapter_uses, use_findings
from wm_doc.ollama_provider import (
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.overviews import package_facts_text, summarize_packages
from wm_doc.pseudocode import MINIMAL_DETAIL, callee_adapters_lookup, render_pseudocode
from wm_doc.render.analysis_json import render_analysis_json
from wm_doc.render.artifact_markdown import render_artifact_inventory
from wm_doc.render.service_markdown import render_service_markdown
from wm_doc.service_docs import doc_path
from wm_doc.summarizer import fit_facts, unknown_names

DYNAMIC = f"{NAMESPACE}:dynamicSQL"
CUSTOM = f"{NAMESPACE}:customSQL"
CALLER = "kkaczk.api:findBySerials"
WRAPPER = "kkaczk.api:outer"
PACKAGE = "JdbcSamples"
# Values of the credential override settings in the samples: never kept anywhere.
CREDENTIAL_VALUES = ("overrideCredentials.$dbUser", "overrideCredentials.$dbPassword")
STRING = "java.lang.String"
MEM = "com.wm.data.ISMemDataImpl"
INTERPRETED = {
    "sql", "sqlFieldType", "sqlOutputField", "sqlVariables", "sqlInputFields",
    "sqlInputFieldTypes", "inputField", "inputFieldType", "inputJDBCType", "outputField",
    "outputFieldType", "outputJDBCType", "resultField", "resultFieldType", "maxRow",
    "queryTimeOut", "resultRowField", "resultRowFieldType",
}  # fmt: skip
CREDENTIAL_KEYS = {
    "userid", "useridType", "inputUseridSign", "password", "passwordType", "inputPasswordSign"
}  # fmt: skip


def _server(root: Path) -> Path:
    install_samples(root, PACKAGE)
    package = FlowPackage(root, PACKAGE)
    package.service(
        CALLER,
        loop(
            invoke(
                DYNAMIC,
                inputs=[
                    copy("/request/serials", "/dynamicSQLInput/IN_ARRAY"),
                    copy("/request/name", "/dynamicSQLInput/test1"),
                ],
            ),
            in_array="/batches",
        ),
        invoke(CUSTOM, inputs=[set_("/$connectionName", "other.db:Conn")]),
        inputs=[record("request", [string("serials"), string("name")])],
    )
    package.service(WRAPPER, invoke(CALLER))
    return root


def _analysis(root: Path, free_text: ExtractionMode | None = None) -> AnalysisResult:
    return analyze_path(root, extraction_config(free_text=free_text))


def _service(analysis: AnalysisResult, name: str) -> FlowService:
    return next(s for s in analysis.services if s.identity.full_name == name)


@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _server(tmp_path_factory.mktemp("jdbc") / "packages")


@pytest.fixture(scope="module")
def analysis(packages: Path) -> AnalysisResult:
    return _analysis(packages)


# --- decoding and normalization -------------------------------------------------------------


def test_sample_adapters_are_in_the_service_inventory(analysis: AnalysisResult) -> None:
    package = next(p for p in analysis.packages if p.name == PACKAGE)
    indexed = {summary.identity.full_name for summary in package.service_index}
    for name in (DYNAMIC, CUSTOM):
        service = _service(analysis, name)
        assert name in indexed
        assert service.source_service_type == "AdapterService"
        assert service.adapter is not None
        assert service.adapter.decoding is AdapterDecoding.DECODED
        assert service.adapter.jdbc is not None and service.adapter.jdbc.supported
        assert not [f for f in service.findings if f.code.startswith("ADAPTER_CONFIGURATION")]


@pytest.mark.parametrize("folder", sample_dirs(), ids=[f.name for f in sample_dirs()])
def test_normalized_configuration_follows_the_reference_document(
    analysis: AnalysisResult, folder: Path
) -> None:
    expected = reference_json(folder)
    assert isinstance(expected, dict)
    if expected.get("serviceTemplateName", "").rsplit(".", 1)[-1] not in SUPPORTED_TEMPLATES:
        pytest.skip("a template that is decoded but not interpreted")
    properties = expected["templateProperties"]
    service = _service(analysis, f"{NAMESPACE}:{folder.name}")
    details = service.adapter
    assert details is not None and details.jdbc is not None
    config = details.jdbc

    assert details.template == expected["serviceTemplateName"]
    assert details.adapter_type == expected["adapterType"]
    assert details.connection == expected["connectionName"]
    assert config.template_kind == expected["serviceTemplateName"].rsplit(".", 1)[-1]
    assert config.metadata_version == expected["metadataVersion"]
    assert config.node_version == expected["adapterServiceNodeVersion"]
    assert (config.input_record, config.output_record) == (
        expected["inputRecordName"],
        expected["outputRecordName"],
    )
    # The SQL exactly as configured (the default policy includes free text).
    assert config.sql is not None and config.sql.disclosure is TextDisclosure.INCLUDED
    assert config.sql.value == properties["sql"]
    # Parallel arrays keep their order and their pairing.
    assert [i.field for i in config.inputs] == properties["inputField"]
    assert [i.field_type for i in config.inputs] == properties["inputFieldType"]
    assert [i.jdbc_type for i in config.inputs] == properties["inputJDBCType"]
    assert [i.position for i in config.inputs] == list(range(1, len(config.inputs) + 1))
    assert [o.field for o in config.outputs] == properties["outputField"]
    assert [o.jdbc_type for o in config.outputs] == properties["outputJDBCType"]
    assert [o.result_field for o in config.outputs] == properties["resultField"]
    assert [o.result_type for o in config.outputs] == properties["resultFieldType"]
    assert [v.name for v in config.variables] == properties.get("sqlVariables", [])
    assert [v.field for v in config.variables] == properties.get("sqlInputFields", [])
    assert [v.field_type for v in config.variables] == properties.get("sqlInputFieldTypes", [])
    assert config.sql_output_field == properties.get("sqlOutputField")
    assert (config.max_rows, config.query_timeout) == (
        properties["maxRow"],
        properties["queryTimeOut"],
    )
    # Empty is kept apart from missing.
    assert config.result_row_field == "" and properties["resultRowField"] == ""
    # Every other property is named, never valued; credential settings are not even named.
    assert set(config.uninterpreted) == set(properties) - INTERPRETED - CREDENTIAL_KEYS
    assert config.issues == []


def test_the_sql_is_read_into_tables_binds_and_substitutions(analysis: AnalysisResult) -> None:
    dynamic = _service(analysis, DYNAMIC).adapter
    custom = _service(analysis, CUSTOM).adapter
    assert dynamic is not None and dynamic.jdbc is not None
    assert custom is not None and custom.jdbc is not None
    dynamic_sql = dynamic.jdbc.sql_analysis
    custom_sql = custom.jdbc.sql_analysis
    assert dynamic_sql is not None and custom_sql is not None

    assert [(o.name, o.access) for o in dynamic_sql.objects] == [("TEST", "read")]
    assert [(b.position, b.column) for b in dynamic_sql.binds] == [
        (1, "t.name"),
        (2, "t.quantity"),
    ]
    assert [(p.name, p.contexts, p.column) for p in dynamic_sql.placeholders] == [
        ("IN_ARRAY", ["value list"], "t.id")
    ]
    assert [(b.position, b.column) for b in custom_sql.binds] == [(1, "t.name"), (2, "t.desc")]
    assert custom_sql.placeholders == []
    # As many `?` as configured bind inputs, in both samples.
    assert len(dynamic_sql.binds) == len(dynamic.jdbc.inputs) == 2
    assert len(custom_sql.binds) == len(custom.jdbc.inputs) == 2


def test_credentials_never_reach_any_output(analysis: AnalysisResult) -> None:
    payload = render_analysis_json(analysis)
    facts = compute_service_facts(analysis)
    pages = [
        render_service_markdown(service, facts=facts[service.identity.full_name])
        for service in analysis.services
    ]
    prompts = [
        render_pseudocode(_service(analysis, name), lambda _: None) for name in (DYNAMIC, CUSTOM)
    ]
    for text in [payload, *pages, *prompts, render_artifact_inventory(analysis)]:
        for value in CREDENTIAL_VALUES:
            assert value not in text
        assert "inputPasswordSign" not in text and "useridType" not in text


def test_the_decoder_alone_keeps_no_sql_text_and_no_credentials() -> None:
    for folder in sample_dirs():
        details = decode_adapter_service(property_blob(folder))
        dumped = details.model_dump_json()
        for value in CREDENTIAL_VALUES:
            assert value not in dumped
        # Without the analysis's policy callback the SQL text is not kept.
        assert details.jdbc is not None and details.jdbc.sql is not None
        assert details.jdbc.sql.value is None


# --- disclosure ------------------------------------------------------------------------------


@pytest.mark.parametrize("mode", [ExtractionMode.REDACT, ExtractionMode.OMIT])
def test_the_sql_text_follows_the_free_text_policy(packages: Path, mode: ExtractionMode) -> None:
    analysis = _analysis(packages, free_text=mode)
    service = _service(analysis, DYNAMIC)
    assert service.adapter is not None and service.adapter.jdbc is not None
    config = service.adapter.jdbc
    assert config.sql is not None and config.sql.value is None
    # The structure is still read: only identifiers are kept.
    assert config.sql_analysis is not None and config.sql_analysis.objects
    sql = "Select * from TEST t Where t.id IN"
    page = render_service_markdown(service, facts=compute_service_facts(analysis)[DYNAMIC])
    prompt = render_pseudocode(service, lambda _: None)
    assert sql not in render_analysis_json(analysis) and sql not in page and sql not in prompt
    assert "withheld" in page and "withheld" in prompt


def _write_adapter(folder: Path, blob: str) -> None:
    folder.mkdir(parents=True)
    (folder / "node.ndf").write_text(
        '<Values version="2.0">\n'
        '  <value name="svc_type">AdapterService</value>\n'
        '  <record name="svc_sig">\n'
        '    <record name="sig_in"><array name="rec_fields" type="record" depth="1"/></record>\n'
        '    <record name="sig_out"><array name="rec_fields" type="record" depth="1"/></record>\n'
        "  </record>\n"
        f'  <value name="IRTNODE_PROPERTY">{blob}</value>\n'
        "</Values>",
        encoding="utf-8",
    )


def _adapter_node(
    root: Path, full_name: str, document: BinaryDocument, long_lengths: str | None = None
) -> None:
    namespace, _, name = full_name.partition(":")
    folder = root / PACKAGE / "ns" / Path(*namespace.split(".")) / name
    raw = encode_idata(document, long_lengths=long_lengths)
    _write_adapter(folder, base64.b64encode(raw).decode("ascii"))


def _strings(*items: str) -> BinaryArray:
    return BinaryArray(STRING, items)


def _custom_sql(
    sql: str, inputs: tuple[str, ...] = (), types: tuple[str, ...] | None = None
) -> BinaryDocument:
    entries: tuple[tuple[str, Value], ...] = (
        ("sql", sql),
        ("inputField", _strings(*inputs)),
        ("inputFieldType", _strings(*(types if types is not None else [STRING] * len(inputs)))),
        ("inputJDBCType", _strings(*["VARCHAR"] * len(inputs))),
        ("outputField", _strings()),
        ("password", "s3cret-Pa55"),
    )
    return BinaryDocument(
        MEM,
        (
            ("serviceTemplateName", "com.wm.adapter.wmjdbc.services.CustomSQL"),
            ("metadataVersion", 0),
            ("connectionName", "orders.db:conn"),
            ("templateProperties", BinaryDocument(MEM, entries)),
            ("adapterServiceNodeVersion", 2),
            ("adapterType", "JDBCAdapter"),
        ),
    )


def test_secret_looking_sql_is_withheld_but_still_read(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    sql = "SELECT id FROM users WHERE password = 'hunter2' AND name = ?"
    _adapter_node(root, "orders.db:login", _custom_sql(sql, ("n",)))
    service = _service(_analysis(root), "orders.db:login")
    assert service.adapter is not None and service.adapter.jdbc is not None
    config = service.adapter.jdbc
    assert config.sql is not None and config.sql.disclosure is TextDisclosure.BLOCKED_SECRET
    assert config.sql_analysis is not None
    assert [o.name for o in config.sql_analysis.objects] == ["users"]
    dumped = service.model_dump_json()
    assert "hunter2" not in dumped and "s3cret-Pa55" not in dumped


# --- unsupported structures and templates ---------------------------------------------------


def _text(value: str) -> bytes:
    return bytes([0x04, len(value)]) + value.encode("utf-16-be")


def _long_sql_value(length: bytes, body: bytes) -> bytes:
    return (
        bytes([0x0B, 0x04, 0, 0, 0, 1, 0x05, 0x01])
        + _text(MEM)
        + _text("serviceTemplateName")
        + _text("com.wm.adapter.wmjdbc.services.CustomSQL")
        + _text("connectionName")
        + _text("orders.db:conn")
        + _text("adapterType")
        + _text("JDBCAdapter")
        + _text("templateProperties")
        + bytes([0x05, 0x01, 0x00, 0x02])
        + _text("sql")
        + bytes([0x04])
        + length
        + body
        + bytes([0x02, 0x00, 0x02, 0x00])
    )


def test_a_long_sql_read_by_an_unconfirmed_encoding_is_marked(tmp_path: Path) -> None:
    # 200 characters: `81 48` is 200 only as a big-endian 7-bit varint; every other reading
    # runs out of bytes or out of step, so that one is used, and the service says so.
    sql = "SELECT * FROM t WHERE x = ? " + "-" * 172
    raw = _long_sql_value(bytes([0x81, 0x48]), sql.encode("utf-16-be"))
    root = tmp_path / "packages"
    folder = root / PACKAGE / "ns" / "orders" / "db" / "longSql"
    _write_adapter(folder, base64.b64encode(raw).decode("ascii"))

    service = _service(_analysis(root), "orders.db:longSql")
    details = service.adapter
    assert details is not None and details.jdbc is not None
    assert details.decoding is AdapterDecoding.DECODED
    assert details.decode_hypotheses == ["length:vlq"]
    assert details.jdbc.sql is not None and details.jdbc.sql.value == sql
    [finding] = [f for f in service.findings if f.code == "ADAPTER_LONG_ENCODING_UNCONFIRMED"]
    assert "length:vlq" in finding.message
    assert "**Unconfirmed reading.**" in render_service_markdown(service)


def test_an_unsupported_structure_falls_back_to_the_identity_fields(tmp_path: Path) -> None:
    # An unknown type tag (0x07) where a value belongs: no reading lifts that.
    raw = (
        bytes([0x0B, 0x04, 0, 0, 0, 1, 0x05, 0x01])
        + _text(MEM)
        + _text("serviceTemplateName")
        + _text("com.wm.adapter.wmjdbc.services.CustomSQL")
        + _text("connectionName")
        + _text("orders.db:conn")
        + _text("adapterType")
        + _text("JDBCAdapter")
        + _text("templateProperties")
        + bytes([0x05, 0x01, 0x00, 0x02])
        + _text("sql")
        + bytes([0x07, 0x01])
        + bytes([0x02, 0x00, 0x02, 0x00])
    )
    root = tmp_path / "packages"
    folder = root / PACKAGE / "ns" / "orders" / "db" / "longSql"
    _write_adapter(folder, base64.b64encode(raw).decode("ascii"))

    service = _service(_analysis(root), "orders.db:longSql")
    details = service.adapter
    assert details is not None
    assert details.decoding is AdapterDecoding.PARTIAL
    assert details.decode_problem is not None and "unsupported_tag" in details.decode_problem
    assert details.operation == "CustomSQL" and details.connection == "orders.db:conn"
    assert details.jdbc is None
    [finding] = [f for f in service.findings if f.code == "ADAPTER_CONFIGURATION_PARTIALLY_DECODED"]
    assert "unsupported_tag" in finding.message
    assert finding.source is not None and finding.source.path.endswith("node.ndf")
    assert "does not support" in render_service_markdown(service)


def test_unverified_templates_keep_the_identity_and_name_their_properties(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    properties = BinaryDocument(
        MEM,
        (
            ("tables.tableName", _strings("ORDERS")),
            ("tables.schemaName", _strings("SALES")),
            ("columnNames", _strings("ID")),
            ("password", "s3cret-Pa55"),
        ),
    )
    document = BinaryDocument(
        MEM,
        (
            ("serviceTemplateName", "com.wm.adapter.wmjdbc.services.Select"),
            ("connectionName", "orders.db:conn"),
            ("templateProperties", properties),
            ("adapterType", "JDBCAdapter"),
        ),
    )
    _adapter_node(root, "orders.db:selectOrders", document)
    service = _service(_analysis(root), "orders.db:selectOrders")
    details = service.adapter
    assert details is not None and details.jdbc is not None
    assert details.decoding is AdapterDecoding.DECODED
    assert details.tables == ["SALES.ORDERS"]
    assert not details.jdbc.supported and details.jdbc.sql is None
    assert details.jdbc.uninterpreted == ["columnNames", "tables.schemaName", "tables.tableName"]
    assert "s3cret" not in service.model_dump_json()


def test_parallel_arrays_of_different_lengths_are_reported(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    sql = "SELECT * FROM t WHERE a = ? AND b = ?"
    _adapter_node(root, "orders.db:uneven", _custom_sql(sql, ("a", "b"), (STRING,)))
    service = _service(_analysis(root), "orders.db:uneven")
    assert service.adapter is not None and service.adapter.jdbc is not None
    config = service.adapter.jdbc
    assert [(i.field, i.field_type) for i in config.inputs] == [("a", STRING), ("b", None)]
    assert any("different lengths" in issue for issue in config.issues)
    assert any(f.code == "ADAPTER_CONFIGURATION_ISSUES" for f in service.findings)


def test_a_bind_count_mismatch_is_a_finding(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    sql = "SELECT * FROM t WHERE a = ? AND b = ? AND c = ?"
    _adapter_node(root, "orders.db:mismatch", _custom_sql(sql, ("a", "b")))
    codes = [f.code for f in adapter_findings(_service(_analysis(root), "orders.db:mismatch"))]
    assert "bind-count-mismatch" in codes


def test_signature_inputs_the_sql_does_not_bind_are_a_finding(analysis: AnalysisResult) -> None:
    findings = adapter_findings(_service(analysis, CUSTOM))
    [unbound] = [f for f in findings if f.code == "unbound-signature-inputs"]
    assert unbound.kind == "inferred" and "`offset`" in unbound.text and "`limit`" in unbound.text


def test_pagination_without_order_and_unbounded_selects_are_risks(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    paged = "SELECT * FROM t WHERE a = ? OFFSET 10 ROWS FETCH FIRST 5 ROWS ONLY"
    _adapter_node(root, "orders.db:page", _custom_sql(paged, ("a",)))
    _adapter_node(root, "orders.db:all", _custom_sql("SELECT * FROM t"))
    analysis = _analysis(root)
    page = {f.code: f.kind for f in adapter_findings(_service(analysis, "orders.db:page"))}
    every = {f.code: f.kind for f in adapter_findings(_service(analysis, "orders.db:all"))}
    assert page["pagination-without-order"] == "risk"
    assert every["unbounded-query"] == "risk"
    assert "unbounded-query" not in page


# --- callers, Stage 7 and outputs ------------------------------------------------------------


def test_dynamic_sql_risks_are_potential_never_confirmed(analysis: AnalysisResult) -> None:
    findings = {f.code: f for f in adapter_findings(_service(analysis, DYNAMIC))}
    assert findings["text-substitution"].kind == "inferred"
    risk = findings["sql-injection-exposure"]
    assert risk.kind == "risk" and "Potential" in risk.text and "Not confirmed" in risk.text
    assert findings["connection-override"].kind == "fact"
    assert findings["statement-output"].kind == "fact"


def test_callers_inherit_the_database_effects_with_their_path(analysis: AnalysisResult) -> None:
    facts = compute_service_facts(analysis)
    direct = [e for e in facts[CALLER].effects if e.known_from == ADAPTER_SQL_KNOWN_FROM]
    assert {(e.object, e.via) for e in direct} == {
        ("table `TEST`", (DYNAMIC,)),
        ("table `TEST`", (CUSTOM,)),
    }
    assert all("inea.configuration.jdbc:UtilsConnection" in e.where for e in direct)
    transitive = [e for e in facts[WRAPPER].effects if e.known_from == ADAPTER_SQL_KNOWN_FROM]
    assert {e.via for e in transitive} == {(CALLER, DYNAMIC), (CALLER, CUSTOM)}
    own = [e for e in facts[DYNAMIC].effects if e.known_from == ADAPTER_SQL_KNOWN_FROM]
    assert [(e.object, e.action, e.via) for e in own] == [
        ("table `TEST`", "reads (SELECT in DynamicSQL)", ())
    ]


def test_caller_facts_show_loops_substitutions_and_connection_overrides(
    analysis: AnalysisResult,
) -> None:
    facts = compute_service_facts(analysis)
    assert facts[CALLER].database_calls == (
        f"`{CUSTOM}` its call: not inside a loop; $connectionName (connection override): "
        "`other.db:Conn`",
        f"`{DYNAMIC}` its call: inside LOOP over `/batches`; dynamicSQLInput/IN_ARRAY "
        "(substitution): from `/request/serials`; $connectionName (connection override): "
        "not set in its input map",
    )
    assert "JDBC adapter calls (direct):" in facts[CALLER].text()
    assert facts[WRAPPER].database_calls == ()

    callers = [_service(analysis, CALLER)]
    uses, hidden = adapter_uses(_service(analysis, DYNAMIC), callers, call_inputs)
    assert hidden == 0
    assert {f.code: f.kind for f in use_findings(uses)} == {
        "query-in-loop": "risk",
        "substitution-mapped": "inferred",
    }
    uses, _ = adapter_uses(_service(analysis, CUSTOM), callers, call_inputs)
    assert {f.code for f in use_findings(uses)} == {"connection-overridden"}


def test_pages_show_the_configuration_and_the_callers(analysis: AnalysisResult) -> None:
    facts = compute_service_facts(analysis)
    services = {s.identity.full_name: s for s in analysis.services}
    incoming = [
        dependency
        for service in analysis.services
        for dependency in service.unique_dependencies
        if dependency.target_service == DYNAMIC
    ]
    page = render_service_markdown(
        services[DYNAMIC], facts=facts[DYNAMIC], incoming_dependencies=incoming, analysed=services
    )
    for heading in ("## Input Signature", "## Called By", "## Processes", "### SQL template"):
        assert heading in page
    assert "Select * from TEST t Where t.id IN (${IN_ARRAY}) AND t.name = ? AND" in page
    assert "| 1 | `test1` | `java.lang.String` | `VARCHAR` | = `t.name` |" in page
    assert "| `${IN_ARRAY}` | `IN_ARRAY` | `java.lang.String` | value list for `t.id` |" in page
    assert "**potential risk**: Potential SQL injection exposure" in page
    assert f"`{CALLER}` (its call): inside LOOP over `/batches`" in page
    caller_page = render_service_markdown(services[CALLER], facts=facts[CALLER])
    assert "JDBC adapter calls (direct; from each call's input map):" in caller_page
    inventory = render_artifact_inventory(analysis)
    assert "reading table `TEST`" in inventory and "| decoded |" in inventory


def test_tables_written_by_two_adapter_services_are_listed(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    _adapter_node(root, "orders.db:a", _custom_sql("INSERT INTO s.t (x) VALUES (?)", ("x",)))
    _adapter_node(root, "orders.db:b", _custom_sql("DELETE FROM S.T WHERE x = ?", ("x",)))
    inventory = render_artifact_inventory(_analysis(root))
    assert "### Tables written by more than one adapter service" in inventory
    assert "| `S.T` |" in inventory


def test_the_prompt_carries_the_sql_parameters_and_findings(analysis: AnalysisResult) -> None:
    prompt = render_pseudocode(_service(analysis, DYNAMIC), lambda _: None)
    assert "    <<<SQL" in prompt and "    SQL>>>" in prompt
    assert "Select * from TEST t Where t.id IN (${IN_ARRAY})" in prompt
    assert (
        "bind parameter 1 (`?`): input `test1` (java.lang.String, VARCHAR) -> = `t.name`"
    ) in prompt
    assert "text substitution `${IN_ARRAY}`: input `IN_ARRAY`" in prompt
    assert "[potential risk] Potential SQL injection exposure" in prompt
    assert "technical output: `SQLStatement`" in prompt


class _Provider:
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
            "purpose": "Reads rows of `TEST` by `t.name` and `t.quantity`.",
            "usage": "Used by the callers listed in the facts.",
            "data_effects": "Reads `TEST` rows whose `t.id` is in `IN_ARRAY`.",
            "steps": ["Opens a cursor."],
            "error_handling": "Retries on deadlock.",
            "designer_comment": "Reads TEST rows.",
        }
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )


def test_describe_explains_the_sql_and_writes_the_steps_itself(
    packages: Path, analysis: AnalysisResult, tmp_path: Path
) -> None:
    provider = _Provider()
    options = DescribeOptions(
        model="fake-model",
        scan_root=packages,
        config=load_config(None),
        docs_dir=tmp_path / "service-docs",
        cache_dir=tmp_path / "cache",
    )
    describe_services(analysis, [DYNAMIC], provider, options)

    assert "Read the SQL template and explain the business rules" in provider.prompts[0]
    assert "Select * from TEST t Where t.id IN (${IN_ARRAY})" in provider.prompts[0]
    text = doc_path(tmp_path / "service-docs", PACKAGE, DYNAMIC).read_text(encoding="utf-8")
    assert "Replaces `${IN_ARRAY}` in the SQL text with the text of `IN_ARRAY`" in text
    assert "Binds `test1` to `?` 1 (= `t.name`), `test2` to `?` 2 (= `t.quantity`)." in text
    assert "Returns the statement as run in `SQLStatement`." in text
    assert "cursor" not in text and "deadlock" not in text
    assert "### JDBC configuration" in text


def test_a_changed_adapter_changes_the_facts_hash_of_its_callers(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    _adapter_node(root, "orders.db:read", _custom_sql("SELECT * FROM a WHERE x = ?", ("x",)))
    package = FlowPackage(root, PACKAGE)
    package.service("orders.api:get", invoke("orders.db:read"))
    package.service("orders.api:other", invoke("orders.api:none"))
    config = load_config(None)
    before = current_facts_hashes(_analysis(root), root, config)

    shutil.rmtree(root / PACKAGE / "ns" / "orders" / "db" / "read")
    _adapter_node(root, "orders.db:read", _custom_sql("SELECT * FROM b WHERE x = ?", ("x",)))
    after = current_facts_hashes(_analysis(root), root, config)

    assert before["orders.db:read"] != after["orders.db:read"]
    assert before["orders.api:get"] != after["orders.api:get"]
    assert before["orders.api:other"] == after["orders.api:other"]


def test_the_explorer_shows_the_sql_but_never_credentials(
    packages: Path, analysis: AnalysisResult
) -> None:
    inputs = explorer_inputs(analysis, packages, load_config(None))
    files = render_data_files(build_bundle(inputs, ExplorerOptions()))
    search = json.loads(files["search.json"])
    identifier = next(s["id"] for s in search["services"] if s["name"] == DYNAMIC)
    adapter = json.loads(files[f"services/{identifier}.json"])["adapter"]
    assert adapter["tables"] == ["TEST"] and adapter["operation"] == "DynamicSQL"
    assert adapter["jdbc"]["sql"].startswith("Select * from TEST t Where t.id IN (${IN_ARRAY})")
    assert [b["column"] for b in adapter["jdbc"]["binds"]] == ["t.name", "t.quantity"]
    everything = b"".join(files.values()).decode("utf-8")
    for value in CREDENTIAL_VALUES:
        assert value not in everything
    excluded = render_data_files(build_bundle(inputs, ExplorerOptions(sql="excluded")))
    assert "Select * from TEST" not in b"".join(excluded.values()).decode("utf-8")


def test_the_explorer_withholds_sql_the_analysis_withheld(packages: Path) -> None:
    analysis = _analysis(packages, free_text=ExtractionMode.REDACT)
    files = render_data_files(
        build_bundle(explorer_inputs(analysis, packages, load_config(None)), ExplorerOptions())
    )
    assert "Select * from TEST" not in b"".join(files.values()).decode("utf-8")
    manifest = json.loads(files["manifest.json"])
    assert manifest["disclosure"]["withheldStrings"] >= 2


# --- AI context ------------------------------------------------------------------------------


def test_callers_prompts_carry_the_statement_and_what_feeds_it(analysis: AnalysisResult) -> None:
    services = {s.identity.full_name: s for s in analysis.services}
    adapters = callee_adapters_lookup(services)
    prompt = render_pseudocode(services[CALLER], lambda _: None, callee_adapters=adapters)
    assert "jdbc: DynamicSQL runs SELECT reading table `TEST`" in prompt
    assert "bind ?1 (= `t.name`): input `dynamicSQLInput/test1` <- from `/request/name`" in prompt
    assert (
        "bind ?2 (= `t.quantity`): input `dynamicSQLInput/test2` <- not set in this call's "
        "input map"
    ) in prompt
    assert (
        "text substitution `${IN_ARRAY}` (value list for `t.id`): input "
        "`dynamicSQLInput/IN_ARRAY` <- from `/request/serials`"
    ) in prompt
    assert "Select * from TEST t Where t.id IN (${IN_ARRAY})" in prompt
    # Smaller prompts keep the statement and drop the callee's SQL text.
    small = render_pseudocode(
        services[CALLER], lambda _: None, callee_adapters=adapters, detail=MINIMAL_DETAIL
    )
    assert "jdbc: DynamicSQL runs SELECT" in small and "<<<SQL" not in small
    # Names from the SQL are facts the model may use.
    answer = "Reads `TEST` rows by `t.name`, `t.quantity` and `t.id` from `/request/serials`."
    assert unknown_names(answer, prompt) == []
    # A service that calls no adapter is rendered as before.
    assert render_pseudocode(
        services[WRAPPER], lambda _: None, callee_adapters=adapters
    ) == render_pseudocode(services[WRAPPER], lambda _: None)


def test_a_long_sql_is_fitted_to_the_context_window(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    sql = "SELECT id FROM t WHERE x = ? AND note <> 'a'\n" + "  AND y > 0\n" * 900
    _adapter_node(root, "orders.db:long", _custom_sql(sql, ("x",)), long_lengths="vlq")
    service = _service(_analysis(root), "orders.db:long")
    assert service.adapter is not None and service.adapter.decode_hypotheses == ["length:vlq"]

    roomy, shortened = fit_facts(service, lambda _: None, {}, 65536)
    assert not shortened and "(cut to fit" not in roomy and roomy.count("AND y > 0") == 900
    tight, shortened = fit_facts(service, lambda _: None, {}, 4096)
    assert shortened and "(cut to fit the context window:" in tight
    assert "<<<SQL" in tight and "SQL>>>" in tight


def test_a_changed_where_clause_changes_the_callers_facts_hash(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    _adapter_node(root, "orders.db:read", _custom_sql("SELECT * FROM a WHERE x = ?", ("x",)))
    FlowPackage(root, PACKAGE).service("orders.api:get", invoke("orders.db:read"))
    config = load_config(None)
    before = current_facts_hashes(_analysis(root), root, config)
    shutil.rmtree(root / PACKAGE / "ns" / "orders" / "db" / "read")
    # Same table, other column: only the SQL tells them apart.
    _adapter_node(root, "orders.db:read", _custom_sql("SELECT * FROM a WHERE y = ?", ("x",)))
    after = current_facts_hashes(_analysis(root), root, config)
    assert before["orders.api:get"] != after["orders.api:get"]


def test_package_overviews_list_each_adapter_statement(analysis: AnalysisResult) -> None:
    summary = summarize_packages(analysis, compute_service_facts(analysis))[PACKAGE]
    text = package_facts_text(summary)
    assert "JDBC adapter statements (from their SQL templates):" in text
    assert (
        f"  {DYNAMIC} (DynamicSQL): SELECT reading table `TEST`; binds `t.name`, "
        "`t.quantity`; substitutes `${IN_ARRAY}`"
    ) in text
    assert f"  {CUSTOM} (CustomSQL): SELECT reading table `TEST`; binds `t.name`, `t.desc`" in text
