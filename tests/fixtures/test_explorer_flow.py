"""M14 stage 6: the conditional flow of a FLOW service in the explorer (`flows/<id>.json`).

Python computes the control model, the field origins and the scenarios, and prepares every
display string with the same wording as the service pages; the app only shows them. Mapping
literals are never exported; condition values (case labels) are shown unless the build
excludes them.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from flowxml import FlowPackage, branch, case, exit_, invoke, map_, record, set_, string
from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.explorer.build import ExplorerOptions, build_bundle
from wm_doc.explorer.contract import FlowView
from wm_doc.explorer.flow import MAX_FLOW_CALLS, MAX_OUTLINE_STEPS, flow_view
from wm_doc.explorer.inputs import explorer_inputs
from wm_doc.explorer.synthetic import FAKE_SECRETS, write_demo_packages
from wm_doc.explorer.text import TextGuard
from wm_doc.explorer.write import dump, render_data_files
from wm_doc.ir import AnalysisResult

PROCESS = "orders.api:processOrder"
MAPSET_LITERAL = "UNCHECKED"  # set by processOrder before its decisions; never exported
FEASIBILITY = ("possible", "conditional", "unresolved")


@pytest.fixture(scope="module")
def packages(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("synthetic-flow") / "packages"
    write_demo_packages(root)
    return root


@pytest.fixture(scope="module")
def analysis(packages: Path) -> AnalysisResult:
    return analyze_path(packages, load_config(None), None, processes_file_explicit=False)


def _build(
    packages: Path, analysis: AnalysisResult, condition_values: str = "included"
) -> dict[str, bytes]:
    inputs = explorer_inputs(analysis, packages, load_config(None))
    options = ExplorerOptions(
        dataset_kind="synthetic",
        condition_values=condition_values,  # type: ignore[arg-type]
    )
    return render_data_files(build_bundle(inputs, options))


@pytest.fixture(scope="module")
def built(packages: Path, analysis: AnalysisResult) -> dict[str, bytes]:
    return _build(packages, analysis)


def _detail(files: dict[str, bytes], name: str) -> dict[str, Any]:
    search = json.loads(files["search.json"])
    identifier = next(item["id"] for item in search["services"] if item["name"] == name)
    detail: dict[str, Any] = json.loads(files[f"services/{identifier}.json"])
    return detail


def _flow(files: dict[str, bytes], name: str) -> dict[str, Any]:
    flow: dict[str, Any] = json.loads(files[f"flows/{_detail(files, name)['id']}.json"])
    return flow


def _plain(segments: list[dict[str, Any]]) -> str:
    return "".join(
        item["text"] if item["kind"] == "text" else f"`{item['code']}`" for item in segments
    )


def _steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found = []
    for step in steps:
        found.append(step)
        found += _steps(step["children"])
    return found


# --- the files --------------------------------------------------------------------------------


def test_a_branching_service_has_a_flow_file(built: dict[str, bytes]) -> None:
    detail = _detail(built, PROCESS)

    assert detail["flow"] == {"decisions": 2, "calls": 5, "exits": 1}
    flow = FlowView.model_validate_json(built[f"flows/{detail['id']}.json"])
    assert flow.service_id == detail["id"]


def test_a_service_without_conditional_logic_has_no_flow_file(built: dict[str, bytes]) -> None:
    detail = _detail(built, "orders.api:validateOrder")

    assert detail["flow"] is None
    assert f"flows/{detail['id']}.json" not in built


def test_the_manifest_digest_covers_the_flow_files(built: dict[str, bytes]) -> None:
    lines = "".join(
        f"{path} {hashlib.sha256(content).hexdigest()}\n"
        for path, content in sorted(built.items())
        if path != "manifest.json"
    )
    manifest = json.loads(built["manifest.json"])

    assert any(path.startswith("flows/") for path in built)
    assert manifest["digest"] == hashlib.sha256(lines.encode("utf-8")).hexdigest()
    assert manifest["disclosure"]["conditionValues"] == "included"


# --- what a flow file says ---------------------------------------------------------------------


def test_decisions_show_conditions_and_link_their_calls(built: dict[str, bytes]) -> None:
    flow = _flow(built, PROCESS)
    validate = _detail(built, "orders.api:validateOrder")["id"]

    first = flow["decisions"][0]
    conditions = {case["id"]: _plain(case["condition"]) for case in first["cases"]}

    assert first["id"] == "D1"
    assert _plain(first["heading"]).startswith("BRANCH on `/order/status`")
    assert conditions == {
        "D1.c1": "`/order/status` is `ACTIVE`",
        "D1.c2": "`/order/status` is `CANCELLED`",
        "D1.c3": "no other case matches",
    }
    link = {"kind": "code", "code": "orders.api:validateOrder", "ref": validate}
    assert link in first["cases"][0]["calls"]
    second = flow["decisions"][1]
    assert second["cases"][1]["ends"]  # the "false" case ends with EXIT $flow FAILURE
    assert second["noMatch"] is not None


def test_calls_say_when_they_run_and_how_certain_that_is(built: dict[str, bytes]) -> None:
    flow = _flow(built, PROCESS)
    validate = _detail(built, "orders.api:validateOrder")["id"]

    calls = {call["id"]: call for call in flow["calls"]}

    assert calls["C1"]["target"] == "orders.api:validateOrder"
    assert calls["C1"]["targetId"] == validate
    assert _plain(calls["C1"]["runsWhen"]) == "D1 = `ACTIVE`"
    assert calls["C1"]["certainty"] == "derived"
    assert calls["C1"]["reach"] == "conditional"
    assert calls["C5"]["target"] == "common.error:handleError"


def test_field_origins_carry_certainty_basis_and_evidence(built: dict[str, bytes]) -> None:
    flow = _flow(built, PROCESS)

    field = flow["decisions"][1]["fields"][0]

    assert field["path"] == "/validationStatus"
    texts = [_plain(origin["text"]) for origin in field["origins"]]
    assert any(text.startswith("copied from `/valid` in the output map of C1") for text in texts)
    assert any(text.startswith("set to a literal (literal, not exported)") for text in texts)
    for origin in field["origins"]:
        assert origin["certainty"] in ("observed", "derived", "possible", "unknown")
        if origin["depth"] == 0:  # mapping lines of this service
            assert origin["basis"] == "flow-xml"
            assert origin["evidence"]["path"].endswith("flow.xml")
    # Where the copied /valid comes from: what the called service declares, and the caller.
    nested = {origin["basis"] for origin in field["origins"] if origin["depth"] == 1}
    assert nested == {"callee-signature", "caller-pipeline"}
    assert {origin["copied"] for origin in field["origins"] if origin["depth"] == 1} == {"/valid"}


def test_scenarios_combine_the_dependent_decisions(built: dict[str, bytes]) -> None:
    flow = _flow(built, PROCESS)

    table = flow["scenarios"][0]

    assert table["decisions"] == ["D1", "D2"]
    assert table["rows"]
    assert all(row["feasibility"] in FEASIBILITY for row in table["rows"])


def test_a_ruled_out_outcome_never_names_the_literal(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Lit")
    pkg.service(
        "lit.api:route",
        branch(
            case("A", map_(set_("/s", "lit-value-one"))),
            case("B", map_(set_("/s", "lit-value-two"))),
            switch="/a",
        ),
        branch(case("ok", invoke("lit.api:x")), case("$default", invoke("lit.api:y")), switch="/s"),
        inputs=[string("a")],
    )
    service = pkg.analyze().services[0]

    found = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="included")

    assert found is not None
    payload = json.loads(dump(found[1]))
    notes = [_plain(note) for table in payload["scenarios"] for note in table["notes"]]
    assert any(
        note.startswith(
            "Ruled out: D1 = `A`; D2 = `ok`: `/s` is always one literal (literal, not exported)"
        )
        for note in notes
    ), notes
    text = dump(found[1]).decode("utf-8")
    assert "lit-value-one" not in text and "lit-value-two" not in text


def test_mapping_literals_and_secrets_never_reach_a_flow_file(built: dict[str, bytes]) -> None:
    text = b"".join(content for path, content in built.items() if path.startswith("flows/"))

    assert MAPSET_LITERAL.encode() not in text
    for secret in FAKE_SECRETS:
        assert secret.encode() not in text
    assert b"Rejected" not in text  # the EXIT failure message


def test_the_outline_follows_the_flow_with_ids(built: dict[str, bytes]) -> None:
    flow = _flow(built, PROCESS)

    steps = _steps(flow["outline"])
    by_ref = {step["ref"]: step for step in steps if step["ref"]}

    assert [step["kind"] for step in flow["outline"]] == ["map", "branch", "branch"]
    assert [child["ref"] for child in by_ref["D1"]["children"]] == ["D1.c1", "D1.c2", "D1.c3"]
    assert [child["ref"] for child in by_ref["D1.c1"]["children"]] == ["C1"]
    assert by_ref["C1"]["targetId"] == _detail(built, "orders.api:validateOrder")["id"]
    assert [child["kind"] for child in by_ref["D2.c2"]["children"]] == ["call", "exit"]
    assert flow["outlineHidden"] == 0


# --- condition values --------------------------------------------------------------------------


def test_condition_values_can_be_left_out(packages: Path, analysis: AnalysisResult) -> None:
    files = _build(packages, analysis, "excluded")

    flow = _flow(files, PROCESS)
    first = flow["decisions"][0]
    text = b"".join(content for path, content in files.items() if path.startswith("flows/"))

    assert json.loads(files["manifest.json"])["disclosure"]["conditionValues"] == "excluded"
    assert _plain(first["cases"][0]["condition"]) == "`/order/status` is a value (withheld)"
    assert _plain(first["cases"][2]["condition"]) == "no other case matches"
    for value in (b"ACTIVE", b"CANCELLED", b"`true`", b"`false`"):
        assert value not in text, value
    # The facts are the same; only the values are not shown.
    included = _flow(_build(packages, analysis), PROCESS)
    assert [call["id"] for call in flow["calls"]] == [call["id"] for call in included["calls"]]
    assert len(flow["scenarios"][0]["rows"]) == len(included["scenarios"][0]["rows"])


LONG_LABEL = "LONGLABEL-" + "q" * 130  # shortened in code spans; never shown in part either


def test_no_case_label_reaches_a_flow_file_when_values_are_left_out(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Labels")
    pkg.service(
        "labels.api:route",
        branch(
            case(LONG_LABEL, invoke("labels.api:a"), exit_(LONG_LABEL), invoke("labels.api:b")),
            case("two spaced words", invoke("labels.api:c")),
            case("/^PATTERNVALUE.*/", invoke("labels.api:d")),
            switch="/kind",
        ),
        branch(
            case('%kind% == "EXPRVALUE"', invoke("labels.api:e")),
            case("$default", invoke("labels.api:f")),
            expressions=True,
        ),
        inputs=[string("kind")],
    )
    service = pkg.analyze().services[0]

    found = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="excluded")
    shown = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="included")

    assert found is not None and shown is not None
    text = dump(found[1]).decode("utf-8")
    for fragment in ("LONGLABEL", "qqqqqqqq", "spaced words", "PATTERNVALUE", "EXPRVALUE"):
        assert fragment not in text, fragment
        assert fragment in dump(shown[1]).decode("utf-8") or fragment == "qqqqqqqq"
    view = json.loads(text)
    # The facts are the same: the EXIT leaves the case's step and the call after it never runs.
    assert [_plain(line) for line in view["exits"]][0].startswith("E1 leaves the SEQUENCE (line ")
    assert "(label withheld) with success" in _plain(view["exits"][0])
    assert view["neverRun"]
    assert _plain(view["decisions"][1]["cases"][0]["condition"]) == (
        "(expression withheld; it tests `/kind`)"
    )


def test_cases_per_decision_are_capped(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Many")
    pkg.service(
        "many.api:route",
        branch(*[case(f"V{n}", invoke(f"many.api:c{n}")) for n in range(45)], switch="/kind"),
        inputs=[string("kind")],
    )

    found = flow_view(
        pkg.analyze().services[0], "svc", {}, TextGuard(), {}, condition_values="included"
    )

    assert found is not None
    decision = found[1].decisions[0]
    assert len(decision.cases) == 40 and decision.cases_hidden == 5


def test_hidden_outline_steps_are_counted_as_the_outline_walks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import wm_doc.explorer.flow as flow_module

    service = _wide_service(tmp_path, cases=4, calls_per_case=10).services[0]
    monkeypatch.setattr(flow_module, "OUTLINE_BYTES", 100_000_000)
    monkeypatch.setattr(flow_module, "MAX_OUTLINE_STEPS", 100_000)
    whole = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="included")
    monkeypatch.setattr(flow_module, "MAX_OUTLINE_STEPS", 300)
    capped = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="included")

    assert whole is not None and capped is not None
    total = len(_steps([step.model_dump(by_alias=True) for step in whole[1].outline]))
    shown = len(_steps([step.model_dump(by_alias=True) for step in capped[1].outline]))
    assert shown == 300
    assert shown + capped[1].outline_hidden == total


def test_the_cli_takes_the_condition_values_option(packages: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "explorer"

    result = runner.invoke(
        app,
        ["explorer", "build", str(packages), "-o", str(output), "--condition-values", "exclude"],
    )
    wrong = runner.invoke(
        app,
        ["explorer", "build", str(packages), "-o", str(output), "--condition-values", "maybe"],
    )

    assert result.exit_code == 0, result.output
    manifest = json.loads((output / "data" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["disclosure"]["conditionValues"] == "excluded"
    assert wrong.exit_code == 2


# --- limits ------------------------------------------------------------------------------------


def _wide_service(root: Path, cases: int, calls_per_case: int) -> AnalysisResult:
    def calls(decision: int, number: int) -> list[str]:
        return [invoke(f"wide.api:c{decision}x{number}x{n}") for n in range(calls_per_case)]

    pkg = FlowPackage(root, "Wide")
    pkg.service(
        "wide.api:route",
        *[
            branch(
                *[case(f"V{number}", *calls(decision, number)) for number in range(cases)],
                switch=f"/kind{decision}",
            )
            for decision in range(45)
        ],
        inputs=[record("request", [string("kind")])],
    )
    return pkg.analyze()


def test_outline_and_lists_are_capped(tmp_path: Path) -> None:
    service = _wide_service(tmp_path, cases=4, calls_per_case=10).services[0]

    found = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="included")

    assert found is not None
    _ref, view = found
    shown = _steps([step.model_dump(by_alias=True) for step in view.outline])
    assert len(shown) <= MAX_OUTLINE_STEPS
    assert view.outline_hidden > 0
    # Counts and byte budgets both cap a part; what is left out is always counted.
    assert len(view.calls) <= MAX_FLOW_CALLS and view.calls_hidden > 0
    assert len(view.calls) + view.calls_hidden == 45 * 4 * 10
    assert len(view.decisions) <= 40 and view.decisions_hidden >= 5
    assert len(view.decisions) + view.decisions_hidden == 45
    assert len(dump(view)) < 200_000


@pytest.mark.slow
def test_no_flow_file_is_over_200_kb(tmp_path: Path) -> None:
    service = _wide_service(tmp_path, cases=30, calls_per_case=4).services[0]

    found = flow_view(service, "svc", {}, TextGuard(), {}, condition_values="included")

    assert found is not None
    assert len(dump(found[1])) < 200_000
