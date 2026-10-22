from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.business_result_schema import BusinessEnrichmentErrorCode
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.ir import AnalysisResult, FlowService
from wm_doc.ollama_provider import (
    OllamaProviderError,
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.pseudocode import load_flow_comments, render_pseudocode
from wm_doc.render.service_markdown import render_service_markdown
from wm_doc.summarizer import (
    SUMMARY_NUM_PREDICT,
    AiServiceSummary,
    SummarizeOptions,
    SummaryStatus,
    fit_facts,
    summarize_analysis,
    summary_order,
    unknown_names,
)

SAMPLES = Path("samples")
READ_CONFIG = "pgp.services.common:readConfig"
SELECT_FROM_CONFIG = "pgp.services.common:selectFromConfig"
OA_SERVICE = "oa.adapter.geographicAddressManagement:createGeographicAddressValidation"
SERVICE_LINE_RE = re.compile(r"^service (\S+)  \[", re.MULTILINE)


@pytest.fixture(scope="module")
def analysis() -> AnalysisResult:
    return analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)


@pytest.fixture(scope="module")
def services(analysis: AnalysisResult) -> dict[str, FlowService]:
    return {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }


class FakeSummaryProvider:
    """Answers with a summary naming the service, which is always grounded."""

    def __init__(
        self, answer: Callable[[str, ProviderGenerationRequest], dict[str, str]] | None = None
    ) -> None:
        self.answer = answer or (lambda name, request: _grounded_answer(name))
        self.requests: list[ProviderGenerationRequest] = []

    def check(self, model: str, *, structured_probe: bool = False) -> ProviderCheckResult:
        return ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version="test",
            model_digest="sha256:test",
            model_found=True,
            structured_output_ok=True,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.requests.append(request)
        match = SERVICE_LINE_RE.search(request.messages[1]["content"])
        assert match is not None
        payload = self.answer(match.group(1), request)
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 500},
        )


def _grounded_answer(name: str) -> dict[str, str]:
    return {
        "summary": f"Summary of `{name}`.",
        "description": f"The service `{name}` performs its documented steps.",
    }


def _options(tmp_path: Path, **overrides: Any) -> SummarizeOptions:
    values: dict[str, Any] = {
        "model": "fake-model",
        "scan_root": SAMPLES,
        "config": load_config(None),
        "cache_dir": tmp_path / "cache",
    }
    values.update(overrides)
    return SummarizeOptions(**values)


def _user_prompt_for(provider: FakeSummaryProvider, name: str) -> str:
    for request in provider.requests:
        content = request.messages[1]["content"]
        if f"service {name}  [" in content:
            return content
    raise AssertionError(f"no prompt was sent for {name}")


def test_summary_order_puts_callees_before_callers(services: dict[str, FlowService]) -> None:
    order = summary_order(services.values())

    assert sorted(order) == sorted(services)
    position = {name: index for index, name in enumerate(order)}
    for service in services.values():
        for dependency in service.unique_dependencies:
            if dependency.resolved and dependency.target_service in services:
                assert position[dependency.target_service] < position[service.identity.full_name]


def _fake_service(name: str, *targets: str) -> Any:
    dependencies = [SimpleNamespace(target_service=target, resolved=True) for target in targets]
    return SimpleNamespace(
        identity=SimpleNamespace(full_name=name), unique_dependencies=dependencies
    )


def test_summary_order_handles_cycles_deterministically() -> None:
    graph = [
        _fake_service("a:entry", "b:loopOne"),
        _fake_service("b:loopOne", "c:loopTwo"),
        _fake_service("c:loopTwo", "b:loopOne", "d:leaf"),
        _fake_service("d:leaf"),
    ]

    order = summary_order(graph)

    assert order == ["d:leaf", "b:loopOne", "c:loopTwo", "a:entry"]
    assert summary_order(list(reversed(graph))) == order


def test_pseudocode_shows_calls_literals_and_callee_notes(
    services: dict[str, FlowService],
) -> None:
    notes = {SELECT_FROM_CONFIG: "Selects the key entry for a user."}

    text = render_pseudocode(services[READ_CONFIG], notes.get)

    assert text.startswith(f"service {READ_CONFIG}  [FLOW]")
    assert "  userId: string" in text
    assert "CALL pub.file:getFile  # platform: reads a file" in text
    assert 'in: set /filename = "./packages/PGP/config/config.xml"' in text
    assert f"CALL {SELECT_FROM_CONFIG}  # Selects the key entry for a user." in text


