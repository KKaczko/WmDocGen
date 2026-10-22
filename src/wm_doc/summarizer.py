"""Bottom-up AI descriptions for individual services (prototype).

Services are summarised one at a time in call-graph order, so a service's callees are
described before the service itself. Each prompt holds the pseudo-code view of a single
service (see :mod:`wm_doc.pseudocode`) plus the one-line descriptions already produced
for the local services it calls, which keeps every prompt small enough for a local
model's context window.

Answers are checked before use: every identifier-shaped name in the answer must occur
in the facts that were sent, and the text must pass the same disclosure scan as
business enrichment. A failed check gets one corrective retry; a second failure is
recorded as ``REJECTED`` and the answer is discarded.

Only validated summaries are cached, keyed by a hash of the exact prompt, model and
generation options. Because callee descriptions are part of the prompt, a changed
callee automatically invalidates the cache entries of its callers. Raw prompts and raw
model responses are never written to disk.

This path is separate from ``enrich-business`` and does not read or write any
``business-context`` or ``business-result`` artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from wm_doc.business_enrichment import BusinessEnrichmentError, assert_business_result_text_safe
from wm_doc.config import AppConfig
from wm_doc.ir import AnalysisResult, FlowService
from wm_doc.ollama_provider import (
    HTTP_TIMEOUT_SECONDS,
    TEMPERATURE,
    BusinessEnrichmentProvider,
    OllamaProviderError,
    ProviderGenerationRequest,
)
from wm_doc.pseudocode import (
    DETAIL_LADDER,
    FULL_DETAIL,
    MINIMAL_DETAIL,
    load_flow_comments,
    render_pseudocode,
)

SUMMARY_SCHEMA_VERSION = "service-summaries.v1"
SUMMARY_PROMPT_VERSION = "service-summary-prompt.v1"
DEFAULT_NUM_CTX = 16384
SUMMARY_NUM_PREDICT = 1024
PROMPT_MARGIN_TOKENS = 256
# Deliberately pessimistic: identifier-heavy pseudo-code averages 3.5-4 characters per
# token, so estimating 3 keeps prompts inside the window without asking the server.
CHARS_PER_TOKEN = 3
MAX_SUMMARY_CHARS = 300
MAX_DESCRIPTION_CHARS = 1500
MAX_REPORTED_NAMES = 6

SUMMARY_DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["summary", "description"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You write short documentation for webMethods Integration Server services. "
    "You are given facts about ONE service as pseudo-code extracted from its definition. "
    "`CALL x` and `TRANSFORM via x` invoke another service; the text after `#` describes "
    "that service: a platform service, a service outside the analysed code, or a "
    "description written earlier. `in:` and `out:` lines map data into or out of a call. "
    "Text after `//` is a developer comment. "
    "Use only these facts. Do not invent systems, users, schedules or business rules the "
    "facts do not show. Copy service, document and field names exactly as written; never "
    "translate or shorten them. Describe error handling only when the facts show it, and "
    "never claim that a service has no error handling. If the business purpose is not "
    "clear from the facts, describe what the service does technically."
)

USER_PROMPT_TEMPLATE = (
    "Facts:\n```\n{facts}\n```\n"
    "Return JSON with two fields:\n"
    "- summary: one sentence of at most 25 words saying what the service does, for a "
    "catalogue of services.\n"
    "- description: 2 to 4 sentences for a developer or analyst covering the main steps, "
    "the important data, what it calls, and error handling if the facts show it.\n"
    "Write in English."
)

RETRY_PROMPT_TEMPLATE = (
    "Your answer used names that do not appear in the facts: {names}. "
    "Answer again, using only names that appear in the facts."
)

_NAME_RE = re.compile(r"[A-Za-z_$][\w$]*(?:[.:/][A-Za-z_$][\w$]*)*")
_SPLIT_RE = re.compile(r"[.:/]")
_COMMON_ABBREVIATIONS = {"e.g", "i.e", "etc", "vs"}


class SummaryStatus(StrEnum):
    OK = "OK"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class AiServiceSummary(BaseModel):
    """The validated AI description of one service, or why there is none."""

    model_config = ConfigDict(frozen=True)

    service: str
    status: SummaryStatus
    summary: str | None = None
    description: str | None = None
    facts_shortened: bool = False
    note: str | None = None
    input_sha256: str


class ServiceSummaryBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = SUMMARY_SCHEMA_VERSION
    prompt_version: str = SUMMARY_PROMPT_VERSION
    model: str
    model_digest: str | None = None
    num_ctx: int
    generation_order: list[str] = Field(default_factory=list)
    summaries: list[AiServiceSummary] = Field(default_factory=list)

    def by_service(self) -> dict[str, AiServiceSummary]:
        return {item.service: item for item in self.summaries}


@dataclass(frozen=True)
class SummarizeOptions:
    model: str
    scan_root: Path
    config: AppConfig
    cache_dir: Path | None = None
    no_cache: bool = False
    refresh: bool = False
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_seconds: int = HTTP_TIMEOUT_SECONDS


@dataclass
class SummarizeStats:
    generated: int = 0
    cached: int = 0
    rejected: int = 0
    failed: int = 0
    shortened: int = 0
    retried: int = 0
    prompt_tokens: list[int] = field(default_factory=list)


ProgressCallback = Callable[[int, int, AiServiceSummary, bool], None]


class SummarizerError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


def default_summary_cache_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        return Path(local_app_data) / "wm-doc" / "service-summaries"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "wm-doc" / "service-summaries"
    return Path.home() / ".cache" / "wm-doc" / "service-summaries"


def summary_order(services: Iterable[FlowService]) -> list[str]:
    """Order services so that every local callee comes before its callers.

    Uses Tarjan's strongly-connected-components algorithm, which emits components in
    reverse topological order of the call graph: callees first. Services in a call cycle
    share a component and are ordered by name; inside a cycle some callee descriptions
    are necessarily unavailable.
    """
    by_name = {service.identity.full_name: service for service in services}
    graph: dict[str, list[str]] = {}
    for name, service in by_name.items():
        targets = {
            dependency.target_service
            for dependency in service.unique_dependencies
            if dependency.resolved
            and dependency.target_service in by_name
            and dependency.target_service != name
        }
        graph[name] = sorted(targets, key=str.casefold)

    index_of: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    order: list[str] = []
    counter = 0

    for root in sorted(graph, key=str.casefold):
        if root in index_of:
            continue
        # Iterative DFS: each frame is (node, iterator position over its neighbours).
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, position = work.pop()
            if position == 0:
                index_of[node] = lowlink[node] = counter
                counter += 1
                stack.append(node)
                on_stack.add(node)
            neighbours = graph[node]
            descended = False
            while position < len(neighbours):
                neighbour = neighbours[position]
                position += 1
                if neighbour not in index_of:
                    work.append((node, position))
                    work.append((neighbour, 0))
                    descended = True
                    break
                if neighbour in on_stack:
                    lowlink[node] = min(lowlink[node], index_of[neighbour])
            if descended:
                continue
            if lowlink[node] == index_of[node]:
                component: list[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                order.extend(sorted(component, key=str.casefold))
            if work:
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
    return order


def build_summary_messages(facts: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(facts=facts)},
    ]


def fit_facts(
    service: FlowService,
    callee_note: Callable[[str], str | None],
    comments: Mapping[str, str],
    num_ctx: int,
) -> tuple[str, bool]:
    """Render the richest pseudo-code that fits the context window.

    Returns the facts and whether anything was left out to make them fit.
    """
    overhead = len(SYSTEM_PROMPT) + len(USER_PROMPT_TEMPLATE)
    budget_tokens = num_ctx - SUMMARY_NUM_PREDICT - PROMPT_MARGIN_TOKENS
    budget_chars = max(budget_tokens * CHARS_PER_TOKEN - overhead, 1000)
    for detail in DETAIL_LADDER:
        facts = render_pseudocode(service, callee_note, comments=comments, detail=detail)
        if len(facts) <= budget_chars:
            return facts, detail is not FULL_DETAIL
    facts = render_pseudocode(service, callee_note, comments=comments, detail=MINIMAL_DETAIL)
    lines = facts.splitlines()
    kept: list[str] = []
    used = 0
    reserve = 120
    for line in lines:
        if used + len(line) + 1 > budget_chars - reserve:
            break
        kept.append(line)
        used += len(line) + 1
    omitted = len(lines) - len(kept)
    kept.append(f"... ({omitted} more lines omitted to fit the model's context window)")
    return "\n".join(kept), True


def summary_cache_key(
    messages: list[dict[str, str]], model: str, model_digest: str | None, num_ctx: int
) -> str:
    payload = {
        "prompt_version": SUMMARY_PROMPT_VERSION,
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "model": model,
        "model_digest": model_digest or "UNKNOWN",
        "messages": messages,
        "draft_schema": SUMMARY_DRAFT_SCHEMA,
        "options": {
            "temperature": TEMPERATURE,
            "num_ctx": num_ctx,
            "num_predict": SUMMARY_NUM_PREDICT,
        },
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def unknown_names(text: str, facts: str) -> list[str]:
    """Return identifier-shaped names in *text* that the facts do not contain."""
    full_names = {match.casefold() for match in _NAME_RE.findall(facts)}
    parts: set[str] = set()
    for name in full_names:
        parts.update(piece for piece in _SPLIT_RE.split(name) if piece)
    unknown: list[str] = []
    for match in _NAME_RE.findall(text):
        candidate = match.strip("/")
        folded = candidate.casefold()
        if not candidate or folded in _COMMON_ABBREVIATIONS or not _is_identifier(candidate):
            continue
        if folded in full_names:
            continue
        pieces = [piece for piece in _SPLIT_RE.split(folded) if piece]
        if "/" in candidate and all(piece in parts for piece in pieces):
            continue  # a pipeline path whose segments all occur in the facts
        if len(pieces) == 1 and folded in parts:
            continue
        if candidate not in unknown:
            unknown.append(candidate)
    return unknown


def summarize_analysis(
    analysis: AnalysisResult,
    provider: BusinessEnrichmentProvider,
    options: SummarizeOptions,
    progress: ProgressCallback | None = None,
) -> tuple[ServiceSummaryBundle, SummarizeStats]:
    """Describe every service in call-graph order, callees first."""
    if not options.model.strip():
        raise SummarizerError("--model must not be blank.")
    check = provider.check(options.model)
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }
    order = summary_order(services.values())
    results: dict[str, AiServiceSummary] = {}
    stats = SummarizeStats()

    def callee_note(target: str) -> str | None:
        result = results.get(target)
        if result is None:
            return "(description not yet available: call cycle)" if target in services else None
        if result.status is SummaryStatus.OK:
            return result.summary
        return None

    cache_dir = None if options.no_cache else options.cache_dir
    for position, name in enumerate(order, start=1):
        result, from_cache = _summarize_one(
            services[name],
            provider,
            options,
            check.model_digest,
            callee_note,
            cache_dir,
            stats,
        )
        results[name] = result
        if result.facts_shortened:
            stats.shortened += 1
        if from_cache:
            stats.cached += 1
        elif result.status is SummaryStatus.OK:
            stats.generated += 1
        elif result.status is SummaryStatus.REJECTED:
            stats.rejected += 1
        else:
            stats.failed += 1
        if progress is not None:
            progress(position, len(order), result, from_cache)

    bundle = ServiceSummaryBundle(
        model=options.model,
        model_digest=check.model_digest,
        num_ctx=options.num_ctx,
        generation_order=order,
        summaries=sorted(results.values(), key=lambda item: item.service.casefold()),
    )
    return bundle, stats


def render_summary_bundle_json(bundle: ServiceSummaryBundle) -> str:
    payload = bundle.model_dump(mode="json")
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _summarize_one(
    service: FlowService,
    provider: BusinessEnrichmentProvider,
    options: SummarizeOptions,
    model_digest: str | None,
    callee_note: Callable[[str], str | None],
    cache_dir: Path | None,
    stats: SummarizeStats,
) -> tuple[AiServiceSummary, bool]:
    name = service.identity.full_name
    comments = load_flow_comments(options.scan_root, service, options.config)
    facts, shortened = fit_facts(service, callee_note, comments, options.num_ctx)
    messages = build_summary_messages(facts)
    key = summary_cache_key(messages, options.model, model_digest, options.num_ctx)

    def outcome(status: SummaryStatus, note: str | None = None, **text: str) -> AiServiceSummary:
        return AiServiceSummary(
            service=name,
            status=status,
            summary=text.get("summary"),
            description=text.get("description"),
            facts_shortened=shortened,
            note=note,
            input_sha256=key,
        )

    if cache_dir is not None and not options.refresh:
        cached = _read_cache(cache_dir, key)
        if cached is not None:
            return outcome(SummaryStatus.OK, **cached), True

    conversation = list(messages)
    for attempt in range(2):
        try:
            generation = provider.generate(
                ProviderGenerationRequest(
                    model=options.model,
                    messages=conversation,
                    schema=SUMMARY_DRAFT_SCHEMA,
                    timeout_seconds=options.timeout_seconds,
                    num_ctx=options.num_ctx,
                    num_predict=SUMMARY_NUM_PREDICT,
                )
            )
        except OllamaProviderError as exc:
            return outcome(SummaryStatus.FAILED, f"generation failed: {exc.safe_message}"), False
        prompt_tokens = generation.metrics.get("prompt_eval_count")
        if isinstance(prompt_tokens, int):
            stats.prompt_tokens.append(prompt_tokens)
            if prompt_tokens >= options.num_ctx - SUMMARY_NUM_PREDICT:
                return (
                    outcome(
                        SummaryStatus.FAILED,
                        "the prompt may have been cut off by the model server "
                        f"({prompt_tokens} prompt tokens for a {options.num_ctx}-token window)",
                    ),
                    False,
                )
        parsed = _parse_draft(generation.content)
        if parsed is None:
            failure = "the model did not return the expected JSON"
            return outcome(SummaryStatus.FAILED, failure), False
        summary, description = parsed
        try:
            assert_business_result_text_safe(f"{summary}\n{description}")
        except BusinessEnrichmentError as exc:
            return outcome(SummaryStatus.REJECTED, exc.safe_message), False
        unknown = unknown_names(f"{summary}\n{description}", facts)
        if not unknown:
            if cache_dir is not None:
                _write_cache(cache_dir, key, summary, description)
            return outcome(SummaryStatus.OK, summary=summary, description=description), False
        if attempt == 0:
            stats.retried += 1
            conversation = [
                *messages,
                {"role": "assistant", "content": generation.content},
                {
                    "role": "user",
                    "content": RETRY_PROMPT_TEMPLATE.format(names=_name_list(unknown)),
                },
            ]
            continue
        return (
            outcome(
                SummaryStatus.REJECTED,
                f"the model's answer named things that are not in the facts: {_name_list(unknown)}",
            ),
            False,
        )
    raise AssertionError("unreachable")


def _parse_draft(content: str) -> tuple[str, str] | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    summary = payload.get("summary")
    description = payload.get("description")
    if not isinstance(summary, str) or not isinstance(description, str):
        return None
    summary = _clean_text(summary, MAX_SUMMARY_CHARS)
    description = _clean_text(description, MAX_DESCRIPTION_CHARS)
    if not summary:
        return None
    return summary, description


def _clean_text(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    sentence_end = cut.rfind(". ")
    return cut[: sentence_end + 1] if sentence_end > limit // 2 else cut.rstrip() + "..."


def _name_list(names: list[str]) -> str:
    shown = ", ".join(f"`{name}`" for name in names[:MAX_REPORTED_NAMES])
    extra = len(names) - min(len(names), MAX_REPORTED_NAMES)
    return shown + (f" and {extra} more" if extra else "")


def _is_acronym(token: str) -> bool:
    """XML, PGP, AES_128, and plurals such as IDs or URLs."""
    letters = [char for char in token if char.isalpha()]
    if letters and letters[-1] == "s" and len(letters) > 2:
        letters = letters[:-1]
    return bool(letters) and all(char.isupper() for char in letters)


def _is_identifier(token: str) -> bool:
    pieces = [piece for piece in _SPLIT_RE.split(token) if piece]
    if pieces and all(_is_acronym(piece) for piece in pieces):
        return False  # including joined forms such as I/O
    if any(separator in token for separator in ".:/"):
        return True
    if "_" in token or "$" in token or any(char.isdigit() for char in token):
        return True
    return any(char.isupper() for char in token[1:])


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / key[:2] / f"{key}.json"


def _read_cache(cache_dir: Path, key: str) -> dict[str, str] | None:
    path = _cache_path(cache_dir, key)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("prompt_version") != SUMMARY_PROMPT_VERSION:
        return None
    summary = payload.get("summary")
    description = payload.get("description")
    if not isinstance(summary, str) or not isinstance(description, str) or not summary:
        return None
    return {"summary": summary, "description": description}


def _write_cache(cache_dir: Path, key: str, summary: str, description: str) -> None:
    path = _cache_path(cache_dir, key)
    payload = {
        "prompt_version": SUMMARY_PROMPT_VERSION,
        "summary": summary,
        "description": description,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)
    except OSError:
        return  # a cache write failure only costs a regeneration next time
