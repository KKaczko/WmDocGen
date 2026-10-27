"""Stage 2 of the conditional-flow work: where the fields a decision tests come from."""

from __future__ import annotations

from pathlib import Path

import pytest
from flowxml import (
    Field,
    FlowPackage,
    branch,
    case,
    copy,
    drop,
    exit_,
    invoke,
    loop,
    map_,
    record,
    seq,
    set_,
    string,
    transform,
    try_catch,
)

from wm_doc.config import ExtractionMode
from wm_doc.flow_lineage import (
    FlowLineage,
    Origin,
    OriginKind,
    VariableOrigins,
    compute_flow_lineage,
)
from wm_doc.flow_logic import Certainty, FlowLogic, GuardKind, compute_flow_logic
from wm_doc.ir import AnalysisResult, FlowService
from wm_doc.render.flow_markdown import render_decision_facts, render_decisions_section

SUBJECT = "lineage.api:subject"
Extra = dict[str, tuple[list[str], list[Field]]]


class Subject:
    """One analysed service with its control model and origins."""

    def __init__(self, analysis: AnalysisResult, name: str = SUBJECT) -> None:
        self.service: FlowService = next(
            item for item in analysis.services if item.identity.full_name == name
        )
        signatures = {item.identity.full_name: item.signature for item in analysis.services}
        logic = compute_flow_logic(self.service)
        assert logic is not None
        self.logic: FlowLogic = logic
        lineage = compute_flow_lineage(self.service, logic, signatures)
        assert lineage is not None
        self.lineage: FlowLineage = lineage

    def variable(self, decision_id: str, path: str | None = None) -> VariableOrigins:
        items = self.lineage.for_decision(decision_id)
        if path is None:
            assert len(items) == 1
            return items[0]
        return next(item for item in items if item.path.text() == path)

    def origins(self, decision_id: str, path: str | None = None) -> list[Origin]:
        variable = self.variable(decision_id, path)
        return [self.lineage.origin(origin_id) for origin_id in variable.origins]

    def kinds(self, decision_id: str, path: str | None = None) -> list[OriginKind]:
        return [origin.kind for origin in self.origins(decision_id, path)]

    def text(self) -> str:
        return render_decisions_section(self.logic, self.lineage)


def _subject(
    tmp_path: Path,
    *steps: str,
    inputs: list[Field] | None = None,
    literals: ExtractionMode | None = None,
    extra: Extra | None = None,
) -> Subject:
    pkg = FlowPackage(tmp_path / "packages", "Lineage")
    pkg.service(SUBJECT, *steps, inputs=inputs)
    for name, (body, outputs) in (extra or {}).items():
        pkg.service(name, *body, outputs=outputs)
    return Subject(pkg.analyze(literals=literals))


def _process_order(tmp_path: Path, extra: Extra | None = None) -> Subject:
    return _subject(
        tmp_path,
        branch(
            case(
                "ACTIVE",
                invoke(
                    "systemA:validateOrder", outputs=[copy("/result/status", "/validationStatus")]
                ),
            ),
            case("FINALIZED", invoke("systemB:finalizeOrder")),
            switch="/request/status",
        ),
        branch(
            case("OK", invoke("systemC:activateOrder")),
            case("ERROR", invoke("common:handleError")),
            switch="/validationStatus",
        ),
        inputs=[record("request", [string("status")])],
        extra=extra,
    )


# --- F1: processOrder ---------------------------------------------------------------------


def test_a_declared_input_comes_from_the_caller(tmp_path: Path) -> None:
    subject = _process_order(tmp_path)

    assert subject.variable("D1").unique
    assert subject.kinds("D1") == [OriginKind.SERVICE_INPUT]
    assert "- Comes from: a declared input of this service" in subject.text()