def test_pseudocode_shows_try_catch_conditions_and_comments(
    services: dict[str, FlowService],
) -> None:
    config = load_config(None)
    oa = services[OA_SERVICE]
    oa_comments = load_flow_comments(SAMPLES, oa, config)
    oa_text = render_pseudocode(oa, lambda _: None, comments=oa_comments)
    test_service = services["pgp.test.encrypt:testEncryptAndSignString"]
    test_text = render_pseudocode(
        test_service,
        lambda _: None,
        comments=load_flow_comments(SAMPLES, test_service, config),
    )

    assert "TRY:" in oa_text and "CATCH:" in oa_text
    assert "when %input/geographicAddressValidation/status% == $null:" in oa_text
    assert "# outside the analysed packages" in oa_text
    assert "(stops at the first child that succeeds)  // Try / Catch" in test_text
    assert "// Sending a message from Alice to Bob" in test_text


def test_pseudocode_for_java_service_states_what_is_not_analysed(
    services: dict[str, FlowService],
) -> None:
    text = render_pseudocode(services["pgp.services.decrypt:decryptAndVerify"], lambda _: None)

    assert "implementation: Java" in text
    assert "reads pipeline fields: cipherTextPath" in text
    assert "(Java control flow and error handling are not analysed)" in text


def test_fit_facts_shrinks_large_services_to_the_window(
    services: dict[str, FlowService],
) -> None:
    oa = services[OA_SERVICE]

    roomy, roomy_shortened = fit_facts(oa, lambda _: None, {}, 32768)
    tight, tight_shortened = fit_facts(oa, lambda _: None, {}, 4096)

    assert not roomy_shortened
    assert tight_shortened
    assert len(tight) < len(roomy)
    assert len(tight) <= (4096 - SUMMARY_NUM_PREDICT) * 3
    assert tight.endswith("to fit the model's context window)")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Reads the config with `pgp.services.common:readConfig`.", []),
        ("It returns the KeyConfig document for a userId, e.g. via XML.", []),
        ("It copies /body/string into /xmldata.", []),
        ("It looks up user IDs and URLs, then handles I/O errors.", []),
        ("It then calls pgp.services.common:deleteConfig.", ["pgp.services.common:deleteConfig"]),
        ("It stores the result in customerAccount.", ["customerAccount"]),
    ],
)
def test_unknown_names_flags_only_names_missing_from_facts(
    services: dict[str, FlowService], text: str, expected: list[str]
) -> None:
    facts = render_pseudocode(services[READ_CONFIG], lambda _: None)

    assert unknown_names(text, facts) == expected


def test_summarize_passes_callee_summaries_and_uses_cache(
    analysis: AnalysisResult, tmp_path: Path
) -> None:
    provider = FakeSummaryProvider()

    bundle, stats = summarize_analysis(analysis, provider, _options(tmp_path))

    by_service = bundle.by_service()
    assert stats.generated == len(by_service) and stats.cached == 0
    assert all(item.status is SummaryStatus.OK for item in by_service.values())
    caller_prompt = _user_prompt_for(provider, READ_CONFIG)
    assert f"CALL {SELECT_FROM_CONFIG}  # Summary of `{SELECT_FROM_CONFIG}`." in caller_prompt
    assert all(request.num_ctx == bundle.num_ctx for request in provider.requests)

    second_provider = FakeSummaryProvider()
    second, second_stats = summarize_analysis(analysis, second_provider, _options(tmp_path))

    assert second_provider.requests == []
    assert second_stats.cached == len(by_service)
    assert second == bundle


def test_changed_callee_summary_invalidates_only_its_callers(
    analysis: AnalysisResult, tmp_path: Path
) -> None:
    first, _ = summarize_analysis(analysis, FakeSummaryProvider(), _options(tmp_path))
    callee_key = first.by_service()[SELECT_FROM_CONFIG].input_sha256
    (tmp_path / "cache" / callee_key[:2] / f"{callee_key}.json").unlink()

    def callee_changes(name: str, request: ProviderGenerationRequest) -> dict[str, str]:
        if name == SELECT_FROM_CONFIG:
            return {"summary": f"Changed `{name}`.", "description": ""}
        return _grounded_answer(name)

    provider = FakeSummaryProvider(callee_changes)
    second, _ = summarize_analysis(analysis, provider, _options(tmp_path))

    regenerated = set()
    for request in provider.requests:
        match = SERVICE_LINE_RE.search(request.messages[1]["content"])
        assert match is not None
        regenerated.add(match.group(1))
    assert SELECT_FROM_CONFIG in regenerated
    assert READ_CONFIG in regenerated
    assert "pgp.services.keys:listEncryptionAlgorithms" not in regenerated
    assert f"# Changed `{SELECT_FROM_CONFIG}`." in _user_prompt_for(provider, READ_CONFIG)
    assert second.by_service()[READ_CONFIG].input_sha256 != (
        first.by_service()[READ_CONFIG].input_sha256
    )


