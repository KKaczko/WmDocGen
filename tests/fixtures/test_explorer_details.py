"""M13 explorer PoC, PR 2: descriptions, data effects, entry points, adapters and trust."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.describer import collect_states, current_facts_hashes
from wm_doc.effects import compute_service_facts
from wm_doc.explorer.build import LITERAL_PLACEHOLDER, ExplorerOptions, build_bundle
from wm_doc.explorer.inputs import explorer_inputs
from wm_doc.explorer.synthetic import (
    FAKE_SECRETS,
    HOSTILE_VISIBLE,
    NOTES_MARKER,
    write_demo_descriptions,
    write_demo_packages,
)
from wm_doc.explorer.text import TextGuard, narrative_blocks
from wm_doc.explorer.write import render_data_files
from wm_doc.ir import AnalysisResult
from wm_doc.render.service_markdown import render_service_markdown

STATE_NAMES = {
    "approved": "approved",
    "approved, facts changed": "stale",
    "draft": "draft",
    "edited": "edited",
    "missing": "none",
}


@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synthetic-details") / "packages"
    write_demo_packages(root, filler_services=10)
    return root


@pytest.fixture(scope="module")
def analysis(packages: Path) -> AnalysisResult:
    return analyze_path(packages, load_config(None), None, processes_file_explicit=False)


@pytest.fixture(scope="module")
def docs_dir(
    packages: Path, analysis: AnalysisResult, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    docs = tmp_path_factory.mktemp("synthetic-docs")
    assert write_demo_descriptions(docs, analysis, packages, load_config(None)) == 7
    return docs


def _build(
    packages: Path, analysis: AnalysisResult, docs_dir: Path, shown: str = "all"
) -> dict[str, bytes]:
    inputs = explorer_inputs(analysis, packages, load_config(None), docs_dir=docs_dir)
    options = ExplorerOptions(dataset_kind="synthetic", descriptions=shown)  # type: ignore[arg-type]
    return render_data_files(build_bundle(inputs, options))


@pytest.fixture(scope="module")
def built(packages: Path, analysis: AnalysisResult, docs_dir: Path) -> dict[str, bytes]:
    return _build(packages, analysis, docs_dir)


def _search(files: dict[str, bytes]) -> dict[str, Any]:
    search: dict[str, Any] = json.loads(files["search.json"])
    return search


def _detail(files: dict[str, bytes], name: str) -> dict[str, Any]:
    identifier = next(s["id"] for s in _search(files)["services"] if s["name"] == name)
    detail: dict[str, Any] = json.loads(files[f"services/{identifier}.json"])
    return detail


def _text(segments: list[dict[str, Any]]) -> str:
    return "".join(s["text"] if s["kind"] == "text" else s["code"] for s in segments)


# --- descriptions -------------------------------------------------------------------------


def test_review_states_are_the_ones_status_reports(
    packages: Path, analysis: AnalysisResult, docs_dir: Path, built: dict[str, bytes]
) -> None:
    facts = compute_service_facts(analysis)
    hashes = current_facts_hashes(analysis, packages, load_config(None), facts=facts)
    status = {
        name: STATE_NAMES[state.value]
        for name, (_, state) in collect_states(analysis, docs_dir, hashes).items()
    }
    shown = {item["name"]: item["description"] for item in _search(built)["services"]}

    assert shown == status
    assert {state for state in shown.values()} == {
        "approved",
        "stale",
        "draft",
        "edited",
        "none",
    }


def test_descriptions_option_hides_unreviewed_text(
    packages: Path, analysis: AnalysisResult, docs_dir: Path
) -> None:
    approved = _build(packages, analysis, docs_dir, "approved")
    states = {item["name"]: item["description"] for item in _search(approved)["services"]}
    assert states["orders.api:getOrder"] == "stale"
    assert states["orders.api:validateOrder"] == "none"
    assert _detail(approved, "orders.api:validateOrder")["description"] is None

    none = _build(packages, analysis, docs_dir, "none")
    assert all(item["description"] == "none" for item in _search(none)["services"])
    assert b"Creates an order from a REST request" not in b"".join(none.values())


def test_description_sections_are_plain_segments_linking_exact_names(
    built: dict[str, bytes],
) -> None:
    detail = _detail(built, "orders.api:createOrder")
    description = detail["description"]
    sections = {section["key"]: section for section in description["sections"]}
    insert_id = _detail(built, "orders.db:insertOrder")["id"]

    assert description["state"] == "approved"
    assert description["model"] == "synthetic-demo-model"
    assert list(sections) == [
        "purpose",
        "usage",
        "dataEffects",
        "mainSteps",
        "detailedFlow",
        "errorHandling",
    ]
    purpose = sections["purpose"]["paragraphs"][0]
    assert {"kind": "code", "code": "orders.db:insertOrder", "ref": insert_id} in purpose
    data = sections["dataEffects"]["paragraphs"][0]
    assert {"kind": "code", "code": "billing.api:postInvoice", "ref": None} in data
    assert len(sections["mainSteps"]["items"]) == 5
    unverified = _detail(built, "customers.api:getCustomer")["description"]
    assert unverified["unverifiedNames"] == ["crm.legacy:findCustomer"]


def test_hostile_text_is_inert_or_withheld(built: dict[str, bytes]) -> None:
    description = _detail(built, "customers.api:updateCustomer")["description"]
    texts = [
        _text(block)
        for section in description["sections"]
        for block in [*section["paragraphs"], *section["items"]]
    ]
    joined = " | ".join(texts)

    for visible in HOSTILE_VISIBLE:
        assert visible in joined  # shown, as text
    assert "[withheld: raw HTML]" in texts
    assert "[withheld: secret-like key/value]" in texts
    assert "[withheld: unsafe Markdown link]" in texts
    everything = b"".join(built.values()).decode("utf-8")
    assert "<img" not in everything and "hunter2" not in everything
    assert chr(0x202E) not in everything
    manifest = json.loads(built["manifest.json"])
    assert manifest["disclosure"]["withheldStrings"] >= 3


def test_comments_notes_secrets_and_literals_never_leave_the_tool(
    built: dict[str, bytes],
) -> None:
    everything = b"".join(built.values()).decode("utf-8")

    assert NOTES_MARKER not in everything
    assert "Demo comment" not in everything  # the Designer comment section
    assert "wm-doc:facts" not in everything and "### Used by" not in everything
    for secret in FAKE_SECRETS:
        assert secret not in everything, secret


# --- facts --------------------------------------------------------------------------------


def test_literal_values_in_effects_are_masked(built: dict[str, bytes]) -> None:
    effects = _detail(built, "orders.api:createOrder")["effects"]
    http = next(e for e in effects if e["action"] == "calls an external HTTP endpoint")

    assert http["knownFrom"] == "literal"
    assert _text(http["where"]) == (
        f"HTTP: url {LITERAL_PLACEHOLDER}, method {LITERAL_PLACEHOLDER}"
    )


def test_entry_points_and_effects_link_analysed_services(built: dict[str, bytes]) -> None:
    detail = _detail(built, "orders.api:createOrder")
    entry = detail["entryPoints"][0]
    post_id = _detail(built, "orders.rest.order:_post")["id"]

    assert entry["kind"] == "REST v1 handler"
    assert _text(entry["name"]) == "HTTP POST /rest/orders/rest/order"
    assert entry["path"][0] == {"name": "orders.rest.order:_post", "id": post_id}
    inserts = next(e for e in detail["effects"] if e["action"] == "inserts rows into")
    assert inserts["via"] == [
        {"name": "orders.db:insertOrder", "id": _detail(built, "orders.db:insertOrder")["id"]}
    ]
    cancel = _detail(built, "orders.api:cancelOrder")["entryPoints"]
    assert [e["kind"] for e in cancel] == ["JMS trigger"]
    documents = detail["documents"]
    assert {"name": "orders.docs:Order", "role": "input", "resolved": True} in documents


def test_adapter_configuration_is_the_allow_listed_one(built: dict[str, bytes]) -> None:
    adapter = _detail(built, "orders.db:insertOrder")["adapter"]

    assert adapter == {
        "adapterType": "JDBCAdapter",
        "connection": "orders.db:conn",
        "databaseName": "ORDERS",
        "databaseProduct": "Oracle",
        "operation": "Insert",
        "tables": ["ORDERS", "ORDER_LINES"],
        "template": "com.wm.adapter.wmjdbc.services.Insert",
        "transactionType": "LOCAL_TRANSACTION",
    }
    assert _detail(built, "orders.api:createOrder")["adapter"] is None


@pytest.mark.parametrize(
    "name",
    [
        "orders.api:createOrder",
        "orders.api:getOrder",
        "orders.api:cancelOrder",
        "orders.db:insertOrder",
        "customers.api:getCustomer",
    ],
)
def test_explorer_facts_match_the_markdown_service_page(
    analysis: AnalysisResult, built: dict[str, bytes], name: str
) -> None:
    facts = compute_service_facts(analysis)
    service = next(s for s in analysis.services if s.identity.full_name == name)
    page = render_service_markdown(service, facts=facts[name])
    detail = _detail(built, name)

    for effect in detail["effects"]:
        assert effect["action"] in page.replace("`", "")
        assert effect["knownFrom"] in page
    for entry in detail["entryPoints"]:
        assert entry["kind"] in page
        assert _text(entry["name"]) in page.replace("`", "")
    assert len(detail["effects"]) == len(facts[name].effects)
    assert detail["callersTotal"] == len(facts[name].callers)


# --- text helpers -------------------------------------------------------------------------


def test_narrative_blocks_keep_known_sections_only() -> None:
    narrative = (
        "## Purpose\n\nDoes a thing.\nOn two lines.\n\n## Main steps\n\n1. First\n   more\n"
        "2. Second\n\n## Designer comment\n\n```text\nsecret stuff\n```\n\n## Mine\n\nextra\n"
    )
    assert narrative_blocks(narrative) == [
        ("purpose", ["Does a thing. On two lines."], []),
        ("mainSteps", [], ["First more", "Second"]),
    ]


def test_segments_split_code_spans_and_unescape_markdown() -> None:
    guard = TextGuard()
    refs = {"a.b:c": "0123456789abcdef"}
    segments = guard.segments("\\- calls `a.b:c` then `x`", refs, prose=True)
    assert [s.model_dump() for s in segments] == [
        {"kind": "text", "text": "- calls "},
        {"kind": "code", "code": "a.b:c", "ref": "0123456789abcdef"},
        {"kind": "text", "text": " then "},
        {"kind": "code", "code": "x", "ref": None},
    ]
    assert guard.segments("<b>x</b>", {}, prose=False)[0].model_dump()["text"] == "<b>x</b>"
    assert guard.withheld == 0
