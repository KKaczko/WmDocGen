"""M13 explorer PoC: the data contract, the build, its safety guarantees and the server."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.call_targets import TargetStatus, classify_target
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.effects import compute_service_facts
from wm_doc.explorer.build import ExplorerInputs, ExplorerOptions, build_bundle
from wm_doc.explorer.contract import (
    CONTRACT,
    SCHEMA_PATH,
    Manifest,
    SearchIndex,
    ServiceDetail,
    render_contract_schema,
)
from wm_doc.explorer.ids import ID_RE, IdCollisionError, IdRegistry, service_id
from wm_doc.explorer.serve import CONTENT_SECURITY_POLICY, make_server
from wm_doc.explorer.synthetic import FAKE_SECRETS, write_demo_packages
from wm_doc.explorer.text import TextGuard
from wm_doc.explorer.write import (
    ExplorerOutputError,
    check_output_location,
    render_data_files,
    write_explorer,
)
from wm_doc.external_systems import ExternalSystem, ExternalSystemCatalog
from wm_doc.ir import AnalysisResult
from wm_doc.service_docs import DocState, DocStatus, ServiceDoc

REPO = Path(__file__).resolve().parents[2]
EXPLORER_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+wm_doc\.explorer", re.MULTILINE)
ABSOLUTE_PATH_RE = re.compile(r"(?:^|[\s\"'(])(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp|var)/)")


@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synthetic") / "packages"
    write_demo_packages(root, filler_services=30)
    return root


@pytest.fixture(scope="module")
def analysis(packages: Path) -> AnalysisResult:
    return analyze_path(packages, load_config(None), None, processes_file_explicit=False)


@pytest.fixture(scope="module")
def built(analysis: AnalysisResult) -> dict[str, bytes]:
    bundle = build_bundle(
        ExplorerInputs(analysis=analysis, facts=compute_service_facts(analysis)),
        ExplorerOptions(dataset_kind="synthetic"),
    )
    return render_data_files(bundle)


def _json(files: dict[str, bytes], path: str) -> Any:
    return json.loads(files[path])


def _detail(files: dict[str, bytes], name: str) -> dict[str, Any]:
    search = _json(files, "search.json")
    identifier = next(item["id"] for item in search["services"] if item["name"] == name)
    detail: dict[str, Any] = _json(files, f"services/{identifier}.json")
    return detail


# --- contract -----------------------------------------------------------------------------


def test_committed_schema_matches_the_contract_models() -> None:
    committed = (REPO / SCHEMA_PATH).read_text(encoding="utf-8")
    assert committed == render_contract_schema(), (
        "Regenerate with: uv run python -m wm_doc.explorer.contract"
    )


def test_every_file_validates_against_the_contract(built: dict[str, bytes]) -> None:
    manifest = Manifest.model_validate_json(built["manifest.json"])
    search = SearchIndex.model_validate_json(built["search.json"])
    details = [
        ServiceDetail.model_validate_json(content)
        for path, content in built.items()
        if path.startswith("services/")
    ]
    assert manifest.contract == search.contract == CONTRACT
    assert manifest.counts.services == len(search.services) == len(details)
    assert all(detail.contract == CONTRACT for detail in details)
    assert all(ID_RE.match(item.id) for item in search.services)
    assert {item.id for item in search.services} == {detail.id for detail in details}


def test_manifest_digest_covers_every_other_file(built: dict[str, bytes]) -> None:
    lines = "".join(
        f"{path} {hashlib.sha256(content).hexdigest()}\n"
        for path, content in sorted(built.items())
        if path != "manifest.json"
    )
    expected = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    assert _json(built, "manifest.json")["digest"] == expected


# --- what the explorer shows ----------------------------------------------------------------


def test_calls_carry_their_status_kind_and_note(built: dict[str, bytes]) -> None:
    detail = _detail(built, "orders.api:createOrder")
    calls = {call["target"]: call for call in detail["calls"]}

    assert calls["orders.db:insertOrder"]["status"] == "resolved"
    assert calls["orders.db:insertOrder"]["targetKind"] == "adapter"
    assert calls["orders.db:insertOrder"]["targetAnalysis"] == "opaque"
    assert ID_RE.match(calls["orders.db:insertOrder"]["targetId"])
    assert calls["pub.client:http"]["status"] == "platform"
    assert calls["pub.client:http"]["note"]
    assert calls["billing.api:postInvoice"]["status"] == "outside"
    assert calls["billing.api:postInvoice"]["targetId"] is None
    assert "pub.flow:debugLog" not in calls  # a disabled step never runs
    assert detail["analysis"]["disabledSteps"] == 1
    assert [caller["name"] for caller in detail["callers"]] == ["orders.rest.order:_post"]
    orders = [call["firstOrder"] for call in detail["calls"]]
    assert orders == sorted(orders)
    evidence = calls["orders.db:insertOrder"]["evidence"][0]
    assert evidence["path"].endswith("createOrder/flow.xml")
    assert evidence["xmlPath"].startswith("/FLOW")


def test_dynamic_java_invocations_are_shown_as_boundaries(built: dict[str, bytes]) -> None:
    detail = _detail(built, "orders.api.routing:routeOrder")
    statuses = sorted((call["status"], call["target"]) for call in detail["calls"])

    assert ("resolved", "orders.api:validateOrder") in statuses
    # One dynamic `Service.doInvoke`, listed once (not again from its finding).
    assert [status for status, _ in statuses].count("dynamic") == 1
    assert detail["kind"] == "java"


def test_signature_marks_document_references_resolved_or_not(built: dict[str, bytes]) -> None:
    detail = _detail(built, "orders.api:createOrder")
    order = detail["signature"]["inputs"][0]

    assert order["name"] == "order"
    assert order["document"] == {"name": "orders.docs:Order", "resolved": True}
    assert detail["signature"]["truncated"] is False


def test_external_system_names_calls_leaving_the_packages(analysis: AnalysisResult) -> None:
    catalog = ExternalSystemCatalog(
        systems=[
            ExternalSystem(id="billing", name="Billing", vendor="SAP", namespaces=["billing.*"])
        ]
    )
    bundle = build_bundle(
        ExplorerInputs(
            analysis=analysis,
            facts=compute_service_facts(analysis, catalog),
            external_systems=catalog,
        ),
        ExplorerOptions(),
    )
    detail = next(d for d in bundle.services.values() if d.name == "orders.api:createOrder")
    billing = next(call for call in detail.calls if call.target == "billing.api:postInvoice")
    assert billing.note == "Billing (SAP)"


def test_search_index_is_sorted_and_names_packages(built: dict[str, bytes]) -> None:
    search = _json(built, "search.json")
    names = [item["name"] for item in search["services"]]

    assert names == sorted(names, key=lambda name: (name.casefold(), name))
    assert {item["name"] for item in search["packages"]} >= {"OrdersApi", "OrdersDb"}
    assert all(item["description"] == "none" for item in search["services"])


def test_description_states_follow_the_descriptions_option(analysis: AnalysisResult) -> None:
    def doc(service: str, status: DocStatus) -> ServiceDoc:
        narrative = "## Purpose\n\nCreates an order. It also logs.\n"
        return ServiceDoc(
            service=service,
            package="OrdersApi",
            status=status,
            model="m",
            facts_hash="f",
            text_hash="t",
            narrative=narrative,
        )

    docs = {
        "orders.api:createOrder": doc("orders.api:createOrder", DocStatus.APPROVED),
        "orders.api:getOrder": doc("orders.api:getOrder", DocStatus.DRAFT),
    }
    states = {"orders.api:createOrder": DocState.STALE, "orders.api:getOrder": DocState.DRAFT}
    facts = compute_service_facts(analysis)

    def search_for(shown: str) -> dict[str, tuple[str, str | None]]:
        bundle = build_bundle(
            ExplorerInputs(analysis, facts, service_docs=docs, service_states=states),
            ExplorerOptions(descriptions=shown),  # type: ignore[arg-type]
        )
        return {item.name: (item.description, item.purpose) for item in bundle.search.services}

    approved = search_for("approved")
    assert approved["orders.api:createOrder"] == ("stale", "Creates an order.")
    assert approved["orders.api:getOrder"] == ("none", None)
    assert search_for("all")["orders.api:getOrder"] == ("draft", "Creates an order.")
    assert search_for("none")["orders.api:createOrder"] == ("none", None)


# --- safety -------------------------------------------------------------------------------


def test_no_secret_comment_literal_or_absolute_path_reaches_the_data(
    built: dict[str, bytes],
) -> None:
    text = b"".join(built.values()).decode("utf-8")

    for secret in FAKE_SECRETS:
        assert secret not in text, secret
    assert "Creates the order. Test password" not in text  # designer comment
    assert "billingEndpoint" not in text  # mapped literal target, never exported
    assert "\\" not in text
    assert not ABSOLUTE_PATH_RE.search(text)


def test_build_is_deterministic_and_independent_of_the_folder_location(
    packages: Path, built: dict[str, bytes], tmp_path: Path
) -> None:
    copy = tmp_path / "elsewhere" / "pkgs"
    shutil.copytree(packages, copy)
    moved = analyze_path(copy, load_config(None), None, processes_file_explicit=False)
    again = render_data_files(
        build_bundle(
            ExplorerInputs(analysis=moved, facts=compute_service_facts(moved)),
            ExplorerOptions(dataset_kind="synthetic"),
        )
    )
    assert again == built


def test_written_folder_is_byte_identical_across_runs(
    packages: Path, analysis: AnalysisResult, tmp_path: Path
) -> None:
    bundle = build_bundle(
        ExplorerInputs(analysis=analysis, facts=compute_service_facts(analysis)),
        ExplorerOptions(dataset_kind="synthetic"),
    )
    first = write_explorer(tmp_path / "a", bundle, packages)
    second = write_explorer(tmp_path / "a", bundle, packages)
    assert first == second
    assert _tree(tmp_path / "a" / "data") == {
        f"data/{path}": hashlib.sha256(content).hexdigest()
        for path, content in render_data_files(bundle).items()
    }
    assert not (tmp_path / "a" / ".data-staging").exists()


def test_build_never_changes_the_analysed_packages(packages: Path, tmp_path: Path) -> None:
    before = _tree(packages, with_mtime=True)
    result = CliRunner().invoke(
        app,
        ["explorer", "build", str(packages), "-o", str(tmp_path / "out"), "--no-analysis-cache"],
    )
    assert result.exit_code == 0, result.output
    assert _tree(packages, with_mtime=True) == before
    assert (tmp_path / "out" / "data" / "manifest.json").is_file()


def test_output_overlapping_the_packages_folder_is_refused(packages: Path, tmp_path: Path) -> None:
    with pytest.raises(ExplorerOutputError) as inside:
        check_output_location(packages / "explorer", packages)
    assert inside.value.code == "OUTPUT_INSIDE_PACKAGES"
    with pytest.raises(ExplorerOutputError) as around:
        check_output_location(packages.parent, packages)
    assert around.value.code == "PACKAGES_INSIDE_OUTPUT"

    before = _tree(packages)
    result = CliRunner().invoke(app, ["explorer", "build", str(packages), "-o", str(packages)])
    assert result.exit_code == 2
    assert "OUTPUT_INSIDE_PACKAGES" in result.output
    assert _tree(packages) == before


def test_managed_cleanup_keeps_unrelated_files(packages: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "data").mkdir(parents=True)
    (out / "data" / "stale.json").write_text("{}", encoding="utf-8")
    (out / "notes.txt").write_text("mine", encoding="utf-8")
    analysis = analyze_path(packages, load_config(None), None, processes_file_explicit=False)
    bundle = build_bundle(
        ExplorerInputs(analysis=analysis, facts=compute_service_facts(analysis)), ExplorerOptions()
    )
    write_explorer(out, bundle, packages)
    assert (out / "notes.txt").read_text(encoding="utf-8") == "mine"
    assert not (out / "data" / "stale.json").exists()


def test_ids_are_stable_and_collisions_fail() -> None:
    assert service_id("Pkg", "a.b:c") == service_id("Pkg", "a.b:c")
    assert service_id("Pkg", "a.b:c") != service_id("Pkg", "a.B:c")
    registry = IdRegistry()
    registry.claim("0123456789abcdef", "one")
    registry.claim("0123456789abcdef", "one")
    with pytest.raises(IdCollisionError):
        registry.claim("0123456789abcdef", "two")


def test_text_guard_strips_invisible_characters_and_withholds_unsafe_text() -> None:
    guard = TextGuard()
    assert guard.name("orders.api:create" + chr(0x202E) + "Order" + chr(7)) == (
        "orders.api:createOrder"
    )
    assert guard.free_text("line one" + chr(0x2028) + "line two") == "line one line two"
    assert guard.free_text("uses password=hunter2 here") == "[withheld: secret-like key/value]"
    assert guard.free_text("<img src=x onerror=alert(1)>") == "[withheld: raw HTML]"
    assert guard.path("C:/Users/me/pkg/flow.xml") == "[withheld: absolute path]"
    assert guard.path("Pkg/ns/a/flow.xml") == "Pkg/ns/a/flow.xml"
    assert guard.free_text("x" * 5000, 100) is not None
    assert len(guard.free_text("x" * 5000, 100) or "") == 100
    assert guard.withheld == 3


def test_call_target_classification() -> None:
    assert classify_target("a.b:c", resolved=True) is TargetStatus.RESOLVED
    assert classify_target("pub.flow:debugLog", resolved=False) is TargetStatus.PLATFORM
    assert classify_target("billing.api:postInvoice", resolved=False) is TargetStatus.OUTSIDE
    assert classify_target("%dynamic%", resolved=False) is TargetStatus.UNRESOLVED


def test_core_modules_never_import_the_explorer() -> None:
    offenders = [
        path.relative_to(REPO).as_posix()
        for path in (REPO / "src" / "wm_doc").rglob("*.py")
        if "explorer" not in path.parts
        and path.name != "cli.py"
        and EXPLORER_IMPORT_RE.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == []


# --- server -------------------------------------------------------------------------------


@pytest.fixture()
def server(tmp_path: Path) -> Iterator[str]:
    (tmp_path / "data").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>x</title>", encoding="utf-8")
    (tmp_path / "data" / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".hidden").write_text("no", encoding="utf-8")
    httpd = make_server(tmp_path, "127.0.0.1", 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_sends_security_headers_and_json_type(server: str) -> None:
    with urllib.request.urlopen(f"{server}/data/manifest.json") as response:
        assert response.headers["Content-Type"].startswith("application/json")
        assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
        assert response.headers["X-Content-Type-Options"] == "nosniff"
    with urllib.request.urlopen(f"{server}/") as response:
        assert response.status == 200


@pytest.mark.parametrize("path", ["/data/", "/.hidden", "/data/../.hidden", "/missing.json"])
def test_server_lists_no_folders_and_hides_dot_files(server: str, path: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(f"{server}{path}")
    assert error.value.code == 404


def _tree(root: Path, *, with_mtime: bool = False) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            key = path.relative_to(root.parent if root.name == "data" else root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            tree[key] = (digest, path.stat().st_mtime_ns) if with_mtime else digest
    return tree


# --- the shipped app ------------------------------------------------------------------------

APP = REPO / "src" / "wm_doc" / "explorer" / "app"
# Strings inside the bundled libraries that look like URLs but are never fetched: XML
# namespaces, error-help links and a URL-parsing base. Anything else fails the test.
INERT_URLS = {
    "http://localhost",
    "http://www.w3.org/1998/Math/MathML",
    "http://www.w3.org/1999/xlink",
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/XML/1998/namespace",
    "https://github.com/ungap/url-search-params.",
    "https://react.dev/errors/",
    "https://reactrouter.com/en/main/routers/picking-a-router.",
}


def test_shipped_app_has_a_strict_policy_and_loads_nothing_external() -> None:
    index = (APP / "index.html").read_text(encoding="utf-8")
    assert "Content-Security-Policy" in index
    assert "script-src 'self'" in index and "connect-src 'self'" in index
    assert "<script>" not in index  # no inline script
    found: set[str] = set()
    for path in APP.rglob("*"):
        if path.suffix in {".html", ".js", ".css"}:
            text = path.read_text(encoding="utf-8")
            found.update(re.findall(r"https?://[^\"'`)\s\\]+", text))
    assert found <= INERT_URLS, sorted(found - INERT_URLS)
    assert (APP / "THIRD-PARTY.txt").is_file()
