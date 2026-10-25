"""M13 explorer PoC, PR 3: the graph table and its agreement with focused publication.

`explorer-ui/src/domain/graph-fixture.json` holds a synthetic graph and, for several services
and depths, the members of `analyze --target-service X --dependency-depth N`. The TypeScript
graph walk must reproduce them (explorer-ui/src/domain/graph.test.ts), which shows the
browser walks only edges Python emitted. Regenerate it with:

    WM_DOC_UPDATE_FIXTURES=1 uv run pytest tests/fixtures/test_explorer_graph.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.effects import compute_service_facts
from wm_doc.explorer.build import ExplorerInputs, ExplorerOptions, build_bundle
from wm_doc.explorer.contract import GraphData
from wm_doc.explorer.synthetic import write_demo_packages
from wm_doc.explorer.write import render_data_files
from wm_doc.ir import AnalysisResult
from wm_doc.scope_analysis import ScopeRequest, ScopeSelectorType, build_focused_scope

REPO = Path(__file__).resolve().parents[2]
FIXTURE = REPO / "explorer-ui" / "src" / "domain" / "graph-fixture.json"
CASES = [
    ("orders.rest.order:_post", 0),
    ("orders.rest.order:_post", 1),
    ("orders.rest.order:_post", 2),
    ("orders.rest.order:_post", None),
    ("orders.api:createOrder", 1),
    ("orders.api:createOrder", 3),
    ("demo001.flows:step000", 2),
    ("demo001.flows:step000", None),
    ("common.error:handleError", 1),
]


@pytest.fixture(scope="module")
def analysis(tmp_path_factory: pytest.TempPathFactory) -> AnalysisResult:
    root = tmp_path_factory.mktemp("synthetic-graph") / "packages"
    write_demo_packages(root, filler_services=30)
    return analyze_path(root, load_config(None), None, processes_file_explicit=False)


@pytest.fixture(scope="module")
def files(analysis: AnalysisResult) -> dict[str, bytes]:
    bundle = build_bundle(
        ExplorerInputs(analysis=analysis, facts=compute_service_facts(analysis)),
        ExplorerOptions(dataset_kind="synthetic"),
    )
    return render_data_files(bundle)


def _json(files: dict[str, bytes], path: str) -> Any:
    return json.loads(files[path])


def test_graph_file_validates_and_follows_the_search_order(files: dict[str, bytes]) -> None:
    graph = GraphData.model_validate_json(files["graph.json"])
    search = _json(files, "search.json")

    assert graph.services == [item["id"] for item in search["services"]]
    size = len(graph.services) + len(graph.targets)
    for source, target, *_ in graph.edges:
        assert 0 <= source < len(graph.services) and 0 <= target < size


def test_every_call_on_a_service_page_is_one_edge(files: dict[str, bytes]) -> None:
    graph = _json(files, "graph.json")
    services: list[str] = graph["services"]
    names = {item["id"]: item["name"] for item in _json(files, "search.json")["services"]}

    def node_name(index: int) -> str:
        if index < len(services):
            return names[services[index]]
        name: str = graph["targets"][index - len(services)]["name"]
        return name

    for node, identifier in enumerate(services):
        detail = _json(files, f"services/{identifier}.json")
        edges = [edge for edge in graph["edges"] if edge[0] == node]
        assert len(edges) == detail["callsTotal"]
        assert [(node_name(e[1]), e[2], e[3]) for e in edges] == [
            (call["target"], call["relation"], call["count"]) for call in detail["calls"]
        ]


def test_resolved_edges_are_exactly_the_resolved_dependencies(
    analysis: AnalysisResult, files: dict[str, bytes]
) -> None:
    graph = _json(files, "graph.json")
    names = {item["id"]: item["name"] for item in _json(files, "search.json")["services"]}
    services = graph["services"]
    resolved = {
        (names[services[source]], names[services[target]], relation)
        for source, target, relation, _ in graph["edges"]
        if target < len(services)
    }
    relation = {"INVOKES": "invokes", "USES_TRANSFORMER": "transformer"}
    expected = {
        (dependency.source_service, dependency.target_service, relation[dependency.dependency_kind])
        for dependency in analysis.unique_dependencies
        if dependency.resolved
    }
    assert resolved == expected


def test_placeholder_targets_belong_to_one_caller_and_platform_targets_are_shared(
    files: dict[str, bytes],
) -> None:
    graph = _json(files, "graph.json")
    offset = len(graph["services"])
    callers: dict[int, set[int]] = {}
    for source, target, *_ in graph["edges"]:
        if target >= offset:
            callers.setdefault(target, set()).add(source)
    for index, target in enumerate(graph["targets"]):
        if target["name"].startswith("<"):
            assert len(callers[index + offset]) == 1, target
    platform = [t for t in graph["targets"] if t["name"] == "common.log:logEvent"]
    assert platform == []  # an analysed service is never a target
    debug_log = [
        i for i, t in enumerate(graph["targets"]) if t["name"] == "pub.flow:getLastError"
    ]
    assert len(debug_log) == 1 and len(callers[debug_log[0] + offset]) > 1


def _scope_members(analysis: AnalysisResult, name: str, depth: int | None) -> list[str]:
    output = build_focused_scope(
        analysis,
        ScopeRequest(ScopeSelectorType.SERVICE, name, depth),
        process_catalog_available=False,
    )
    assert output.scope is not None
    return sorted(member.service for member in output.scope.service_memberships)


def test_typescript_graph_fixture_is_current(
    analysis: AnalysisResult, files: dict[str, bytes]
) -> None:
    fixture = {
        "comment": "Generated by tests/fixtures/test_explorer_graph.py; do not edit.",
        "search": _json(files, "search.json"),
        "graph": _json(files, "graph.json"),
        "cases": [
            {
                "focal": name,
                "depth": depth,
                "members": _scope_members(analysis, name, depth),
            }
            for name, depth in CASES
        ],
    }
    text = json.dumps(fixture, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    if os.environ.get("WM_DOC_UPDATE_FIXTURES") == "1":
        FIXTURE.write_text(text, encoding="utf-8", newline="\n")
    committed = FIXTURE.read_text(encoding="utf-8") if FIXTURE.exists() else ""
    assert committed == text, "Regenerate with WM_DOC_UPDATE_FIXTURES=1 (see module docstring)"
