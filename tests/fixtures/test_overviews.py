"""Package and server overviews: deterministic package facts, overview files and site pages."""

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
from wm_doc.describer import DescribeError, DescribeOptions, DescribeOutcome, approve_docs
from wm_doc.effects import compute_service_facts
from wm_doc.ir import AnalysisResult
from wm_doc.ollama_provider import (
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.overviews import (
    NO_CALLERS,
    describe_overviews,
    overview_states,
    package_facts_text,
    server_facts_text,
    summarize_packages,
)
from wm_doc.render.package_markdown import package_page_filenames
from wm_doc.service_docs import (
    DocState,
    Narrative,
    doc_path,
    new_doc,
    overview_doc_path,
    read_doc,
    write_doc,
)

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
READ_CONFIG = "pgp.services.common:readConfig"
GET_FILE_CONTENT = "pgp.services.common:getFileContent"
PACKAGE_RE = re.compile(r"^package (\S+): ", re.MULTILINE)

Answer = Callable[[str, ProviderGenerationRequest], dict[str, Any]]


def grounded(subject: str, request: ProviderGenerationRequest) -> dict[str, Any]:
    return {
        "purpose": f"Groups the services of {subject}. It is a test answer.",
        "items": ["Reads configuration.", "Encrypts and decrypts data.", "--"],
        "entry_points": "Work enters through the services listed as entry points.",
        "systems_and_data": "Uses the files and documents listed in the facts.",
    }


class OverviewProvider:
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
        payload = self.answer(self.subject_of(request), request)
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 300},
        )

    @staticmethod
    def subject_of(request: ProviderGenerationRequest) -> str:
        prompt = request.messages[1]["content"]
        match = PACKAGE_RE.search(prompt)
        if match is not None and "Facts about one package" in prompt:
            return f"package {match.group(1)}"
        return "the server"

    def prompt_for(self, subject: str) -> str:
        for request in self.requests:
            if self.subject_of(request) == subject:
                return request.messages[1]["content"]
        raise AssertionError(f"no prompt was sent for {subject}")


@pytest.fixture(scope="module")
def samples() -> AnalysisResult:
    return analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)


def _options(tmp_path: Path, **overrides: Any) -> DescribeOptions:
    values: dict[str, Any] = {
        "model": "fake-model",
        "scan_root": SAMPLES,
        "config": load_config(None),
        "docs_dir": tmp_path / "service-docs",
        "cache_dir": tmp_path / "cache",
    }
    values.update(overrides)
    return DescribeOptions(**values)


def test_package_summary_lists_services_entries_and_own_effects(
    samples: AnalysisResult,
) -> None:
    summaries = summarize_packages(samples, compute_service_facts(samples))

    pgp = summaries["PGP"]
    assert set(summaries) == {"SampleOrders", "PGP"}
    assert len(pgp.services) == 34
    assert pgp.type_counts() == {"FLOW": 23, "Java": 11}
    assert list(pgp.services) == sorted(pgp.services, key=str.casefold)
    entries = {entry.service: entry.reached_from for entry in pgp.entries}
    assert entries[GET_FILE_CONTENT] == (NO_CALLERS,)
    # readConfig is called inside the package, so it is not an entry point.
    assert READ_CONFIG not in entries
    assert [(row.action, row.services) for row in pgp.effects] == [
        ("reads a file", (READ_CONFIG,))
    ]
    adapter = summaries["SampleOrders"]
    assert any(row.where == "Broker/UM" for row in adapter.effects)
    assert pgp.calls_into == () and pgp.called_from == ()


