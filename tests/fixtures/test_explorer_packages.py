"""M13 explorer PoC, PR 4: package files, the server overview, and scale budgets.

The scale test is marked `slow` (run it with `uv run pytest -m slow`). It builds an analysis
of about 7,300 services and 9,600 document types in memory, by analysing one synthetic
package and copying it under new names, and checks the export budgets of the plan.
"""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path
from typing import Any

import pytest

from wm_doc.analysis import analyze_path
from wm_doc.config import AppConfig, load_config
from wm_doc.effects import compute_service_facts
from wm_doc.explorer.build import (
    LITERAL_PLACEHOLDER,
    ExplorerInputs,
    ExplorerOptions,
    build_bundle,
)
from wm_doc.explorer.contract import PackageDetail, ServerOverview
from wm_doc.explorer.inputs import explorer_inputs
from wm_doc.explorer.synthetic import (
    write_demo_descriptions,
    write_demo_overviews,
    write_demo_packages,
)
from wm_doc.explorer.write import render_data_files, write_explorer
from wm_doc.ir import AnalysisResult, AnalyzedPackage
from wm_doc.overviews import summarize_packages


@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synthetic-packages") / "packages"
    write_demo_packages(root, filler_services=30, filler_documents=12)
    return root


@pytest.fixture(scope="module")
def analysis(packages: Path) -> AnalysisResult:
    return analyze_path(packages, load_config(None), None, processes_file_explicit=False)


