"""analysis.json is written piece by piece but must match the one-shot serialization exactly."""

from __future__ import annotations

import json
from pathlib import Path

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.ir import AnalysisResult
from wm_doc.render.analysis_json import render_analysis_json, write_analysis_json

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _one_shot(analysis: AnalysisResult) -> str:
    payload = analysis.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def test_streamed_analysis_json_matches_the_one_shot_text(tmp_path: Path) -> None:
    analysis = analyze_path(SAMPLES, load_config(None))
    path = tmp_path / "analysis.json"

    write_analysis_json(path, analysis)

    expected = _one_shot(analysis)
    assert render_analysis_json(analysis) == expected
    assert path.read_text(encoding="utf-8") == expected
    assert json.loads(expected)["packages"]


def test_empty_analysis_matches_too(tmp_path: Path) -> None:
    analysis = analyze_path(tmp_path, load_config(None))

    assert render_analysis_json(analysis) == _one_shot(analysis)
