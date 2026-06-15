from __future__ import annotations

import json

from wm_doc.ir import AnalysisResult


def render_analysis_json(analysis: AnalysisResult) -> str:
    payload = analysis.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