def test_ungrounded_answer_is_retried_then_rejected(
    analysis: AnalysisResult, tmp_path: Path
) -> None:
    def invents_names(name: str, request: ProviderGenerationRequest) -> dict[str, str]:
        if name == SELECT_FROM_CONFIG:
            return {"summary": "Loads data from customerAccountTable.", "description": ""}
        return _grounded_answer(name)

    provider = FakeSummaryProvider(invents_names)

    bundle, stats = summarize_analysis(analysis, provider, _options(tmp_path, no_cache=True))

    rejected = bundle.by_service()[SELECT_FROM_CONFIG]
    assert rejected.status is SummaryStatus.REJECTED
    assert rejected.summary is None
    assert "`customerAccountTable`" in (rejected.note or "")
    assert stats.retried >= 1 and stats.rejected == 1
    retry = [r for r in provider.requests if len(r.messages) == 4]
    assert retry and retry[0].messages[2]["role"] == "assistant"
    assert "customerAccountTable" in retry[0].messages[3]["content"]
    caller_prompt = _user_prompt_for(provider, READ_CONFIG)
    assert f"CALL {SELECT_FROM_CONFIG}  # no description available" in caller_prompt


def test_provider_error_marks_one_service_failed_and_continues(
    analysis: AnalysisResult, tmp_path: Path
) -> None:
    def fails_once(name: str, request: ProviderGenerationRequest) -> dict[str, str]:
        if name == READ_CONFIG:
            raise OllamaProviderError(BusinessEnrichmentErrorCode.TIMEOUT, "Timed out.")
        return _grounded_answer(name)

    bundle, stats = summarize_analysis(
        analysis, FakeSummaryProvider(fails_once), _options(tmp_path, no_cache=True)
    )

    failed = bundle.by_service()[READ_CONFIG]
    assert failed.status is SummaryStatus.FAILED
    assert "Timed out" in (failed.note or "")
    assert stats.failed == 1
    assert stats.generated == len(bundle.summaries) - 1


def test_service_page_ai_section(services: dict[str, FlowService]) -> None:
    service = services[READ_CONFIG]
    plain = render_service_markdown(service)
    ok = AiServiceSummary(
        service=READ_CONFIG,
        status=SummaryStatus.OK,
        summary="Reads the PGP key configuration for a user.",
        description="# Not a heading. It parses config.xml.",
        facts_shortened=True,
        input_sha256="0" * 64,
    )
    rejected = ok.model_copy(
        update={"status": SummaryStatus.REJECTED, "summary": None, "note": "it named `x`."}
    )

    with_ai = render_service_markdown(service, ai_summary=ok, ai_model="qwen-test")
    with_rejection = render_service_markdown(service, ai_summary=rejected, ai_model="qwen-test")

    assert "## AI Description" not in plain
    assert with_ai.replace(_ai_block(with_ai), "") == plain
    assert "**In short:** Reads the PGP key configuration for a user.\n" in with_ai
    assert "(`qwen-test`)" in with_ai
    assert "> Some detail was left out to fit the model's context window.\n\n" in with_ai
    assert "\n\\# Not a heading." in with_ai
    assert "No AI description is shown: it named `x`.\n" in with_rejection


def _ai_block(page: str) -> str:
    start = page.index("## AI Description")
    return page[start : page.index("## Identity")]


def test_summarize_cli_writes_ai_pages_and_analyze_removes_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "wm_doc.cli.SUMMARY_PROVIDER_FACTORY",
        lambda *args, **kwargs: FakeSummaryProvider(),
    )
    output = tmp_path / "docs"

    result = CliRunner().invoke(
        app,
        [
            "summarize",
            str(SAMPLES),
            "--output",
            str(output),
            "--model",
            "fake-model",
            "--cache-dir",
            str(tmp_path / "cache"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "AI service descriptions:" in result.output
    overview = (output / "ai-summaries.md").read_text(encoding="utf-8")
    assert f"[`{READ_CONFIG}`](services/pgp.services.common_readConfig.md)" in overview
    assert "[AI service descriptions (not reviewed)](ai-summaries.md)" in (
        output / "index.md"
    ).read_text(encoding="utf-8")
    page = (output / "services" / "pgp.services.common_readConfig.md").read_text(encoding="utf-8")
    assert "## AI Description" in page
    payload = json.loads((output / "ai-summaries.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == "service-summaries.v1"
    assert payload["generation_order"].index(SELECT_FROM_CONFIG) < payload[
        "generation_order"
    ].index(READ_CONFIG)

    plain = CliRunner().invoke(app, ["analyze", str(SAMPLES), "--output", str(output)])

    assert plain.exit_code == 0, plain.output
    assert not (output / "ai-summaries.md").exists()
    assert not (output / "ai-summaries.json").exists()
    page = (output / "services" / "pgp.services.common_readConfig.md").read_text(encoding="utf-8")
    assert "## AI Description" not in page
