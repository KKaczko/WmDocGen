from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from wm_doc.business_result_schema import BusinessEnrichmentErrorCode
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
    assert result["schema_version"] == "business-result.v1"
    assert result["context_id"] == context["context_id"]
    assert result["source_context_sha256"]
    assert result["language"] == "pl"
    assert result["claims"][0]["claim_id"].startswith("claim_")
    assert result["claims"][0]["evidence_ids"][0] in {
        item["evidence_id"] for item in context["evidence"]
    }
    assert result["claims"][0]["confidence"] == "CONFIRMED"
    assert result["claims"][1]["confidence"] == "INFERRED"
    assert result["validation"]["draft_schema_version"] == "business-draft.v1"
    assert result["provenance"]["draft_schema_version"] == "business-draft.v1"
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


def test_enrich_business_rejects_unknown_evidence(
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

    assert result.exit_code == 1
    assert BusinessEnrichmentErrorCode.EVIDENCE_INVALID.value in result.output
    assert not (tmp_path / "business" / "result.json").exists()


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
    assert BusinessEnrichmentErrorCode.EVIDENCE_INVALID.value in result.output


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
                "section": "strange-section",
                "evidence_ids": [evidence_id, evidence_id],
            },
            {
                "text": "Opis wspierany dowodem.",
                "section": "strange-section",
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