def test_a_value_copied_from_a_call_response_may_come_from_it(tmp_path: Path) -> None:
    subject = _process_order(tmp_path)

    variable = subject.variable("D2")
    assert not variable.unique
    assert subject.kinds("D2") == [OriginKind.COPY, OriginKind.CALLER]
    copied = subject.origins("D2")[0]
    assert copied.source_path is not None and copied.source_path.text() == "/result/status"
    assert [(term.kind, term.case_ids) for term in copied.guard.terms] == [
        (GuardKind.IN_CASE, ("D1.c1",))
    ]
    assert "S20" in copied.rules and copied.weak
    sources = [subject.lineage.origin(origin_id) for origin_id in copied.source_origins]
    assert [source.kind for source in sources] == [OriginKind.CALL_RESPONSE, OriginKind.CALLER]
    assert sources[0].call_id == "C1" and sources[0].notes == ("output_map_reads",)
    assert variable.calls_in_between == ("C1", "C2")
    assert variable.depends_on_calls == ("C1",)
    text = subject.text()
    assert "copied from `/result/status` in the output map of C1 `systemA:validateOrder`" in text
    assert "only when D1 = `ACTIVE`" in text
    assert "outside the analysed packages" in text
    assert "shares the pipeline (S16): C1 `systemA:validateOrder`, C2" in text


def test_an_analysed_callee_names_its_declared_output(tmp_path: Path) -> None:
    subject = _process_order(
        tmp_path,
        extra={"systemA:validateOrder": ([map_()], [record("result", [string("status")])])},
    )

    copied = subject.origins("D2")[0]
    response = subject.lineage.origin(copied.source_origins[0])
    assert response.kind is OriginKind.CALL_RESPONSE
    assert response.notes == ("declared_output", "output_map_reads")
    assert response.declared_path is not None
    assert response.declared_path.text() == "/result/status"
    assert "it declares the output `/result/status`" in subject.text()


# --- single definitions --------------------------------------------------------------------


def test_the_last_overwrite_is_the_only_origin(tmp_path: Path) -> None:  # F4
    subject = _subject(
        tmp_path,
        map_(set_("/mode", "SLOW")),
        map_(set_("/mode", "FAST")),
        branch(case("FAST", invoke("x.api:fast")), switch="/mode"),
    )

    assert subject.variable("D1").unique
    [origin] = subject.origins("D1")
    assert (origin.kind, origin.value, origin.certainty) == (
        OriginKind.SET,
        "FAST",
        Certainty.OBSERVED,
    )
    assert "- Comes from: set to `FAST` in the MAP (line" in subject.text()


def test_a_dropped_field_is_absent(tmp_path: Path) -> None:  # F5
    subject = _subject(
        tmp_path,
        map_(copy("/request/status", "/status")),
        map_(drop("/status")),
        branch(case("A", invoke("x.api:a")), switch="/status"),
        inputs=[record("request", [string("status")])],
    )

    assert subject.kinds("D1") == [OriginKind.DROPPED]
    assert subject.variable("D1").absent_possible
    assert "dropped in the MAP" in subject.text()


def test_a_field_nobody_sets_comes_from_the_caller(tmp_path: Path) -> None:  # F6
    subject = _subject(tmp_path, branch(case("Y", invoke("x.api:y")), switch="/flag"))

    assert subject.kinds("D1") == [OriginKind.CALLER]
    assert not subject.variable("D1").unique
    assert "- Not set by this service before this decision" in subject.text()


def test_a_transformer_output_feeds_a_decision(tmp_path: Path) -> None:  # F15
    subject = _subject(
        tmp_path,
        map_(
            set_("/mode", "fast"),
            transform("pub.string:toUpper", [copy("/mode", "/inString")], [copy("/value", "/up")]),
        ),
        branch(case("FAST", invoke("x.api:fast")), switch="/up"),
        branch(case("x", invoke("x.api:x")), switch="/inString"),
    )

    [origin, caller] = subject.origins("D1")
    assert origin.kind is OriginKind.TRANSFORMER and origin.call_id == "C1"
    assert caller.kind is OriginKind.CALLER  # the output may be absent (S20)
    assert origin.weak and "S20" in origin.rules
    assert origin.source_path is not None and origin.source_path.text() == "/value"
    assert [item.text() for item in origin.inputs] == ["/mode"]
    assert subject.variable("D1").depends_on_calls == ("C1",)
    # The transformer's input is not a pipeline field (S18).
    assert subject.kinds("D2") == [OriginKind.CALLER]