def test_entry_points_name_artifacts_and_callers_from_other_packages(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    _flow_service(root, "Callee", "callee.api", "work")
    _flow_service(root, "Caller", "caller.api", "start", invokes="callee.api:work")
    trigger = root / "Caller" / "ns" / "caller" / "trg" / "onEvent"
    trigger.mkdir(parents=True)
    (trigger / "node.ndf").write_text(
        '<Values version="2.0">\n'
        '  <value name="node_type">webMethods/trigger</value>\n'
        '  <value name="serviceName">caller.api:start</value>\n</Values>',
        encoding="utf-8",
    )
    analysis = analyze_path(root, load_config(None))

    summaries = summarize_packages(analysis, compute_service_facts(analysis))

    callee = {entry.service: entry.reached_from for entry in summaries["Callee"].entries}
    caller = {entry.service: entry.reached_from for entry in summaries["Caller"].entries}
    assert callee == {"callee.api:work": ("package Caller (`caller.api:start`)",)}
    assert len(caller["caller.api:start"]) == 1
    assert caller["caller.api:start"][0].endswith("`caller.trg:onEvent`")
    assert summaries["Caller"].calls_into == (("Callee", 1),)
    assert summaries["Callee"].called_from == (("Caller", 1),)
    server = server_facts_text(summaries)
    assert "  Caller -> Callee (1 calls)" in server
    assert "calls from other packages: 1" in server


def test_package_facts_hash_text_has_no_purposes_and_prompt_fits_budget(
    samples: AnalysisResult,
) -> None:
    summary = summarize_packages(samples, compute_service_facts(samples))["PGP"]
    purposes = dict.fromkeys(summary.services, "Does a documented thing.")

    plain = package_facts_text(summary)
    with_purposes = package_facts_text(summary, purposes)
    fitted = package_facts_text(summary, purposes, 2500)

    assert "purpose:" not in plain
    assert with_purposes.count("| purpose: Does a documented thing.") == len(summary.services)
    assert len(fitted) <= 2500
    assert "left out to fit the context window" in fitted
    assert fitted.startswith("package PGP: 34 services")


def test_describe_overviews_writes_package_then_server_files(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    provider = OverviewProvider()
    results, stats = describe_overviews(
        samples, ["PGP", "SampleOrders"], provider, _options(tmp_path), server=True
    )

    assert [result.service for result in results] == ["package:SampleOrders", "package:PGP", "server"]
    assert {result.outcome for result in results} == {DescribeOutcome.GENERATED}
    assert stats.counts[DescribeOutcome.GENERATED] == 3
    package_file = overview_doc_path(tmp_path / "service-docs", "PGP")
    assert package_file == tmp_path / "service-docs" / "PGP" / "_package.md"
    text = package_file.read_text(encoding="utf-8")
    assert text.startswith("---\nservice: package:PGP\npackage: PGP\nstatus: draft\n")
    assert "# Package PGP\n" in text
    for heading in ("## Purpose", "## Main capabilities", "## Entry points",
                    "## Systems and data", "## Notes", "## Facts"):
        assert heading in text
    assert "- Encrypts and decrypts data." in text
    assert "- --" not in text  # punctuation-only items are dropped
    server_text = (tmp_path / "service-docs" / "_server.md").read_text(encoding="utf-8")
    assert "# Server overview\n" in server_text
    assert "## Business areas" in server_text
    # The server prompt is written from the package overviews of the same run.
    assert "| purpose: Groups the services of package PGP." in provider.prompt_for("the server")


def test_package_prompt_uses_service_description_purposes(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    docs = tmp_path / "service-docs"
    narrative = Narrative(
        purpose="Loads the PGP settings file for the other services. More text.",
        usage="u",
        data_effects="d",
        steps=("s",),
        error_handling="e",
        designer_comment="c",
    )
    write_doc(
        doc_path(docs, "PGP", READ_CONFIG),
        new_doc(READ_CONFIG, "PGP", narrative, model="m", facts="f", facts_markdown=""),
    )
    provider = OverviewProvider()

    describe_overviews(samples, ["PGP"], provider, _options(tmp_path))

    prompt = provider.prompt_for("package PGP")
    assert f"  {READ_CONFIG} [FLOW] | purpose: Loads the PGP settings file" in prompt
    # Without a description file the purpose comes from the deterministic summary.
    assert f"  {GET_FILE_CONTENT}: {NO_CALLERS} | purpose: " in prompt


def test_overview_files_are_kept_once_approved_or_unchanged(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    options = _options(tmp_path)
    describe_overviews(samples, ["PGP"], OverviewProvider(), options)
    path = overview_doc_path(options.docs_dir, "PGP")
    first = path.read_text(encoding="utf-8")

    again, _ = describe_overviews(samples, ["PGP"], OverviewProvider(), options)
    redo, _ = describe_overviews(
        samples, ["PGP"], OverviewProvider(), _options(tmp_path, redo_drafts=True)
    )
    approved, missing = approve_docs(options.docs_dir, services=["package:PGP"])
    provider = OverviewProvider()
    protected, _ = describe_overviews(
        samples, ["PGP"], provider, _options(tmp_path, redo_drafts=True)
    )

    assert again[0].outcome is DescribeOutcome.UNCHANGED
    assert path.read_text(encoding="utf-8").startswith(first.split("status:")[0])
    assert redo[0].outcome is DescribeOutcome.CACHED
    assert (approved, missing) == (["package:PGP"], [])
    assert protected[0].outcome is DescribeOutcome.PROTECTED
    assert provider.requests == []
    doc = read_doc(path)
    assert doc is not None and doc.state() is DocState.APPROVED


def test_overview_states_report_missing_draft_and_changed_facts(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    options = _options(tmp_path)
    facts = compute_service_facts(samples)
    before = overview_states(samples, options.docs_dir, facts)

    describe_overviews(samples, ["PGP"], OverviewProvider(), options)
    approve_docs(options.docs_dir, services=["package:PGP"])
    path = overview_doc_path(options.docs_dir, "PGP")
    path.write_text(
        re.sub(r"facts_hash: \w+", "facts_hash: 0000", path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    after = overview_states(samples, options.docs_dir, facts)

    assert before == {
        "package:SampleOrders": DocState.MISSING,
        "package:PGP": DocState.MISSING,
        "server": DocState.MISSING,
    }
    assert after["package:PGP"] is DocState.STALE
    assert after["server"] is DocState.MISSING


def test_ungrounded_overview_is_rejected_and_not_written(
    samples: AnalysisResult, tmp_path: Path
) -> None:
    def invented(subject: str, request: ProviderGenerationRequest) -> dict[str, Any]:
        answer = grounded(subject, request)
        answer["purpose"] = "Sends invoices through `billing.api:sendInvoice` every night."
        return answer

    results, stats = describe_overviews(
        samples, ["PGP"], OverviewProvider(invented), _options(tmp_path)
    )

    assert results[0].outcome is DescribeOutcome.REJECTED
    assert "billing.api:sendInvoice" in (results[0].note or "")
    assert stats.retried == 1
    assert not overview_doc_path(tmp_path / "service-docs", "PGP").exists()


def test_unknown_package_is_an_error(samples: AnalysisResult, tmp_path: Path) -> None:
    with pytest.raises(DescribeError, match="Unknown package"):
        describe_overviews(samples, ["Nope"], OverviewProvider(), _options(tmp_path))


def test_package_page_filenames_disambiguate_sanitized_collisions() -> None:
    names = package_page_filenames(["A b", "A_b", "Orders"])

    assert names["Orders"] == "Orders.md"
    assert names["A b"] != names["A_b"]
    assert names["A b"].startswith("A_b__") and names["A_b"].startswith("A_b__")


def test_cli_overview_status_and_published_package_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    packages = tmp_path / "packages"
    shutil.copytree(SAMPLES / "PGP", packages / "PGP")
    monkeypatch.setattr(
        "wm_doc.cli.DESCRIBE_PROVIDER_FACTORY", lambda *args, **kwargs: OverviewProvider()
    )
    docs = tmp_path / "service-docs"
    common = ["--docs-dir", str(docs)]
    runner = CliRunner()

    no_selection = runner.invoke(app, ["overview", str(packages), "--model", "m", *common])
    both = runner.invoke(
        app, ["overview", str(packages), "--model", "m", "--all", "--package", "PGP", *common]
    )
    unknown = runner.invoke(
        app, ["overview", str(packages), "--model", "m", "--package", "Nope", *common]
    )
    written = runner.invoke(
        app,
        ["overview", str(packages), "--model", "m", "--all", "--server",
         "--cache-dir", str(tmp_path / "cache"), *common],
    )
    status = runner.invoke(app, ["status", str(packages), *common])
    approved = runner.invoke(app, ["approve", *common, "--service", "server"])
    site = tmp_path / "site"
    published = runner.invoke(app, ["analyze", str(packages), "--output", str(site), *common])

    assert no_selection.exit_code == 2
    assert both.exit_code == 2
    assert unknown.exit_code == 2
    assert "unknown package(s): Nope" in unknown.output
    assert written.exit_code == 0, written.output
    assert "[1/2] package PGP: generated" in written.output
    assert "[2/2] server overview: generated" in written.output
    assert "Wrote 2 overview(s)" in written.output
    assert status.exit_code == 0, status.output
    assert "Overviews (packages and server): 2" in status.output
    assert "without a service" not in status.output
    status_md = (docs / "STATUS.md").read_text(encoding="utf-8")
    assert "| `package:PGP` | draft |" in status_md
    assert approved.exit_code == 0, approved.output
    assert published.exit_code == 0, published.output
    page = (site / "packages" / "PGP.md").read_text(encoding="utf-8")
    assert page.startswith("# Package PGP\n\n**Draft, not reviewed.**")
    assert "### Purpose" in page
    assert "## Entry Points" in page
    assert f"| [`{READ_CONFIG}`](../services/pgp.services.common_readConfig.md) | FLOW |" in page
    index = (site / "index.md").read_text(encoding="utf-8")
    assert "## Server Overview\n\n**Approved.**" in index
    assert "| [PGP](packages/PGP.md) | 34 | 14 | Groups the services of package PGP. |" in index


def test_package_pages_are_written_without_description_files(tmp_path: Path) -> None:
    packages = tmp_path / "packages"
    shutil.copytree(SAMPLES / "PGP", packages / "PGP")
    site = tmp_path / "site"

    result = CliRunner().invoke(app, ["analyze", str(packages), "--output", str(site)])

    assert result.exit_code == 0, result.output
    page = (site / "packages" / "PGP.md").read_text(encoding="utf-8")
    assert "No package overview yet" not in page
    assert "| Services | 34 |" in page
    assert "| reads a file | file |" in page
    index = (site / "index.md").read_text(encoding="utf-8")
    assert "| Package | Services | Entry points |\n" in index
    assert "| [PGP](packages/PGP.md) | 34 | 14 |\n" in index


FLOW_NODE = """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>"""


def _flow_service(root: Path, package: str, namespace: str, name: str, invokes: str = "") -> None:
    folder = root / package / "ns" / Path(*namespace.split(".")) / name
    folder.mkdir(parents=True)
    (folder / "node.ndf").write_text(FLOW_NODE, encoding="utf-8")
    step = (
        f'<INVOKE SERVICE="{invokes}" VALIDATE-IN="$none" VALIDATE-OUT="$none"></INVOKE>'
        if invokes
        else ""
    )
    (folder / "flow.xml").write_text(
        f'<FLOW VERSION="3.0" CLEANUP="true">{step}</FLOW>', encoding="utf-8"
    )
