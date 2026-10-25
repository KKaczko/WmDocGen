"""Freeze today's pseudo-code and description facts hashes.

The conditional-flow work adds new views of the FLOW, but the pseudo-code the model sees and the
facts hash of a description file must not change by accident: a changed facts hash marks every
approved description as "approved, facts changed". The snapshot covers every pseudo-code detail
level (with callee notes, external-system notes, callee outputs and step comments, as prompts
use them) for the samples and for a builder-made service with the rarer shapes. Regenerate on
purpose with `WM_DOC_UPDATE_FIXTURES=1 uv run pytest tests/unit/test_flow_facts_golden.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from flowxml import (
    FlowPackage,
    branch,
    case,
    copy,
    exit_,
    invoke,
    loop,
    map_,
    record,
    repeat,
    seq,
    set_,
    string,
)

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.describer import current_facts_hashes
from wm_doc.ir import AnalysisResult
from wm_doc.pseudocode import (
    DETAIL_LADDER,
    callee_outputs_lookup,
    load_flow_comments,
    render_pseudocode,
)

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples"
GOLDEN = ROOT / "tests" / "fixtures" / "golden" / "flow-facts.json"


def _shapes(root: Path) -> Path:
    """A service with REPEAT, a disabled step, EXIT FAILURE, label expressions and direct cases."""
    pkg = FlowPackage(root, "Shapes")
    pkg.service(
        "shapes.all:rareShapes",
        map_(set_("/mode", "fast"), copy("/request/id", "/id"), comment="Prepare the request."),
        repeat(invoke("shapes.api:call"), count="2", back_off="5"),
        invoke("shapes.api:skipped", disabled=True),
        branch(
            case("1", map_(set_("/verified", "true")), wrap=False),
            case("$default", invoke("shapes.api:reject"), wrap=False),
            switch="/verified",
        ),
        loop(
            branch(
                case('%items/status% == "STOP"', exit_("$loop")),
                case("$default", invoke("shapes.api:each")),
                expressions=True,
            ),
            in_array="/items",
            out_array="/results",
        ),
        seq(invoke("shapes.api:first"), invoke("shapes.api:second"), exit_on="DONE"),
        branch(case("ERROR", exit_("$flow", "FAILURE", "failed")), switch="/state"),
        inputs=[record("request", [string("id")])],
    )
    return root


def _snapshot(analysis: AnalysisResult, root: Path) -> dict[str, dict[str, str]]:
    config = load_config(None)
    facts = current_facts_hashes(analysis, root, config)
    services = {item.identity.full_name: item for item in analysis.services}
    outputs = callee_outputs_lookup(services)

    def external(target: str) -> str | None:
        return "declared external system Test" if target.startswith("sample.orders.") else None

    snapshot: dict[str, dict[str, str]] = {}
    for name in sorted(services):
        service = services[name]
        entry = {
            "facts": facts[name],
            "pseudocode": _digest(render_pseudocode(service, lambda _: None)),
        }
        comments = load_flow_comments(root, service, config)
        for level, detail in enumerate(DETAIL_LADDER):
            text = render_pseudocode(
                service,
                lambda target: f"note for {target}",
                comments=comments,
                detail=detail,
                external_note=external,
                callee_outputs=outputs,
            )
            entry[f"prompt_level_{level}"] = _digest(text)
        snapshot[name] = entry
    return snapshot


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current(tmp_path: Path) -> dict[str, dict[str, str]]:
    config = load_config(None)
    current = _snapshot(analyze_path(SAMPLES, config, None, processes_file_explicit=False), SAMPLES)
    shapes = _shapes(tmp_path / "shapes")
    current.update(_snapshot(analyze_path(shapes, config), shapes))
    return current


def test_pseudocode_and_facts_hashes_are_unchanged(tmp_path: Path) -> None:
    current = _current(tmp_path)
    if os.environ.get("WM_DOC_UPDATE_FIXTURES") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(
            json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    changed = sorted(
        name for name in expected.keys() | current.keys() if expected.get(name) != current.get(name)
    )
    assert not changed, (
        "pseudo-code or facts hash changed for: " + ", ".join(changed) + ". If intended, "
        "regenerate with WM_DOC_UPDATE_FIXTURES=1 and say so in the change notes."
    )


def test_the_rare_shapes_service_parses_cleanly(tmp_path: Path) -> None:
    shapes = _shapes(tmp_path / "shapes")
    service = analyze_path(shapes, load_config(None)).services[0]

    assert service.findings == []
    assert service.disabled_steps == 1