@pytest.fixture(scope="module")
def docs_dir(
    packages: Path, analysis: AnalysisResult, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    docs = tmp_path_factory.mktemp("synthetic-overviews")
    write_demo_descriptions(docs, analysis, packages, load_config(None))
    assert write_demo_overviews(docs, analysis) == 3
    return docs


def _files(
    packages: Path, analysis: AnalysisResult, docs_dir: Path | None, shown: str = "all"
) -> dict[str, bytes]:
    inputs = explorer_inputs(analysis, packages, load_config(None), docs_dir=docs_dir)
    options = ExplorerOptions(dataset_kind="synthetic", descriptions=shown)  # type: ignore[arg-type]
    return render_data_files(build_bundle(inputs, options))


@pytest.fixture(scope="module")
def files(packages: Path, analysis: AnalysisResult, docs_dir: Path) -> dict[str, bytes]:
    return _files(packages, analysis, docs_dir)


def _package(files: dict[str, bytes], name: str) -> dict[str, Any]:
    search = json.loads(files["search.json"])
    identifier = next(item["id"] for item in search["packages"] if item["name"] == name)
    package: dict[str, Any] = json.loads(files[f"packages/{identifier}.json"])
    return package


def _text(segments: list[dict[str, Any]]) -> str:
    return "".join(s["text"] if s["kind"] == "text" else s["code"] for s in segments)


def test_one_valid_file_per_package_listing_its_services(
    analysis: AnalysisResult, files: dict[str, bytes]
) -> None:
    search = json.loads(files["search.json"])
    paths = [path for path in files if path.startswith("packages/")]
    assert len(paths) == len(analysis.packages) == len(search["packages"])
    for path in paths:
        detail = PackageDetail.model_validate_json(files[path])
        listed = [item for item in search["services"] if item["package"] == detail.name]
        assert [service.name for service in detail.services] == [item["name"] for item in listed]
        assert detail.services_total == len(listed)


def test_package_facts_follow_the_package_summary(
    analysis: AnalysisResult, files: dict[str, bytes]
) -> None:
    summary = summarize_packages(analysis, compute_service_facts(analysis))["OrdersApi"]
    detail = _package(files, "OrdersApi")

    assert detail["documentTypes"] == summary.document_count == 2
    assert [entry["service"]["name"] for entry in detail["entryPoints"]] == [
        entry.service for entry in summary.entries
    ]
    assert [(link["name"], link["calls"]) for link in detail["callsInto"]] == list(
        summary.calls_into
    )
    assert [(link["name"], link["calls"]) for link in detail["calledFrom"]] == list(
        summary.called_from
    )
    assert all(link["id"] is not None for link in detail["callsInto"])
    entries = {entry["service"]["name"]: entry for entry in detail["entryPoints"]}
    cancel = entries["orders.api:cancelOrder"]
    assert "JMS trigger" in _text(cancel["reachedFrom"][0])


def test_package_effects_are_own_effects_with_literals_masked(files: dict[str, bytes]) -> None:
    effects = _package(files, "OrdersApi")["effects"]
    http = next(e for e in effects if e["action"] == "calls an external HTTP endpoint")

    assert LITERAL_PLACEHOLDER in _text(http["where"])
    assert http["knownFrom"] == ["literal"]
    assert [s["name"] for s in http["services"]] == ["orders.api:createOrder"]
    # Table effects belong to OrdersDb's adapter services, not to the package calling them.
    assert not any(e["action"] == "inserts rows into" for e in effects)
    db = _package(files, "OrdersDb")["effects"]
    assert any(e["action"] == "inserts rows into" for e in db)


def test_overviews_show_with_their_review_state(
    packages: Path, analysis: AnalysisResult, docs_dir: Path, files: dict[str, bytes]
) -> None:
    orders = _package(files, "OrdersApi")["overview"]
    assert orders["state"] == "approved"
    assert [s["key"] for s in orders["sections"]] == [
        "purpose",
        "capabilities",
        "entryPoints",
        "systemsAndData",
    ]
    assert _package(files, "OrdersDb")["overview"]["state"] == "draft"
    assert _package(files, "CommonUtils")["overview"] is None

    server = ServerOverview.model_validate_json(files["overview.json"])
    assert server.description is not None and server.description.state == "approved"
    assert [section.key for section in server.description.sections][:2] == ["purpose", "areas"]

    approved_only = _files(packages, analysis, docs_dir, "approved")
    assert _package(approved_only, "OrdersDb")["overview"] is None
    search = json.loads(approved_only["search.json"])
    orders_entry = next(p for p in search["packages"] if p["name"] == "OrdersApi")
    assert orders_entry["overview"] == "approved" and orders_entry["purpose"]


def test_skipped_packages_are_listed_with_their_reason(
    tmp_path: Path, packages: Path
) -> None:
    config = load_config(None)
    selection = config.packages.model_copy(update={"exclude": ["Demo*"]})
    narrowed: AppConfig = config.model_copy(update={"packages": selection})
    analysis = analyze_path(packages, narrowed, None, processes_file_explicit=False)
    files = render_data_files(
        build_bundle(explorer_inputs(analysis, packages, narrowed), ExplorerOptions())
    )
    skipped = json.loads(files["overview.json"])["skippedPackages"]
    assert [item["name"] for item in skipped] == ["Demo001", "Demo002", "DemoDocs001"]
    assert all(item["reason"] for item in skipped)


# --- scale --------------------------------------------------------------------------------

SCALE_PACKAGES = 292  # x 25 services, plus the 15 of the core server: 7,315 services
SCALE_DOCUMENT_PACKAGES = 24  # x 400 document types, plus 2: 9,602


def _scaled_analysis(root: Path) -> AnalysisResult:
    """One analysed filler package and document package, copied under new names."""
    write_demo_packages(root, filler_services=25, filler_documents=400)
    base = analyze_path(root, load_config(None), None, processes_file_explicit=False)
    by_name = {package.name: package for package in base.packages}
    flows = by_name["Demo001"].model_dump_json()
    documents = by_name["DemoDocs001"].model_dump_json()
    copies: list[AnalyzedPackage] = []
    for number in range(2, SCALE_PACKAGES + 1):
        docs = (number - 1) % SCALE_DOCUMENT_PACKAGES + 1
        text = (
            flows.replace("demo001.", f"demo{number:03d}.")
            .replace("Demo001", f"Demo{number:03d}")
            .replace("demodocs001.", f"demodocs{docs:03d}.")
        )
        copies.append(AnalyzedPackage.model_validate_json(text))
    for number in range(2, SCALE_DOCUMENT_PACKAGES + 1):
        text = documents.replace("demodocs001.", f"demodocs{number:03d}.").replace(
            "DemoDocs001", f"DemoDocs{number:03d}"
        )
        copies.append(AnalyzedPackage.model_validate_json(text))
    return base.model_copy(update={"packages": [*base.packages, *copies]})


@pytest.mark.slow
def test_export_meets_the_budgets_at_production_size(tmp_path: Path) -> None:
    analysis = _scaled_analysis(tmp_path / "packages")
    services = analysis.services
    assert 7_300 <= len(services) <= 7_400
    assert 9_600 <= len(analysis.document_types) <= 9_700

    started = time.perf_counter()
    facts = compute_service_facts(analysis)
    bundle = build_bundle(ExplorerInputs(analysis, facts), ExplorerOptions())
    report = write_explorer(tmp_path / "out", bundle, tmp_path / "packages")
    seconds = time.perf_counter() - started
    data = tmp_path / "out" / "data"

    tracemalloc.start()
    try:
        render_data_files(
            build_bundle(
                ExplorerInputs(analysis, compute_service_facts(analysis)), ExplorerOptions()
            )
        )
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()

    budgets = {
        "export seconds (30)": (seconds, 30),
        "memory MB above the analysis (300)": (peak / 1e6, 300),
        "data MB (30)": (report.data_bytes / 1e6, 30),
        "graph.json MB (2)": ((data / "graph.json").stat().st_size / 1e6, 2),
        "search.json MB (2)": ((data / "search.json").stat().st_size / 1e6, 2),
        "largest service file KB (100)": (
            max(path.stat().st_size for path in (data / "services").iterdir()) / 1e3,
            100,
        ),
    }
    over = {name: round(value, 1) for name, (value, limit) in budgets.items() if value > limit}
    assert over == {}, budgets