def test_an_invoke_input_map_value_stays_after_the_call(tmp_path: Path) -> None:  # F16
    subject = _subject(
        tmp_path,
        invoke("x.api:send", inputs=[set_("/mode", "FAST")]),
        branch(case("FAST", invoke("x.api:fast")), switch="/mode"),
    )

    [origin] = subject.origins("D1")
    assert origin.kind is OriginKind.SET and "S17" in origin.rules
    assert origin.certainty is Certainty.DERIVED
    variable = subject.variable("D1")
    assert not variable.unique  # the called service may change it afterwards
    assert variable.calls_in_between == ("C1",)
    assert "in the input map of C1 `x.api:send`" in subject.text()
    assert "assumption S17" in subject.text()


# --- several definitions -------------------------------------------------------------------


def test_two_branch_cases_give_two_possible_origins(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("A", map_(set_("/t", "1"))),
            case("$default", map_(set_("/t", "2"))),
            switch="/s",
        ),
        branch(case("1", invoke("x.api:one")), switch="/t"),
    )

    assert not subject.variable("D2").unique
    assert [origin.value for origin in subject.origins("D2")] == ["1", "2"]
    second = subject.text().split("### D2")[1]
    assert "Comes from" not in second
    assert "- May come from any of:" in second


def test_set_and_copy_to_one_field_in_one_map(tmp_path: Path) -> None:  # F17
    subject = _subject(
        tmp_path,
        map_(set_("/t", "A"), copy("/request/status", "/t")),
        branch(case("A", invoke("x.api:a")), switch="/t"),
        inputs=[record("request", [string("status")])],
    )

    origins = subject.origins("D1")
    assert [origin.kind for origin in origins] == [OriginKind.SET, OriginKind.COPY]
    assert all("S19" in origin.rules for origin in origins)
    assert all(origin.certainty is Certainty.POSSIBLE for origin in origins)
    assert "their order is an assumption" in subject.text()


def test_overwrite_off_keeps_the_earlier_value(tmp_path: Path) -> None:  # F18
    subject = _subject(
        tmp_path,
        map_(set_("/t", "A")),
        map_(set_("/t", "B", overwrite=False)),
        branch(case("A", invoke("x.api:a")), switch="/t"),
    )

    origins = subject.origins("D1")
    assert [origin.value for origin in origins] == ["A", "B"]
    assert origins[1].weak and "S21" in origins[1].rules
    assert "only if it has no value yet (overwrite off)" in subject.text()


def test_variable_substitution_is_a_template(tmp_path: Path) -> None:  # F18
    subject = _subject(
        tmp_path,
        map_(set_("/t", "%kind%-x", variables=True)),
        branch(case("a-x", invoke("x.api:a")), switch="/t"),
    )

    [origin] = subject.origins("D1")
    assert origin.template and "S21" in origin.rules
    assert "set from the template `%kind%-x`" in subject.text()


@pytest.mark.parametrize("inputs", [None, [set_("/preserve", "t")]])
def test_clear_pipeline_may_remove_the_field(tmp_path: Path, inputs: list[str] | None) -> None:
    # F19. The `preserve` list may come from the pipeline, so the earlier value stays possible.
    subject = _subject(
        tmp_path,
        map_(set_("/t", "A")),
        invoke("pub.flow:clearPipeline", inputs=inputs),
        branch(case("A", invoke("x.api:a")), switch="/t"),
    )

    origins = subject.origins("D1")
    assert [origin.kind for origin in origins] == [OriginKind.SET, OriginKind.CLEARED]
    assert origins[1].rules == ("S26",) and origins[1].weak
    assert subject.variable("D1").absent_possible
    assert "removed by C1 `pub.flow:clearPipeline` (line" in subject.text()
    assert "unless its `preserve` list names it" in subject.text()


