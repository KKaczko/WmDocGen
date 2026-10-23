"""M12 phase 4: per-service description files and the describe/approve/status workflow."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import load_config
from wm_doc.describer import (
    DescribeOptions,
    DescribeOutcome,
    approve_docs,
    collect_states,
    current_facts_hashes,
    describe_services,
    export_designer_comments,
    narrative_from_payload,
)
from wm_doc.ir import AnalysisResult
from wm_doc.ollama_provider import (
    OllamaProviderError,
    ProviderCheckResult,
    ProviderErrorCode,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.service_docs import DocState, DocStatus, doc_path, parse_doc, read_doc

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
READ_CONFIG = "pgp.services.common:readConfig"
SELECT_FROM_CONFIG = "pgp.services.common:selectFromConfig"
SERVICE_LINE_RE = re.compile(r"^service (\S+)  \[", re.MULTILINE)

Answer = Callable[[str, ProviderGenerationRequest], dict[str, Any]]


def grounded(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
    return {
        "purpose": f"Handles the work of `{name}`. It is a test answer.",
        "usage": "Used by the callers listed in the facts.",
        "data_effects": "Returns the documents in its signature.",
        "steps": ["Reads the input.", "Calls the listed services."],
        "error_handling": "Not shown in the facts.",
        "designer_comment": f"Service {name}: performs its documented steps.",
    }


class FakeProvider:
    def __init__(self, answer: Answer = grounded) -> None:
        self.answer = answer
        self.requests: list[ProviderGenerationRequest] = []

    def check(self, model: str) -> ProviderCheckResult:
        return ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version="test",
            model_digest="sha256:test",
            model_found=True,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.requests.append(request)
        payload = self.answer(self.service_of(request), request)
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )

    @staticmethod
    def service_of(request: ProviderGenerationRequest) -> str:
        match = SERVICE_LINE_RE.search(request.messages[1]["content"])
        assert match is not None
        return match.group(1)

    def prompt_for(self, name: str) -> str:
        for request in self.requests:
            if self.service_of(request) == name:
                return request.messages[1]["content"]
        raise AssertionError(f"no prompt was sent for {name}")

    def described(self) -> list[str]:
        return [self.service_of(request) for request in self.requests]


@pytest.fixture(scope="module")
def samples() -> AnalysisResult:
    return analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)


def _options(tmp_path: Path, root: Path = SAMPLES, **overrides: Any) -> DescribeOptions:
    values: dict[str, Any] = {
        "model": "fake-model",
        "scan_root": root,
        "config": load_config(None),
        "docs_dir": tmp_path / "service-docs",
        "cache_dir": tmp_path / "cache",
    }
    values.update(overrides)
    return DescribeOptions(**values)


def _doc_file(tmp_path: Path, service: str, package: str = "PGP") -> Path:
    return doc_path(tmp_path / "service-docs", package, service)


def test_describe_writes_a_draft_file_with_narrative_and_facts(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    results, stats = describe_services(samples, [READ_CONFIG], FakeProvider(), _options(tmp_path))

    path = _doc_file(tmp_path, READ_CONFIG)
    assert results[0].outcome is DescribeOutcome.GENERATED
    assert path == tmp_path / "service-docs" / "PGP" / "pgp" / "services" / "common" / (
        "readConfig.md"
    )
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nservice: pgp.services.common:readConfig\npackage: PGP\n")
    assert "status: draft\n" in text
    for heading in (
        "## Purpose",
        "## Usage",
        "## What it does to data",
        "## Main steps",
        "## Error handling",
        "## Designer comment",
        "## Notes",
        "### Data and systems touched",
    ):
        assert heading in text
    doc = parse_doc(text)
    assert doc is not None
    assert doc.state() is DocState.DRAFT
    assert doc.purpose_line() == f"Handles the work of `{READ_CONFIG}`."
    assert doc.designer_comment() == f"Service {READ_CONFIG}: performs its documented steps."
    assert "filename `./packages/PGP/config/config.xml`" in doc.facts_markdown
    assert stats.counts[DescribeOutcome.GENERATED] == 1


def test_punctuation_only_steps_are_dropped() -> None:
    payload = grounded(READ_CONFIG, None)  # type: ignore[arg-type]
    payload["steps"] = ["Reads the input.", ",", " - ", "Calls the listed services."]

    narrative = narrative_from_payload(payload)

    assert narrative is not None
    assert narrative.steps == ("Reads the input.", "Calls the listed services.")


def test_with_callees_describes_callees_first_and_passes_their_purpose(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    provider = FakeProvider()

    describe_services(
        samples, [READ_CONFIG, SELECT_FROM_CONFIG], provider, _options(tmp_path)
    )

    assert provider.described() == [SELECT_FROM_CONFIG, READ_CONFIG]
    assert (
        f"CALL {SELECT_FROM_CONFIG}  # Handles the work of `{SELECT_FROM_CONFIG}`."
        in provider.prompt_for(READ_CONFIG)
    )


def test_rerun_keeps_unchanged_drafts_without_calling_the_model(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    describe_services(samples, [READ_CONFIG], FakeProvider(), _options(tmp_path))
    before = _doc_file(tmp_path, READ_CONFIG).read_bytes()
    provider = FakeProvider()

    results, _ = describe_services(samples, [READ_CONFIG], provider, _options(tmp_path))

    assert results[0].outcome is DescribeOutcome.UNCHANGED
    assert provider.requests == []
    assert _doc_file(tmp_path, READ_CONFIG).read_bytes() == before


def test_edited_narrative_and_notes_are_never_overwritten(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    describe_services(samples, [READ_CONFIG], FakeProvider(), _options(tmp_path))
    path = _doc_file(tmp_path, READ_CONFIG)
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        f"Handles the work of `{READ_CONFIG}`.", "Loads the PGP key settings for one user."
    ).replace(
        "<!-- Your notes. wm-doc never changes this section. -->", "Owner: integration team."
    )
    path.write_text(text, encoding="utf-8")
    provider = FakeProvider()

    results, _ = describe_services(
        samples, [READ_CONFIG], provider, _options(tmp_path, redo_drafts=True)
    )

    doc = read_doc(path)
    assert results[0].outcome is DescribeOutcome.PROTECTED
    assert provider.requests == []
    assert doc is not None and doc.state() is DocState.EDITED
    assert doc.purpose_line() == "Loads the PGP key settings for one user."
    assert doc.notes == "Owner: integration team."


def test_redo_drafts_regenerates_but_keeps_notes(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    describe_services(samples, [READ_CONFIG], FakeProvider(), _options(tmp_path))
    path = _doc_file(tmp_path, READ_CONFIG)
    doc = read_doc(path)
    assert doc is not None
    doc.notes = "Owner: integration team."
    path.write_text(doc.render(), encoding="utf-8")
    provider = FakeProvider()

    results, _ = describe_services(
        samples, [READ_CONFIG], provider, _options(tmp_path, redo_drafts=True, refresh=True)
    )

    assert results[0].outcome is DescribeOutcome.GENERATED
    assert provider.described() == [READ_CONFIG]
    regenerated = read_doc(path)
    assert regenerated is not None and regenerated.notes == "Owner: integration team."


def test_approved_callee_text_is_used_as_caller_context(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    describe_services(samples, [SELECT_FROM_CONFIG], FakeProvider(), _options(tmp_path))
    callee = _doc_file(tmp_path, SELECT_FROM_CONFIG)
    callee.write_text(
        callee.read_text(encoding="utf-8").replace(
            f"Handles the work of `{SELECT_FROM_CONFIG}`.",
            "Picks the key settings for one user from the PGP configuration.",
        ),
        encoding="utf-8",
    )
    approved, missing = approve_docs(tmp_path / "service-docs", services=[SELECT_FROM_CONFIG])
    provider = FakeProvider()

    describe_services(samples, [READ_CONFIG], provider, _options(tmp_path))

    assert approved == [SELECT_FROM_CONFIG] and missing == []
    assert (
        f"CALL {SELECT_FROM_CONFIG}  # Picks the key settings for one user from the PGP "
        "configuration." in provider.prompt_for(READ_CONFIG)
    )


def test_rejected_answer_writes_no_file_and_keeps_existing_one(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    def invents(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        answer = grounded(name, request)
        answer["data_effects"] = "Writes rows to customerAccountTable."
        return answer

    results, stats = describe_services(
        samples, [READ_CONFIG], FakeProvider(invents), _options(tmp_path)
    )

    assert results[0].outcome is DescribeOutcome.REJECTED
    assert "`customerAccountTable`" in (results[0].note or "")
    assert stats.retried == 1
    assert not _doc_file(tmp_path, READ_CONFIG).exists()


def test_unsafe_answer_gets_one_corrective_retry(samples: AnalysisResult, tmp_path: Path) -> None:
    calls: list[str] = []

    def leaks_once(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        calls.append(name)
        answer = grounded(name, request)
        if len(calls) == 1:
            answer["data_effects"] = "Reads jdbc:oracle:thin:@dbhost:1521:ORCL."
        return answer

    provider = FakeProvider(leaks_once)
    results, stats = describe_services(samples, [READ_CONFIG], provider, _options(tmp_path))

    assert results[0].outcome is DescribeOutcome.GENERATED
    assert stats.retried == 1
    assert "cannot be published (connection string)" in provider.requests[1].messages[-1][
        "content"
    ]
    assert "jdbc:oracle" not in _doc_file(tmp_path, READ_CONFIG).read_text(encoding="utf-8")


def test_answer_that_stays_unsafe_is_rejected(samples: AnalysisResult, tmp_path: Path) -> None:
    def leaks(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        answer = grounded(name, request)
        answer["data_effects"] = "Reads jdbc:mysql://dbhost/orders."
        return answer

    results, stats = describe_services(
        samples, [READ_CONFIG], FakeProvider(leaks), _options(tmp_path)
    )

    assert results[0].outcome is DescribeOutcome.REJECTED
    assert results[0].note == "the answer failed the disclosure scan: connection string"
    assert stats.retried == 1
    assert not _doc_file(tmp_path, READ_CONFIG).exists()


def _invents(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
    answer = grounded(name, request)
    answer["data_effects"] = "Writes rows to customerAccountTable."
    return answer


def test_keep_unverified_writes_a_marked_draft(samples: AnalysisResult, tmp_path: Path) -> None:
    from wm_doc.render.service_markdown import doc_badge

    options = _options(tmp_path, keep_unverified=True)
    provider = FakeProvider(_invents)

    results, stats = describe_services(samples, [READ_CONFIG], provider, options)

    assert results[0].outcome is DescribeOutcome.UNVERIFIED
    assert stats.counts[DescribeOutcome.UNVERIFIED] == 1
    path = _doc_file(tmp_path, READ_CONFIG)
    text = path.read_text(encoding="utf-8")
    assert "unverified_names:\n- customerAccountTable\n" in text
    assert (
        "> **Unverified draft:** the model used names that are not in the facts: "
        "`customerAccountTable`. Check them before approving."
    ) in text
    doc = read_doc(path)
    assert doc is not None and doc.state() is DocState.DRAFT
    assert doc.purpose_line() == f"Handles the work of `{READ_CONFIG}`."
    assert "unverified names" in doc_badge(doc)

    # Not cached: the next run asks the model again instead of keeping the draft.
    describe_services(samples, [READ_CONFIG], provider, options)
    assert len(provider.requests) == 4

    approve_docs(tmp_path / "service-docs", services=[READ_CONFIG])
    approved = path.read_text(encoding="utf-8")
    assert "unverified" not in approved.casefold()
    assert "status: approved" in approved


def test_keep_unverified_never_keeps_an_unsafe_answer(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    def leaks(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        answer = grounded(name, request)
        answer["data_effects"] = "Reads jdbc:mysql://dbhost/orders."
        return answer

    results, _ = describe_services(
        samples, [READ_CONFIG], FakeProvider(leaks), _options(tmp_path, keep_unverified=True)
    )

    assert results[0].outcome is DescribeOutcome.REJECTED
    assert not _doc_file(tmp_path, READ_CONFIG).exists()


def test_verified_answer_replaces_an_unverified_draft(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    options = _options(tmp_path, keep_unverified=True)
    describe_services(samples, [READ_CONFIG], FakeProvider(_invents), options)

    results, _ = describe_services(samples, [READ_CONFIG], FakeProvider(), options)

    assert results[0].outcome is DescribeOutcome.GENERATED
    text = _doc_file(tmp_path, READ_CONFIG).read_text(encoding="utf-8")
    assert "unverified" not in text.casefold()


def test_provider_failure_is_reported_per_service(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    def fails(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        if name == SELECT_FROM_CONFIG:
            raise OllamaProviderError(ProviderErrorCode.TIMEOUT, "Timed out.")
        return grounded(name, request)

    results, _ = describe_services(
        samples, [READ_CONFIG, SELECT_FROM_CONFIG], FakeProvider(fails), _options(tmp_path)
    )

    outcomes = {result.service: result.outcome for result in results}
    assert outcomes == {
        SELECT_FROM_CONFIG: DescribeOutcome.FAILED,
        READ_CONFIG: DescribeOutcome.GENERATED,
    }


def test_interrupted_run_resumes_from_written_files(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    def interrupt(name: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        if name == READ_CONFIG:
            raise KeyboardInterrupt
        return grounded(name, request)

    with pytest.raises(KeyboardInterrupt):
        describe_services(
            samples, [READ_CONFIG, SELECT_FROM_CONFIG], FakeProvider(interrupt), _options(tmp_path)
        )
    provider = FakeProvider()
    results, _ = describe_services(
        samples, [READ_CONFIG, SELECT_FROM_CONFIG], provider, _options(tmp_path)
    )

    assert {r.service: r.outcome for r in results} == {
        SELECT_FROM_CONFIG: DescribeOutcome.UNCHANGED,
        READ_CONFIG: DescribeOutcome.GENERATED,
    }
    assert provider.described() == [READ_CONFIG]


def _synthetic(root: Path, extra_step: str = "") -> Path:
    service_dir = root / "Orders" / "ns" / "orders" / "api" / "createOrder"
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "node.ndf").write_text(
        '<Values version="2.0">\n  <value name="svc_type">flow</value>\n</Values>',
        encoding="utf-8",
    )
    (service_dir / "flow.xml").write_text(
        '<FLOW VERSION="3.0"><INVOKE SERVICE="pub.publish:publish"/>'
        f"{extra_step}</FLOW>",
        encoding="utf-8",
    )
    return root


def test_approved_description_is_flagged_when_facts_change(tmp_path: Path) -> None:
    root = _synthetic(tmp_path / "packages")
    options = _options(tmp_path, root=root)
    describe_services(analyze_path(root, load_config(None)), ["orders.api:createOrder"],
                      FakeProvider(), options)
    approve_docs(tmp_path / "service-docs", package="Orders")
    _synthetic(root, '<INVOKE SERVICE="pub.client:http"/>')
    analysis = analyze_path(root, load_config(None))
    provider = FakeProvider()

    results, _ = describe_services(analysis, ["orders.api:createOrder"], provider, options)

    path = doc_path(tmp_path / "service-docs", "Orders", "orders.api:createOrder")
    doc = read_doc(path)
    assert results[0].outcome is DescribeOutcome.PROTECTED
    assert provider.requests == []
    assert doc is not None and doc.status is DocStatus.APPROVED
    assert doc.state() is DocState.STALE
    assert "calls an external HTTP endpoint" in doc.facts_markdown
    hashes = current_facts_hashes(analysis, root, load_config(None))
    states = collect_states(analysis, tmp_path / "service-docs", hashes)
    assert states["orders.api:createOrder"] == ("Orders", DocState.STALE)


def test_export_comments_includes_approved_only_by_default(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    describe_services(
        samples, [READ_CONFIG, SELECT_FROM_CONFIG], FakeProvider(), _options(tmp_path)
    )
    approve_docs(tmp_path / "service-docs", services=[READ_CONFIG])

    approved_only = export_designer_comments(tmp_path / "service-docs", tmp_path / "out1")
    with_drafts = export_designer_comments(
        tmp_path / "service-docs", tmp_path / "out2", include_drafts=True
    )

    assert approved_only == {"PGP": 1}
    assert with_drafts == {"PGP": 2}
    text = (tmp_path / "out1" / "PGP.txt").read_text(encoding="utf-8")
    assert f"[{READ_CONFIG}] (approved)" in text
    assert f"Service {READ_CONFIG}: performs its documented steps." in text
    assert SELECT_FROM_CONFIG not in text


def test_cli_workflow_describe_approve_status_and_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packages = tmp_path / "packages"
    shutil.copytree(SAMPLES / "PGP", packages / "PGP")
    monkeypatch.setattr(
        "wm_doc.cli.DESCRIBE_PROVIDER_FACTORY", lambda *args, **kwargs: FakeProvider()
    )
    docs = tmp_path / "service-docs"
    runner = CliRunner()
    common = ["--docs-dir", str(docs)]

    bad = runner.invoke(
        app, ["describe", str(packages), "--model", "m", "--all", "--package", "PGP"]
    )
    described = runner.invoke(
        app,
        ["describe", str(packages), "--model", "m", "--service", READ_CONFIG, "--with-callees",
         "--cache-dir", str(tmp_path / "cache"), *common],
    )
    approved = runner.invoke(app, ["approve", *common, "--service", READ_CONFIG])
    status = runner.invoke(app, ["status", str(packages), *common])
    published = runner.invoke(app, ["analyze", str(packages), "--output", str(tmp_path / "site"),
                                    *common])

    assert bad.exit_code == 2
    assert described.exit_code == 0, described.output
    assert f"{SELECT_FROM_CONFIG}: generated" in described.output
    assert "- new drafts: 2 generated, 0 from cache" in described.output
    assert approved.exit_code == 0, approved.output
    assert f"approved: {READ_CONFIG}" in approved.output
    assert status.exit_code == 0, status.output
    assert "- approved: 1" in status.output
    assert "- draft: 1" in status.output
    status_md = (docs / "STATUS.md").read_text(encoding="utf-8")
    assert "| PGP |" in status_md
    assert published.exit_code == 0, published.output
    site = tmp_path / "site"
    page = (site / "services" / "pgp.services.common_readConfig.md").read_text(encoding="utf-8")
    assert "## Description\n\n> **Approved.**" in page
    assert page.count("## Description") == 1
    assert "## Designer Comment" in page
    assert "### Purpose" in page
    callee_page = (site / "services" / "pgp.services.common_selectFromConfig.md").read_text(
        encoding="utf-8"
    )
    assert "**Draft, not reviewed.** Written by `m`" in callee_page
    catalogue = (site / "service-catalogue.md").read_text(encoding="utf-8")
    assert "| approved | 1 |" in catalogue
    assert "[Service catalogue (descriptions and review status)](service-catalogue.md)" in (
        site / "index.md"
    ).read_text(encoding="utf-8")
