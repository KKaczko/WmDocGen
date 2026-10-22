"""Overview page and JSON for the bottom-up AI service descriptions (prototype)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from wm_doc.summarizer import (
    ServiceSummaryBundle,
    SummaryStatus,
    render_summary_bundle_json,
)

AI_SUMMARIES_JSON = "ai-summaries.json"
AI_SUMMARIES_MARKDOWN = "ai-summaries.md"


def render_ai_summaries_markdown(
    bundle: ServiceSummaryBundle, service_filenames: dict[str, str]
) -> str:
    counts = Counter(item.status for item in bundle.summaries)
    shortened = sum(1 for item in bundle.summaries if item.facts_shortened)
    lines = [
        "# AI Service Descriptions",
        "",
        (
            f"Written by a local language model (`{bundle.model}`), one service at a time. "
            "Services were described in call-graph order, so each description could use the "
            "descriptions of the services it calls. None of this text has been reviewed: "
            "treat it as a starting point and check it against the facts on each service page."
        ),
        "",
        "| Result | Services |",
        "| --- | ---: |",
        f"| Described | {counts.get(SummaryStatus.OK, 0)} |",
        f"| Answer rejected by validation | {counts.get(SummaryStatus.REJECTED, 0)} |",
        f"| Generation failed | {counts.get(SummaryStatus.FAILED, 0)} |",
        f"| Facts shortened to fit the context window | {shortened} |",
        "",
        "## Services",
        "",
        "| Service | In short |",
        "| --- | --- |",
    ]
    for item in bundle.summaries:
        filename = service_filenames.get(item.service)
        name = f"`{item.service}`"
        link = f"[{name}](services/{filename})" if filename else name
        if item.status is SummaryStatus.OK:
            text = item.summary or ""
        else:
            text = f"_No description: {item.note or item.status.value.lower()}_"
        lines.append(f"| {link} | {_escape_cell(text)} |")
    lines.append("")
    return "\n".join(lines)


def write_ai_summary_outputs(
    output_dir: Path, bundle: ServiceSummaryBundle, service_filenames: dict[str, str]
) -> list[Path]:
    json_path = output_dir / AI_SUMMARIES_JSON
    markdown_path = output_dir / AI_SUMMARIES_MARKDOWN
    json_path.write_text(render_summary_bundle_json(bundle), encoding="utf-8")
    markdown_path.write_text(
        render_ai_summaries_markdown(bundle, service_filenames), encoding="utf-8"
    )
    return [json_path, markdown_path]


def _escape_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