def test_restore_pipeline_may_put_a_value_back(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/t", "A")),
        invoke("pub.flow:restorePipeline"),
        branch(case("A", invoke("x.api:a")), switch="/t"),
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.RESTORED]
    assert "assumption S27" in subject.text()


# --- control flow --------------------------------------------------------------------------


def test_an_exit_carries_its_value_past_later_steps(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(
            map_(set_("/t", "A")),
            branch(case("X", map_(set_("/t", "B")), exit_("S")), switch="/x"),
            map_(set_("/t", "C")),
            name="S",
        ),
        branch(case("B", invoke("x.api:b")), switch="/t"),
    )

    assert [origin.value for origin in subject.origins("D2")] == ["B", "C"]


def test_a_catch_sees_values_set_before_the_failure(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        try_catch(
            [map_(set_("/stage", "sent")), invoke("x.api:send")],
            [branch(case("sent", invoke("x.api:undo")), switch="/stage")],
        ),
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.CALLER]


def test_a_loop_carries_values_into_the_next_iteration(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        loop(
            branch(case("Y", invoke("x.api:again")), switch="/seen"),
            map_(set_("/seen", "Y")),
            in_array="/items",
        ),
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.CALLER]


def test_a_loop_element_names_the_current_item(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        loop(branch(case("NEW", invoke("x.api:add")), switch="/items/status"), in_array="/items"),
        inputs=[record("items", [string("status")], dim=1)],
    )

    variable = subject.variable("D1")
    assert variable.loop_path is not None and variable.loop_path.text() == "/items"
    assert subject.kinds("D1") == [OriginKind.SERVICE_INPUT]
    assert "Inside the LOOP over `/items`, that path names the current element (S22)." in (
        subject.text()
    )


def test_a_whole_document_copy_defines_its_fields(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(copy("/request;2;0", "/order;2;0")),
        branch(case("A", invoke("x.api:a")), switch="/order/status"),
        inputs=[record("request", [string("status")])],
    )

    [origin, caller] = subject.origins("D1")
    assert origin.kind is OriginKind.COPY and caller.kind is OriginKind.CALLER
    assert origin.source_path is not None and origin.source_path.text() == "/request/status"
    assert origin.written_path is not None and origin.written_path.text() == "/order"


def test_a_field_written_inside_is_a_partial_change(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/order/note", "x")),
        branch(case("A", invoke("x.api:a")), switch="/order"),
    )

    assert subject.kinds("D1") == [OriginKind.PARTIAL, OriginKind.CALLER]


# --- negatives -----------------------------------------------------------------------------


def test_a_declared_output_never_replaces_the_value(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/verified", "false")),
        invoke("pgp.lib:verify"),
        branch(case("true", invoke("x.api:ok")), switch="/verified"),
        extra={"pgp.lib:verify": ([map_()], [string("verified")])},
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.CALL_RESPONSE]
    assert not subject.variable("D1").unique


def test_an_implicit_callee_output_is_a_caveat(tmp_path: Path) -> None:  # F23 (PGP shape)
    subject = _subject(
        tmp_path,
        invoke("pgp.lib:verify"),
        branch(case("true", invoke("x.api:ok")), switch="/verified"),
    )

    assert subject.kinds("D1") == [OriginKind.CALLER]
    assert subject.variable("D1").calls_in_between == ("C1",)
    assert "Calls that run before the decision may also change it" in subject.text()


def test_unknown_copy_attributes_make_the_copy_possible(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/source", "A")),
        map_(copy("/source", "/t", CONDITION="%flag% == 1")),
        branch(case("A", invoke("x.api:a")), switch="/t"),
    )

    origins = subject.origins("D1")
    assert [origin.kind for origin in origins] == [OriginKind.COPY, OriginKind.CALLER]
    assert origins[0].weak and "S25" in origins[0].rules


