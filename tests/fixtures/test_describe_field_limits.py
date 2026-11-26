"""`describe.fieldLimits`: an answer is checked whole, then cut to configurable caps."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from describe_answers import flow_items
from flowxml import FlowPackage, invoke

from wm_doc.analysis_cache import input_fingerprint
from wm_doc.config import AppConfig, load_config
from wm_doc.describer import DescribeOptions, DescribeOutcome, clean_text, describe_services
from wm_doc.ollama_provider import (
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.service_docs import doc_path

SUBJECT = "orders.core:save"
CALLER = "di.channel.bpms.services.fsm:serviceOrderCommentNotification"
# A usage text whose 400th character falls inside the caller's name, with no sentence end in
# its second half: the old cut made `di.channel...fsm:serviceOrderComm` and rejected it.
FILLER = "Used by the field service channel " + "for order comment notifications " * 10
USAGE = f"{FILLER}through {CALLER} and the other callers listed in the facts"
assert len(FILLER) < 400 < len(FILLER) + len("through ") + len(CALLER)


class Provider:
    def __init__(self) -> None:
        self.requests = 0

    def check(self, model: str) -> ProviderCheckResult:
        return ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version="test",
            model_digest="sha256:test",
            model_found=True,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.requests += 1
        payload = {
            "purpose": "Saves an order.",
            "usage": USAGE,
            "data_effects": "Returns nothing.",
            "steps": ["Saves the order."],
            "detailed_steps": flow_items(request.messages[1]["content"]),
            "error_handling": "Not shown in the facts.",
            "designer_comment": "Saves an order.",
        }
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )


def _describe(tmp_path: Path, config: AppConfig) -> tuple[DescribeOutcome, str]:
    root = tmp_path / "packages"
    pkg = FlowPackage(root, "Orders")
    pkg.service(SUBJECT, invoke("pub.flow:debugLog"))
    pkg.service(CALLER, invoke(SUBJECT))
    options = DescribeOptions(
        model="fake-model",
        scan_root=root,
        config=config,
        docs_dir=tmp_path / "service-docs",
        cache_dir=tmp_path / "cache",
    )
    results, _ = describe_services(pkg.analyze(), [SUBJECT], Provider(), options)
    text = doc_path(tmp_path / "service-docs", "Orders", SUBJECT).read_text(encoding="utf-8")
    usage = re.search(r"## Usage\n\n(.*?)\n\n", text, re.DOTALL)
    return results[0].outcome, usage.group(1) if usage else ""


def _config(tmp_path: Path, yaml_text: str) -> AppConfig:
    path = tmp_path / "wm-doc.yml"
    path.write_text(yaml_text, encoding="utf-8")
    return load_config(path)


def test_a_cut_never_ends_inside_a_word() -> None:
    assert clean_text(f"Used by aaaa {CALLER}", 40) == "Used by aaaa..."
    assert clean_text(f"Used by aaaa {CALLER}", None) == f"Used by aaaa {CALLER}"
    assert clean_text("First sentence here. Second one", 25) == "First sentence here."


def test_names_are_checked_before_the_answer_is_cut(tmp_path: Path) -> None:
    outcome, usage = _describe(tmp_path, load_config(None))

    assert outcome is DescribeOutcome.GENERATED
    assert len(usage) <= 400
    assert usage.endswith("...")
    assert "serviceOrderComm" not in usage  # cut before the name, never inside it


def test_field_limits_can_be_raised_or_switched_off(tmp_path: Path) -> None:
    raised = _config(tmp_path, "describe:\n  fieldLimits:\n    usage: 2000\n")
    single = _config(tmp_path, "describe:\n  fieldLimits:\n    usage: null\n")
    every = _config(tmp_path, "describe:\n  fieldLimits:\n    enabled: false\n")
    off = _config(tmp_path, "describe:\n  fieldLimits: off\n")

    assert raised.describe.fieldLimits.limit("usage") == 2000
    assert single.describe.fieldLimits.limit("usage") is None
    assert single.describe.fieldLimits.limit("purpose") == 400
    assert every.describe.fieldLimits.limit("purpose") is None
    assert off.describe.fieldLimits.limit("dataEffects") is None
    outcome, usage = _describe(tmp_path, single)
    assert outcome is DescribeOutcome.GENERATED
    assert usage == USAGE


def test_describe_settings_keep_the_cached_analysis(tmp_path: Path) -> None:
    root = tmp_path / "packages"
    FlowPackage(root, "Orders").service(SUBJECT, invoke("pub.flow:debugLog"))
    changed: dict[str, Any] = {"describe": {"fieldLimits": {"enabled": False}}}

    assert input_fingerprint(root, AppConfig(), None, False) == input_fingerprint(
        root, AppConfig.model_validate(changed), None, False
    )
