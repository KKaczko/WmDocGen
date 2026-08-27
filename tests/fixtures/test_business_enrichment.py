from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from wm_doc.business_enrichment import _normalize_section
from wm_doc.business_result_schema import (
    BusinessClaimSection,
    BusinessDraftClaim,
    BusinessDraftItem,
    BusinessEnrichmentErrorCode,
    business_draft_json_schema,
)
from wm_doc.cli import app
from wm_doc.ollama_provider import (
    OllamaProviderError,
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    validate_ollama_url,
)


class FakeBusinessProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.check_count = 0
        self.generate_count = 0
        self.last_request: ProviderGenerationRequest | None = None

    def check(self, model: str, *, structured_probe: bool = False) -> ProviderCheckResult:
        self.check_count += 1
        return ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version="0.0.test",
            model_digest="sha256:testdigest",
            model_found=True,
            structured_output_ok=structured_probe,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.generate_count += 1
        self.last_request = request
        return ProviderGenerationResult(
            content=self.content,
            provider_kind="ollama",
            model=request.model,
            ollama_version="0.0.test",
            model_digest="sha256:testdigest",
            metrics={"eval_count": 7},
            attempts=1,
        )


def test_enrich_business_writes_validated_result_and_uses_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    payload = _business_draft_payload(context)
    provider = FakeBusinessProvider(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )
    output = tmp_path / "business"
    output.mkdir()
    (output / "keep.txt").write_text("do not touch", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    first = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(output),
            "--model",
            "fake-model",
            "--language",
            "pl",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert first.exit_code == 0, first.output
    assert "cache: miss" in first.output
    assert provider.generate_count == 1
    result_text = (output / "result.json").read_text(encoding="utf-8")
    result = json.loads(result_text)
    assert result["schema_version"] == "business-result.v2"
    assert result["context_id"] == context["context_id"]
    assert result["source_context_sha256"]
    assert result["language"] == "pl"
    assert result["claims"][0]["claim_id"].startswith("claim_")
    assert result["claims"][0]["evidence_ids"][0] in {
        item["evidence_id"] for item in context["evidence"]
    }
    assert result["claims"][0]["confidence"] == "SUPPORTED"
    assert result["claims"][1]["confidence"] == "INFERRED"
    assert result["validation"]["draft_schema_version"] == "business-draft.v2"
    assert result["provenance"]["draft_schema_version"] == "business-draft.v2"
    assert "fake-model" in result_text
    assert "http://localhost" not in result_text
    assert "Business context JSON" not in result_text
    assert "inferences" not in result
    assert (output / "index.md").exists()
    assert (output / "keep.txt").read_text(encoding="utf-8") == "do not touch"
    first_json = (output / "result.json").read_bytes()
    first_markdown = (output / "index.md").read_bytes()

    second = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(output),
            "--model",
            "fake-model",
            "--language",
            "pl",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert second.exit_code == 0, second.output
    assert "cache: hit" in second.output
    assert provider.generate_count == 1
    assert (output / "result.json").read_bytes() == first_json
    assert (output / "index.md").read_bytes() == first_markdown
    assert provider.last_request is not None
    assert provider.last_request.schema["title"] == "BusinessDraft"
    assert "result_id" not in json.dumps(provider.last_request.schema)
    assert provider.last_request.messages[0]["role"] == "system"


def test_enrich_business_drops_claims_citing_unknown_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    payload = _business_draft_payload(context)
    payload["claims"][0]["evidence_ids"] = ["evidence_missing"]
    provider = FakeBusinessProvider(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    # A bad citation no longer discards the whole generation. The offending claim is
    # dropped and reported; the draft's other item (a valid inference) still publishes.
    assert result.exit_code == 0, result.output
    published = _read_json(tmp_path / "business" / "result.json")
    assert [item["confidence"] for item in published["claims"]] == ["INFERRED"]
    assert "UNKNOWN_EVIDENCE_CLAIM_DISCARDED" in {
        item["code"] for item in published["limitations"]
    }
    # The drop notice names the bogus id for auditability; no claim may cite it.
    assert "evidence_missing" not in json.dumps(published["claims"])


def test_enrich_business_rejects_unsafe_model_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    payload = _business_draft_payload(context)
    payload["claims"][0]["text"] = "Uses password=super-secret-marker"
    provider = FakeBusinessProvider(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    assert result.exit_code == 1
    assert BusinessEnrichmentErrorCode.DISCLOSURE_FAILED.value in result.output
    assert "super-secret-marker" not in result.output
    assert not (tmp_path / "business" / "result.json").exists()


def test_enrich_business_rejects_invalid_draft_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    provider = FakeBusinessProvider("not json")
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    assert result.exit_code == 1
    assert BusinessEnrichmentErrorCode.DRAFT_INVALID.value in result.output
    assert "not json" not in result.output


def test_enrich_business_rejects_final_metadata_in_draft(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    payload = _business_draft_payload(context)
    payload["result_id"] = "business_result_model_owned"
    payload["status"] = "COMPLETE"
    provider = FakeBusinessProvider(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    assert result.exit_code == 1
    assert BusinessEnrichmentErrorCode.DRAFT_INVALID.value in result.output


def test_enrich_business_requires_evidence_for_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    payload = _business_draft_payload(context)
    payload["inferences"][0]["evidence_ids"] = []
    provider = FakeBusinessProvider(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    assert result.exit_code == 1
    # business-draft.v2 requires at least one evidence id per claim, so an uncited
    # inference can no longer be expressed and is rejected as a malformed draft.
    assert BusinessEnrichmentErrorCode.DRAFT_INVALID.value in result.output


def test_enrich_business_normalizes_unknown_section_and_duplicates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    evidence_id = _safe_evidence_id(context)
    payload = {
        "claims": [
            {
                "text": "Opis wspierany dowodem.",
                "section": "general",
                "evidence_ids": [evidence_id, evidence_id],
            },
            {
                "text": "Opis wspierany dowodem.",
                "section": "general",
                "evidence_ids": [evidence_id],
            },
        ]
    }
    provider = FakeBusinessProvider(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _read_json(tmp_path / "business" / "result.json")
    assert len(output["claims"]) == 1
    assert output["claims"][0]["section"] == "general"
    assert output["claims"][0]["evidence_ids"] == [evidence_id]


def test_enrich_business_preserves_context_limitations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    context["status"] = "PARTIAL"
    context["status_reasons"] = ["BUSINESS_CONTEXT_PARTIAL_SCOPE"]
    context["limitations"] = [
        {
            "code": "SCOPE_DEPTH_LIMIT_REACHED",
            "summary": "Depth-limited publication stopped traversal.",
            "evidence_ids": [],
        }
    ]
    context_path.write_text(
        json.dumps(context, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    provider = FakeBusinessProvider(json.dumps({"claims": []}, ensure_ascii=False))
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(
        app,
        [
            "enrich-business",
            "--context",
            str(context_path),
            "--output",
            str(tmp_path / "business"),
            "--model",
            "fake-model",
            "--no-cache",
        ],
    )

    assert result.exit_code == 0, result.output
    output = _read_json(tmp_path / "business" / "result.json")
    assert output["status"] == "PARTIAL"
    limitation_codes = {item["code"] for item in output["limitations"]}
    assert "SCOPE_DEPTH_LIMIT_REACHED" in limitation_codes
    assert "BUSINESS_CONTEXT_PARTIAL_SCOPE" in limitation_codes
    assert "BUSINESS_ENRICHMENT_CONTEXT_PARTIAL" in limitation_codes


def test_ollama_test_uses_structured_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = FakeBusinessProvider("{}")
    monkeypatch.setattr(
        "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
        lambda *args, **kwargs: provider,
    )

    result = CliRunner().invoke(app, ["ollama-test", "--model", "fake-model"])

    assert result.exit_code == 0, result.output
    assert "structured JSON supported: yes" in result.output
    assert "M8c draft contract supported: yes" in result.output
    assert provider.check_count == 1
    assert provider.generate_count == 0


def test_enrich_business_discards_claims_naming_ungrounded_identifiers(
    tmp_path: Path,
) -> None:
    """Regression for a real qwen3.5:4b run that invented a surname for a document type.

    The model emitted "Korzeniewska (KeyConfig) ..." while citing valid evidence ids, and
    the published result labelled every such claim CONFIRMED. Citations were checked for
    existence but claim text was never checked against the evidence it cited.
    """
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    evidence_id = _document_evidence_id(context)
    hallucinated = {
        "claims": [
            {
                "section": "general",
                "text": "Korzeniewska (KeyConfig) contains the fields userId, pub and sec.",
                "evidence_ids": [evidence_id],
            },
            {
                "section": "general",
                "text": "The service calls AcmeBillingGateway to settle the request.",
                "evidence_ids": [evidence_id],
            },
        ],
        "inferences": [
            {
                "section": "general",
                "text": "Korzeniewska (KeyConfig) contains the field sec.",
                "evidence_ids": [evidence_id],
            }
        ],
        "unknowns": [],
        "limitations": [],
    }
    provider = FakeBusinessProvider(json.dumps(hallucinated, ensure_ascii=False))
    output = tmp_path / "business"

    result = _invoke_enrichment(provider, context_path, output, tmp_path / "cache")

    assert result.exit_code == 0, result.output
    published = _read_json(output / "result.json")
    assert published["claims"] == []
    discarded = [
        item
        for item in published["limitations"]
        if item["code"] == "UNGROUNDED_CLAIM_DISCARDED"
    ]
    assert len(discarded) == 1
    assert "Korzeniewska" in discarded[0]["summary"]
    assert "AcmeBillingGateway" in discarded[0]["summary"]
    assert "CONFIRMED" not in json.dumps(published)


def test_enrich_business_keeps_claims_grounded_in_cited_evidence(tmp_path: Path) -> None:
    """Prose, acronyms and identifiers present in the cited evidence must survive."""
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    evidence_id = _safe_evidence_id(context)
    grounded = {
        "claims": [
            {
                "section": "general",
                "text": "Reads a configuration file and returns the selected key.",
                "evidence_ids": [evidence_id],
            },
            {
                "section": "general",
                "text": "The service parses XML and PGP data, then returns JSON.",
                "evidence_ids": [evidence_id],
            },
        ],
        "inferences": [],
        "unknowns": [],
        "limitations": [],
    }
    provider = FakeBusinessProvider(json.dumps(grounded, ensure_ascii=False))
    output = tmp_path / "business"

    result = _invoke_enrichment(provider, context_path, output, tmp_path / "cache")

    assert result.exit_code == 0, result.output
    published = _read_json(output / "result.json")
    assert len(published["claims"]) == 2
    assert all(item["confidence"] == "SUPPORTED" for item in published["claims"])
    assert not [
        item
        for item in published["limitations"]
        if item["code"] == "UNGROUNDED_CLAIM_DISCARDED"
    ]


def test_bad_claims_are_dropped_without_discarding_the_whole_generation(
    tmp_path: Path,
) -> None:
    """One malformed claim must not throw away a multi-minute generation.

    Mis-sectioned claims, claims citing a non-existent evidence id, and claims naming
    identifiers no evidence supports are each dropped and reported as their own
    limitation; the remaining claims still publish.
    """
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    by_type: dict[str, list[str]] = {}
    for item in context["evidence"]:
        by_type.setdefault(item["evidence_type"], []).append(item["evidence_id"])

    draft = {
        "claims": [
            {
                "section": "general",
                "evidence_ids": [by_type["SERVICE"][0]],
                "text": "The service reads configuration and returns a key.",
            },
            {
                "section": "general",
                "evidence_ids": ["evidence_doesnotexist"],
                "text": "A claim citing an evidence id that is not in this context.",
            },
            {
                "section": "objects",
                "evidence_ids": [by_type["DOCUMENT"][0]],
                "text": "Korzeniewska is the owner of this document type.",
            },
        ],
        "inferences": [],
        "unknowns": [],
        "limitations": [],
    }
    provider = FakeBusinessProvider(json.dumps(draft, ensure_ascii=False))
    output = tmp_path / "business"

    result = _invoke_enrichment(provider, context_path, output, tmp_path / "cache")

    assert result.exit_code == 0, result.output
    published = _read_json(output / "result.json")
    assert len(published["claims"]) == 1
    codes = {item["code"] for item in published["limitations"]}
    assert "UNKNOWN_EVIDENCE_CLAIM_DISCARDED" in codes
    assert "UNGROUNDED_CLAIM_DISCARDED" in codes


def test_sentence_initial_invented_name_is_caught(tmp_path: Path) -> None:
    """A capital opening a sentence is normally grammar, which hid an invented name.

    "Korzeniewska is the owner ..." previously published because sentence-initial
    capitals are exempt from the identifier check. Ordinary prose openings must still
    survive, so both directions are asserted.
    """
    context_path = _business_context(tmp_path)
    context = _read_json(context_path)
    evidence_id = _document_evidence_id(context)

    cases = [
        ("Korzeniewska is the owner of this document type.", 0),
        ("Keys are resolved from a keystore location.", 1),
        ("The service returns a key to the caller.", 1),
    ]
    for index, (text, expected_claims) in enumerate(cases):
        draft = {
            "claims": [
                {"section": "objects", "evidence_ids": [evidence_id], "text": text}
            ],
            "inferences": [],
            "unknowns": [],
            "limitations": [],
        }
        provider = FakeBusinessProvider(json.dumps(draft, ensure_ascii=False))
        output = tmp_path / f"case-{index}"
        # A fresh cache dir per case: the cache key covers the context and model, not
        # the draft, so a shared dir would replay the first case's result.
        result = _invoke_enrichment(provider, context_path, output, tmp_path / f"cache-{index}")

        assert result.exit_code == 0, result.output
        published = _read_json(output / "result.json")
        assert len(published["claims"]) == expected_claims, text


def test_draft_schema_constrains_sections_and_requires_citations() -> None:
    """business-draft.v2 encodes two rules the runtime previously enforced too late.

    `section` was a bare string defaulting to "general", so models never learned the
    other sections existed and filed everything under the catch-all. `evidence_ids`
    was optional, so a model asked for business meaning simply stopped citing and the
    whole run was rejected. Both are now structural, and Ollama/OpenAI structured
    decoding enforces them during generation.
    """
    schema = business_draft_json_schema()
    claim = schema["$defs"]["BusinessDraftClaim"]

    assert "evidence_ids" in claim["required"]
    assert claim["properties"]["evidence_ids"]["minItems"] == 1

    section_enum = schema["$defs"]["BusinessClaimSection"]["enum"]
    assert set(section_enum) == {item.value for item in BusinessClaimSection}
    assert "purpose" in section_enum

    # An unknown section is no longer expressible in the draft contract.
    with pytest.raises(ValidationError):
        BusinessDraftClaim(text="t", section="strange-section", evidence_ids=["e"])

    # Unknowns and limitations legitimately carry no citation.
    assert BusinessDraftItem(text="t").evidence_ids == []


def test_normalize_section_still_coerces_aliases() -> None:
    """Providers without grammar-constrained decoding can still send loose section names."""
    assert _normalize_section("steps") == BusinessClaimSection.STAGES
    assert _normalize_section("Business Objects") == BusinessClaimSection.OBJECTS
    assert _normalize_section("strange-section") == BusinessClaimSection.GENERAL
    assert _normalize_section(None) == BusinessClaimSection.GENERAL


def test_ollama_url_policy_rejects_remote_without_opt_in() -> None:
    assert validate_ollama_url("http://localhost:11434") == "http://localhost:11434"
    with pytest.raises(OllamaProviderError):
        validate_ollama_url("https://example.com:11434")
    assert (
        validate_ollama_url(
            "https://example.com:11434",
            allow_remote_provider=True,
        )
        == "https://example.com:11434"
    )


def _invoke_enrichment(
    provider: FakeBusinessProvider,
    context_path: Path,
    output: Path,
    cache_dir: Path,
) -> Any:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            "wm_doc.cli.BUSINESS_ENRICHMENT_PROVIDER_FACTORY",
            lambda *args, **kwargs: provider,
        )
        return CliRunner().invoke(
            app,
            [
                "enrich-business",
                "--context",
                str(context_path),
                "--output",
                str(output),
                "--model",
                "fake-model",
                "--cache-dir",
                str(cache_dir),
            ],
        )


def _business_context(tmp_path: Path) -> Path:
    published = tmp_path / "published"
    _run(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--target-service",
            "pgp.services.common:readConfig",
            "--dependency-depth",
            "1",
        ]
    )
    output = tmp_path / "business-context"
    _run(["build-business-context", "--input", str(published), "--output", str(output)])
    return output / "context.json"


def _business_draft_payload(context: dict[str, Any]) -> dict[str, Any]:
    evidence_id = _safe_evidence_id(context)
    return {
        "claims": [
            {
                "section": "purpose",
                "text": "Pomaga opisać technicznie wybrany zakres.",
                "evidence_ids": [evidence_id],
            }
        ],
        "inferences": [
            {
                "section": "systems",
                "text": "MoĹĽe wspieraÄ‡ techniczny przepĹ‚yw konfiguracji.",
                "evidence_ids": [evidence_id],
            }
        ],
        "unknowns": [],
        "limitations": [],
    }


def _document_evidence_id(context: dict[str, Any]) -> str:
    """An evidence id whose summary names the KeyConfig document and its fields."""
    return next(
        item["evidence_id"]
        for item in context["evidence"]
        if item["evidence_type"] == "DOCUMENT"
        and "KeyConfig" in json.dumps(item["summary"])
    )


def _safe_evidence_id(context: dict[str, Any]) -> str:
    return next(
        item["evidence_id"]
        for item in context["evidence"]
        if item["evidence_type"] in {"SERVICE", "SCOPE_MEMBERSHIP", "DETERMINISTIC_SUMMARY"}
    )


def _run(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output


def _samples() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