def test_a_scoped_step_is_not_followed(tmp_path: Path) -> None:  # F21
    scoped = seq(
        map_(set_("/t", "B")),
        branch(case("B", invoke("x.api:inner")), switch="/t"),
    ).replace("<SEQUENCE", '<SEQUENCE SCOPE="/doc"', 1)
    subject = _subject(
        tmp_path,
        map_(set_("/t", "A")),
        scoped,
        branch(case("A", invoke("x.api:after")), switch="/t"),
    )

    assert subject.variable("D1").notes == ("scope",)
    assert "assumption S24" in subject.text().split("### D2")[0]
    after = subject.origins("D2")
    assert [origin.kind for origin in after] == [OriginKind.SET, OriginKind.UNKNOWN]
    assert after[1].certainty is Certainty.UNKNOWN


def test_no_origin_is_matched_by_a_similar_name(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/statusCode", "A"), set_("/order/status", "A"), set_("/Status", "A")),
        branch(case("A", invoke("x.api:a")), switch="/status"),
    )

    assert subject.kinds("D1") == [OriginKind.CALLER]


def test_withheld_literals_are_not_shown(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/mode", "TOPSECRETVALUE")),
        branch(case("x", invoke("x.api:x")), switch="/mode"),
        literals=ExtractionMode.REDACT,
    )

    [origin] = subject.origins("D1")
    assert origin.value is None
    text = subject.text()
    assert "TOPSECRETVALUE" not in text
    assert "set to a value the literal policy does not show" in text


def test_label_expressions_follow_each_field(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/a", "1")),
        branch(case('%a% == "1" && %b% == "2"', invoke("x.api:both")), expressions=True),
    )

    assert [item.path.text() for item in subject.lineage.for_decision("D1")] == ["/a", "/b"]
    assert subject.kinds("D1", "/a") == [OriginKind.SET]
    assert subject.kinds("D1", "/b") == [OriginKind.CALLER]


def test_too_many_decisions_are_reported(tmp_path: Path) -> None:
    steps = [branch(case("A", invoke(f"x.api:a{i}")), switch=f"/s{i}") for i in range(205)]
    subject = _subject(tmp_path, *steps)

    assert subject.lineage.unfollowed["D201"] == ("decision_limit",)
    assert subject.lineage.for_decision("D201") == ()
    assert any("first 200 decisions" in limit for limit in subject.lineage.limits)


def test_a_transformer_output_keeps_the_earlier_value_possible(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/up", "old")),
        map_(
            set_("/mode", "x"),
            transform("pub.string:toUpper", [copy("/mode", "/inString")], [copy("/value", "/up")]),
        ),
        branch(case("A", invoke("x.api:fast")), switch="/up"),
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.TRANSFORMER]
    assert not subject.variable("D1").unique


def test_a_copy_from_one_list_element_is_possible(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/s", "v"), set_("/t", "old")),
        map_(copy("/s[1]", "/t")),
        branch(case("v", invoke("x.api:v")), switch="/t"),
    )

    origins = subject.origins("D1")
    assert [origin.kind for origin in origins] == [OriginKind.SET, OriginKind.COPY]
    assert origins[1].weak and "S20" in origins[1].rules
    assert not subject.variable("D1").unique


def test_a_decision_on_one_list_element_is_never_certain(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/items/x", "A")),
        branch(case("A", invoke("x.api:a")), switch="/items[1]/x"),
    )

    variable = subject.variable("D1")
    assert variable.notes == ("list_element",)
    assert not variable.unique
    assert "The decision tests one list element" in subject.text()


def test_a_failing_output_map_feeds_the_next_alternative(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/a", "first")),
        seq(
            invoke("ext.api:x", outputs=[copy("/q", "/a")]),
            branch(case("first", invoke("x.api:b")), switch="/a"),
            exit_on="SUCCESS",
        ),
    )

    kinds = subject.kinds("D1")
    assert OriginKind.SET in kinds and OriginKind.COPY in kinds


def test_the_facts_block_caps_the_cases(tmp_path: Path) -> None:
    cases = [case(f"V{index}", invoke(f"x.api:v{index}")) for index in range(60)]
    subject = _subject(tmp_path, branch(*cases, switch="/s"))

    text = render_decision_facts(subject.logic, subject.lineage)
    assert "  - ... and 20 more case(s)" in text
    assert "D1.c41" not in text


# --- invariants and output -----------------------------------------------------------------


def test_origins_are_deterministic_and_resolve(tmp_path: Path) -> None:
    first = _process_order(tmp_path / "a")
    second = _process_order(tmp_path / "b")

    assert first.text() == second.text()
    assert first.lineage.variables == second.lineage.variables
    for variable in first.lineage.variables:
        for origin_id in variable.origins:
            origin = first.lineage.origin(origin_id)
            for source_id in origin.source_origins:
                first.lineage.origin(source_id)
        if variable.unique:
            [only] = variable.origins
            assert not first.lineage.origin(only).weak
            assert variable.calls_in_between == ()


def test_description_facts_list_the_decisions(tmp_path: Path) -> None:
    subject = _process_order(tmp_path)
    text = render_decision_facts(subject.logic, subject.lineage)

    assert text.startswith("### Decisions")
    assert "  - D1.c1 `/request/status` is `ACTIVE`: C1 `systemA:validateOrder`" in text
    assert "  - `/request/status`: comes from: a declared input of this service" in text
    assert "  - `/validationStatus`: may come from: copied from `/result/status`" in text
    assert "calls before it may change it: C1, C2" in text
    assert "\n## " not in text


def test_the_facts_block_gains_decisions_without_changing_the_hash(tmp_path: Path) -> None:
    from wm_doc.describer import deterministic_facts, render_facts_block
    from wm_doc.effects import compute_service_facts

    pkg = FlowPackage(tmp_path / "packages", "Lineage")
    pkg.service(SUBJECT, branch(case("A", invoke("x.api:a")), switch="/s"))
    pkg.service("lineage.api:plain", invoke("x.api:a"))
    analysis = pkg.analyze()
    facts = compute_service_facts(analysis)
    by_name = {item.identity.full_name: item for item in analysis.services}

    block = render_facts_block(by_name[SUBJECT], facts[SUBJECT])
    assert "### Decisions" in block
    plain = render_facts_block(by_name["lineage.api:plain"], facts["lineage.api:plain"])
    assert "### Decisions" not in plain
    hashed = deterministic_facts(by_name[SUBJECT], facts[SUBJECT], {}, lambda _name: None)
    assert "comes from" not in hashed


def test_the_service_page_shows_origins(tmp_path: Path) -> None:
    from wm_doc.render.service_markdown import render_service_markdown

    subject = _process_order(tmp_path)
    page = render_service_markdown(subject.service)

    assert "Where `/validationStatus` comes from:" in page
    assert page.index("## Decisions") < page.index("Where `/request/status` comes from:")


@pytest.mark.slow
def test_origins_stay_fast_on_a_large_service(tmp_path: Path) -> None:
    import time

    steps = []
    for index in range(600):
        steps.append(map_(set_(f"/s{index % 50}", "A"), copy(f"/s{index % 50}", f"/t{index}")))
        steps.append(invoke(f"x.api:call{index}"))
        steps.append(
            branch(
                case("A", map_(set_(f"/s{(index + 1) % 50}", "B"))),
                case("$default", exit_("$parent")),
                switch=f"/t{index}",
            )
        )
    pkg = FlowPackage(tmp_path / "packages", "Lineage")
    pkg.service(SUBJECT, seq(*steps, name="Main", exit_on="DONE"))
    analysis = pkg.analyze()
    started = time.perf_counter()
    subject = Subject(analysis)
    text = subject.text()
    elapsed = time.perf_counter() - started

    assert len(subject.logic.decisions) == 600
    assert "Where `/t0` comes from:" in text
    assert elapsed < 10
