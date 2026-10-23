"""`wm-doc describe`: write or refresh per-service description files, callees first.

For each selected service, in call-graph order:

1. Build the deterministic facts: pseudo-code view, usage and data effects (see
   :mod:`wm_doc.effects`), declared external systems, developer step comments.
2. If the service already has a description that is approved or was edited by hand, only
   its facts block is refreshed. An unedited draft whose facts are unchanged is kept too,
   unless `redo_drafts` is set.
3. Otherwise a local model drafts the narrative, using the Purpose lines of the services
   it calls (approved text first, then drafts) as context. Every name in the answer must
   appear in the facts, and the text must pass the disclosure scan; one corrective retry
   is allowed. The file is written as soon as the draft validates, so an interrupted run
   loses at most the service in progress, and the next run continues from the files.

Only validated drafts are cached (by a hash of the exact prompt and model). Raw prompts and
responses are never stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from collections.abc import Callable, Collection, Iterable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

from wm_doc.callgraph import summary_order
from wm_doc.config import AppConfig
from wm_doc.disclosure import unsafe_disclosure_label
from wm_doc.effects import ServiceFacts, compute_service_facts
from wm_doc.external_systems import EMPTY_CATALOG, ExternalSystemCatalog, system_label
from wm_doc.ir import AnalysisResult, FlowService, ServiceType, SignatureField
from wm_doc.ollama_provider import (
    HTTP_TIMEOUT_SECONDS,
    TEMPERATURE,
    ModelProvider,
    OllamaProviderError,
    ProviderGenerationRequest,
)
from wm_doc.pseudocode import FULL_DETAIL, load_flow_comments, render_pseudocode
from wm_doc.render.service_markdown import render_effects_table, render_entry_points_table
from wm_doc.render.service_summary import adapter_sentence
from wm_doc.service_docs import (
    MAX_DESIGNER_COMMENT_CHARS,
    DocState,
    DocStatus,
    Narrative,
    ServiceDoc,
    doc_path,
    facts_hash,
    iter_docs,
    new_doc,
    read_doc,
    write_doc,
)
from wm_doc.summarizer import DEFAULT_NUM_CTX, fit_facts, unknown_names

DESCRIBE_PROMPT_VERSION = "service-describe-prompt.v2"
DESCRIBE_NUM_PREDICT = 1536
MAX_STEPS = 8
MAX_STEP_CHARS = 200
FIELD_LIMITS = {
    "purpose": 400,
    "usage": 400,
    "data_effects": 900,
    "error_handling": 300,
}

DESCRIBE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "purpose": {"type": "string"},
        "usage": {"type": "string"},
        "data_effects": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "error_handling": {"type": "string"},
        "designer_comment": {"type": "string"},
    },
    "required": [
        "purpose",
        "usage",
        "data_effects",
        "steps",
        "error_handling",
        "designer_comment",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "You write documentation for webMethods Integration Server services. You are given "
    "facts about ONE service: a `used by` section, a `data and systems touched` section, "
    "and pseudo-code of its steps. `CALL x` and `TRANSFORM via x` invoke another service; "
    "the text after `#` describes that service. `in:` and `out:` lines map data into or "
    "out of a call. Text after `//` is a developer comment. "
    "Use only these facts. Do not invent systems, users, schedules, tables or business "
    "rules. Copy service, document, field and system names exactly as written; never "
    "translate or shorten them. Describe error handling only as the facts show it. If the "
    "business purpose is not clear from the facts, describe what the service does "
    "technically."
)

USER_PROMPT_TEMPLATE = (
    "Facts:\n```\n{facts}\n```\n"
    "Return JSON with these fields, in English:\n"
    "- purpose: one or two sentences saying what the service is for. Start with a verb.\n"
    "- usage: one or two sentences on who or what uses it, from `used by`.\n"
    "- data_effects: one to three sentences on which data objects it receives, returns, "
    "reads, creates, changes, publishes or sends, and where, from `data and systems "
    "touched`.\n"
    "- steps: three to six short items, the main steps in order.\n"
    "- error_handling: one sentence. If the facts show no error handling, say that it is "
    "not shown in the facts.\n"
    "- designer_comment: plain text of at most 600 characters, without Markdown, for the "
    "service's Comments field in Designer: purpose, main inputs and outputs, and effects."
)

# Adapter and other opaque services have no steps the tool can read. The model words the
# purpose, usage and data effects only; the tool writes their steps and error handling.
OPAQUE_PROMPT_TEMPLATE = (
    "Facts:\n```\n{facts}\n```\n"
    "This service has no FLOW or Java steps in the facts: it is an adapter or other "
    "service whose implementation is a configuration. Do not describe steps, SQL, "
    "conditions or error handling that the facts do not state.\n"
    "Return JSON with these fields, in English:\n"
    "- purpose: one or two sentences saying what the service is for, from its name, "
    "signature and the configured operation in the facts. Start with a verb.\n"
    "- usage: one or two sentences on who or what uses it, from `used by`.\n"
    "- data_effects: one or two sentences on the data it reads or changes and where, from "
    "`data and systems touched`.\n"
    "- steps: an empty list.\n"
    "- error_handling: an empty string.\n"
    "- designer_comment: plain text of at most 600 characters, without Markdown, for the "
    "service's Comments field in Designer: purpose, main inputs and outputs, and effects."
)
OPAQUE_ERROR_HANDLING = "Error handling is not analysed for this service type."

RETRY_PROMPT_TEMPLATE = (
    "Your answer used names that do not appear in the facts: {names}. "
    "Answer again, using only names that appear in the facts."
)
DISCLOSURE_RETRY_PROMPT_TEMPLATE = (
    "Your answer contained text that cannot be published ({label}). Answer again without "
    "connection strings, credentials, file paths, links, HTML or code; name connections, "
    "services and tables only as they appear in the facts."
)


class DescribeOutcome(StrEnum):
    GENERATED = "generated"
    CACHED = "cached"
    UNCHANGED = "unchanged"
    PROTECTED = "kept (approved or edited)"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass(frozen=True)
class DescribeOptions:
    model: str
    scan_root: Path
    config: AppConfig
    docs_dir: Path
    cache_dir: Path | None = None
    no_cache: bool = False
    refresh: bool = False
    redo_drafts: bool = False
    num_ctx: int = DEFAULT_NUM_CTX
    timeout_seconds: int = HTTP_TIMEOUT_SECONDS
    external_systems: ExternalSystemCatalog = EMPTY_CATALOG
    parallel: int = 1


@dataclass(frozen=True)
class DescribeResult:
    service: str
    outcome: DescribeOutcome
    path: Path | None = None
    note: str | None = None
    facts_shortened: bool = False


@dataclass
class DescribeStats:
    counts: dict[DescribeOutcome, int] = field(default_factory=dict)
    retried: int = 0
    shortened: int = 0
    prompt_tokens: list[int] = field(default_factory=list)

    def add(self, result: DescribeResult) -> None:
        self.counts[result.outcome] = self.counts.get(result.outcome, 0) + 1
        if result.facts_shortened:
            self.shortened += 1


ProgressCallback = Callable[[int, int, DescribeResult], None]


class DescribeError(Exception):
    def __init__(self, safe_message: str) -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message


def describe_services(
    analysis: AnalysisResult,
    selected: Iterable[str],
    provider: ModelProvider,
    options: DescribeOptions,
    progress: ProgressCallback | None = None,
) -> tuple[list[DescribeResult], DescribeStats]:
    if not options.model.strip():
        raise DescribeError("--model must not be blank.")
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }
    wanted = set(selected)
    unknown = sorted(wanted - services.keys())
    if unknown:
        raise DescribeError(f"Unknown service(s): {', '.join(unknown[:5])}.")
    order = [name for name in summary_order(services.values()) if name in wanted]
    facts = compute_service_facts(analysis, options.external_systems)
    run = _Run(services, facts, open_session(provider, options), options, order)
    results: dict[str, DescribeResult] = {}

    def finish(result: DescribeResult) -> None:
        run.stats.add(result)
        results[result.service] = result
        if progress is not None:
            progress(len(results), len(order), result)

    if options.parallel <= 1:
        for name in order:
            finish(run.describe(name))
    else:
        _describe_in_parallel(run, order, options.parallel, finish)
    return [results[name] for name in order], run.stats


def open_session(provider: ModelProvider, options: DescribeOptions) -> ModelSession:
    """Check the model once and return a session using the run's options."""
    check = provider.check(options.model)
    return ModelSession(
        provider,
        model=options.model,
        model_digest=check.model_digest,
        num_ctx=options.num_ctx,
        timeout_seconds=options.timeout_seconds,
        cache_dir=None if options.no_cache else options.cache_dir,
        refresh=options.refresh,
    )


def _describe_in_parallel(
    run: _Run, order: list[str], workers: int, finish: Callable[[DescribeResult], None]
) -> None:
    """Run up to *workers* services at once; a service starts after its earlier callees.

    Callee context only ever comes from services earlier in the call-graph order, which are
    finished before a caller starts, so the files are the same as in a sequential run.
    """
    waiting_on = {
        name: {
            callee
            for callee in run.local_callees(name)
            if callee in run.position and run.position[callee] < run.position[name]
        }
        for name in order
    }
    pending = list(order)
    done: set[str] = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        running: dict[Future[DescribeResult], str] = {}
        while pending or running:
            for name in list(pending):
                if len(running) >= workers:
                    break
                if waiting_on[name] <= done:
                    pending.remove(name)
                    running[pool.submit(run.describe, name)] = name
            if not running:
                raise DescribeError("Could not schedule the remaining services.")
            finished, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in sorted(finished, key=lambda item: run.position[running[item]]):
                done.add(running.pop(future))
                finish(future.result())


def deterministic_facts(
    service: FlowService,
    facts: ServiceFacts,
    comments: dict[str, str],
    external_note: Callable[[str], str | None],
) -> str:
    """Everything known about a service without callee descriptions: the basis of its hash.

    Callee wording is left out on purpose, so rewording a callee's description does not mark
    every approved caller as "facts changed".
    """
    return render_pseudocode(
        service,
        lambda _: None,
        comments=comments,
        detail=FULL_DETAIL,
        facts_text=facts.text(),
        external_note=external_note,
    )


def current_facts_hashes(
    analysis: AnalysisResult,
    scan_root: Path,
    config: AppConfig,
    external_systems: ExternalSystemCatalog = EMPTY_CATALOG,
    *,
    facts: Mapping[str, ServiceFacts] | None = None,
    only: Collection[str] | None = None,
) -> dict[str, str]:
    """Facts hash per service; `only` limits the work to services that have a description."""
    if facts is None:
        facts = compute_service_facts(analysis, external_systems)

    def external_note(target: str) -> str | None:
        system = external_systems.match(target)
        return system_label(system) if system is not None else None

    hashes: dict[str, str] = {}
    for package in analysis.packages:
        for service in package.services:
            name = service.identity.full_name
            if only is not None and name not in only:
                continue
            comments = load_flow_comments(scan_root, service, config)
            hashes[name] = facts_hash(
                deterministic_facts(service, facts[name], comments, external_note)
            )
    return hashes


STATE_ORDER = (
    DocState.STALE,
    DocState.EDITED,
    DocState.DRAFT,
    DocState.MISSING,
    DocState.APPROVED,
)


def collect_states(
    analysis: AnalysisResult, docs_dir: Path, hashes: dict[str, str]
) -> dict[str, tuple[str, DocState]]:
    """service -> (package, state) for every analysed service."""
    states: dict[str, tuple[str, DocState]] = {}
    for package in analysis.packages:
        for service in package.services:
            name = service.identity.full_name
            doc = read_doc(doc_path(docs_dir, package.name, name))
            state = DocState.MISSING if doc is None else doc.state(hashes.get(name))
            states[name] = (package.name, state)
    return states


def render_status(
    states: dict[str, tuple[str, DocState]],
    orphans: list[str],
    overviews: dict[str, DocState] | None = None,
) -> str:
    counts: dict[str, dict[DocState, int]] = {}
    for package, state in states.values():
        per_package = counts.setdefault(package, {})
        per_package[state] = per_package.get(state, 0) + 1
    header = " | ".join(state.value for state in STATE_ORDER)
    lines = [
        "# Description status",
        "",
        "Generated by `wm-doc status`. Approved texts are never overwritten; "
        "\"approved, facts changed\" means the service changed after approval.",
        "",
        f"| Package | {header} |",
        "| --- |" + " ---: |" * len(STATE_ORDER),
    ]
    totals = dict.fromkeys(STATE_ORDER, 0)
    for package in sorted(counts, key=str.casefold):
        row = [counts[package].get(state, 0) for state in STATE_ORDER]
        for state, value in zip(STATE_ORDER, row, strict=True):
            totals[state] += value
        lines.append(f"| {package} | " + " | ".join(str(value) for value in row) + " |")
    lines.append("| **Total** | " + " | ".join(str(totals[s]) for s in STATE_ORDER) + " |")
    for state in STATE_ORDER:
        if state is DocState.APPROVED:
            continue
        names = sorted(
            (name for name, (_, current) in states.items() if current is state),
            key=str.casefold,
        )
        if names:
            lines += ["", f"## {state.value.capitalize()} ({len(names)})", ""]
            lines += [f"- `{name}`" for name in names]
    if overviews:
        lines += [
            "",
            "## Overviews",
            "",
            "Package overviews (`<Package>/_package.md`) and the server overview "
            "(`_server.md`); approve one with `wm-doc approve --service package:<Package>` "
            "or `--service server`.",
            "",
            "| Overview | State |",
            "| --- | --- |",
        ]
        lines += [f"| `{name}` | {state.value} |" for name, state in overviews.items()]
    if orphans:
        lines += ["", f"## Description files without a service or package ({len(orphans)})", ""]
        lines += [f"- `{name}`" for name in orphans]
    lines.append("")
    return "\n".join(lines)


def export_designer_comments(
    docs_dir: Path, output_dir: Path, *, include_drafts: bool = False
) -> dict[str, int]:
    """Write `<Package>.txt` files of Designer comment texts; return counts per package."""
    by_package: dict[str, list[tuple[str, str, DocState]]] = {}
    for _path, doc in iter_docs(docs_dir):
        state = doc.state()
        if state not in (DocState.APPROVED, DocState.STALE) and not include_drafts:
            continue
        comment = doc.designer_comment()
        if comment:
            by_package.setdefault(doc.package or "_", []).append((doc.service, comment, state))
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, int] = {}
    for package, entries in sorted(by_package.items()):
        lines = [
            f"# Designer comments for package {package}",
            "# Paste each text into the Comments field of the service in Designer.",
            "",
        ]
        for service, comment, state in sorted(entries, key=lambda item: item[0].casefold()):
            lines += [f"[{service}] ({state.value})", comment, ""]
        (output_dir / f"{package}.txt").write_text("\n".join(lines), encoding="utf-8")
        written[package] = len(entries)
    return written


def approve_docs(
    docs_dir: Path,
    *,
    services: Iterable[str] = (),
    package: str | None = None,
    all_drafts: bool = False,
) -> tuple[list[str], list[str]]:
    """Mark matching drafts approved against the facts shown in their files.

    Returns (approved services, requested services that have no description file).
    """
    wanted = set(services)
    found: set[str] = set()
    approved: list[str] = []
    for path, doc in iter_docs(docs_dir):
        matches = (
            doc.service in wanted
            or (package is not None and doc.package == package)
            or all_drafts
        )
        if not matches:
            continue
        found.add(doc.service)
        if doc.status is DocStatus.APPROVED:
            continue
        doc.status = DocStatus.APPROVED
        doc.facts_hash = doc.current_facts_hash or doc.facts_hash
        write_doc(path, doc)
        approved.append(doc.service)
    return sorted(approved, key=str.casefold), sorted(wanted - found, key=str.casefold)


def render_facts_block(service: FlowService, facts: ServiceFacts) -> str:
    """Deterministic facts shown at the bottom of every description file."""
    callers = (
        ", ".join(f"`{name}`" for name in facts.callers)
        if facts.callers
        else "no service in the analysed packages"
    )
    lines = [
        "## Facts",
        "",
        "Generated by wm-doc from the package files and refreshed on every run.",
        "",
        "### Used by",
        "",
        f"Called by: {callers}.",
        "",
        render_entry_points_table(facts).rstrip(),
        "",
        "### Inputs and outputs",
        "",
    ]
    if service.specification:
        lines += [f"Specification: `{service.specification}`.", ""]
    lines += _field_lines("Input", service.signature.inputs)
    lines += _field_lines("Output", service.signature.outputs)
    lines += ["", "### Data and systems touched", "", render_effects_table(facts).rstrip()]
    return "\n".join(lines)


def _field_lines(label: str, fields: list[SignatureField]) -> list[str]:
    if not fields:
        return [f"- {label}: none declared"]
    lines = []
    for item in fields:
        kind = f"document `{item.document_reference}`" if item.document_reference else (
            f"`{item.data_type or 'unknown'}`"
        )
        if item.dimensions:
            kind += " list"
        lines.append(f"- {label} `{item.name}`: {kind}")
    return lines


@dataclass(frozen=True)
class AnswerSpec[T]:
    """What a model answer looks like, and the validated ask-and-check loop for it.

    An answer is accepted only when it parses, passes the disclosure scan, and every
    identifier-shaped name in it occurs in the facts that were sent; one corrective retry is
    allowed. Only accepted answers are cached.
    """

    prompt_version: str
    schema: dict[str, Any]
    num_predict: int
    from_payload: Callable[[Any], T | None]
    to_payload: Callable[[T], dict[str, Any]]
    text_of: Callable[[T], str]

    def ask(
        self, session: ModelSession, messages: list[dict[str, str]], prompt_facts: str
    ) -> tuple[T | None, bool, tuple[DescribeOutcome, str]]:
        """Return (answer or None, whether it came from the cache, outcome and note)."""
        key = session.cache_key(messages, self.prompt_version, self.schema, self.num_predict)
        if session.cache_dir is not None and not session.refresh:
            payload = _read_cached_payload(session.cache_dir, key, self.prompt_version)
            cached = self.from_payload(payload) if payload is not None else None
            if cached is not None:
                return cached, True, (DescribeOutcome.CACHED, "")
        conversation = list(messages)
        for attempt in range(2):
            content, failure = session.complete(conversation, self.schema, self.num_predict)
            if content is None:
                return None, False, failure
            try:
                value = self.from_payload(json.loads(content))
            except json.JSONDecodeError:
                value = None
            if value is None:
                note = "the model did not return the expected JSON"
                return None, False, (DescribeOutcome.FAILED, note)
            answer_text = self.text_of(value)
            label = unsafe_disclosure_label(answer_text)
            if label is not None:
                note = f"the answer failed the disclosure scan: {label}"
                correction = DISCLOSURE_RETRY_PROMPT_TEMPLATE.format(label=label)
            else:
                unknown = unknown_names(answer_text, prompt_facts)
                if not unknown:
                    if session.cache_dir is not None:
                        _write_cached_payload(
                            session.cache_dir, key, self.prompt_version, self.to_payload(value)
                        )
                    return value, False, (DescribeOutcome.GENERATED, "")
                names = ", ".join(f"`{name}`" for name in unknown[:6])
                note = f"the model's answer named things that are not in the facts: {names}"
                correction = RETRY_PROMPT_TEMPLATE.format(names=names)
            if attempt == 1:
                return None, False, (DescribeOutcome.REJECTED, note)
            with session.lock:
                session.stats.retried += 1
            conversation = [
                *messages,
                {"role": "assistant", "content": content},
                {"role": "user", "content": correction},
            ]
        raise AssertionError("unreachable")


class ModelSession:
    """One model on one provider, shared by describe and overview runs."""

    def __init__(
        self,
        provider: ModelProvider,
        *,
        model: str,
        model_digest: str | None,
        num_ctx: int,
        timeout_seconds: int,
        cache_dir: Path | None,
        refresh: bool,
    ) -> None:
        self.provider = provider
        self.model = model
        self.model_digest = model_digest
        self.num_ctx = num_ctx
        self.timeout_seconds = timeout_seconds
        self.cache_dir = cache_dir
        self.refresh = refresh
        self.stats = DescribeStats()
        self.lock = threading.Lock()

    def complete(
        self, messages: list[dict[str, str]], schema: dict[str, Any], num_predict: int
    ) -> tuple[str | None, tuple[DescribeOutcome, str]]:
        """One provider call; refuses answers to prompts the server may have cut off."""
        try:
            generation = self.provider.generate(
                ProviderGenerationRequest(
                    model=self.model,
                    messages=messages,
                    schema=schema,
                    timeout_seconds=self.timeout_seconds,
                    num_ctx=self.num_ctx,
                    num_predict=num_predict,
                )
            )
        except OllamaProviderError as exc:
            return None, (DescribeOutcome.FAILED, f"generation failed: {exc.safe_message}")
        # Native Ollama reports prompt_eval_count; the /v1 API reports prompt_tokens.
        prompt_tokens = generation.metrics.get(
            "prompt_eval_count", generation.metrics.get("prompt_tokens")
        )
        if isinstance(prompt_tokens, int):
            with self.lock:
                self.stats.prompt_tokens.append(prompt_tokens)
            if prompt_tokens >= self.num_ctx - num_predict:
                return None, (
                    DescribeOutcome.FAILED,
                    "the prompt may have been cut off by the model server "
                    f"({prompt_tokens} prompt tokens for a {self.num_ctx}-token window)",
                )
        return generation.content, (DescribeOutcome.GENERATED, "")

    def cache_key(
        self,
        messages: list[dict[str, str]],
        prompt_version: str,
        schema: dict[str, Any],
        num_predict: int,
    ) -> str:
        payload = {
            "prompt_version": prompt_version,
            "model": self.model,
            "model_digest": self.model_digest or "UNKNOWN",
            "messages": messages,
            "schema": schema,
            "options": {
                "temperature": TEMPERATURE,
                "num_ctx": self.num_ctx,
                "num_predict": num_predict,
            },
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cache_path(cache_dir: Path, key: str) -> Path:
    return cache_dir / key[:2] / f"{key}.json"


def _read_cached_payload(cache_dir: Path, key: str, prompt_version: str) -> Any:
    try:
        payload = json.loads(_cache_path(cache_dir, key).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("prompt_version") != prompt_version:
        return None
    # "narrative" is the key used by the first describe release.
    return payload.get("answer", payload.get("narrative"))


def _write_cached_payload(
    cache_dir: Path, key: str, prompt_version: str, answer: dict[str, Any]
) -> None:
    path = _cache_path(cache_dir, key)
    payload = {"prompt_version": prompt_version, "answer": answer}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        os.replace(temp, path)
    except OSError:
        return  # a cache write failure only costs a regeneration next time


class _Run:
    def __init__(
        self,
        services: dict[str, FlowService],
        facts: dict[str, ServiceFacts],
        session: ModelSession,
        options: DescribeOptions,
        order: list[str],
    ) -> None:
        self.services = services
        self.facts = facts
        self.session = session
        self.options = options
        self.position = {name: index for index, name in enumerate(order)}
        self.stats = session.stats
        self.generated: dict[str, str] = {}
        self.lock = session.lock
        # Description files as they were before this run. Reading them up front keeps the
        # prompts independent of the order in which parallel requests finish.
        needed = set(order)
        for name in order:
            needed.update(self.local_callees(name))
        self.docs: dict[str, ServiceDoc | None] = {
            name: read_doc(self.path(name)) for name in sorted(needed)
        }

    # Context ---------------------------------------------------------------------------

    def local_callees(self, name: str) -> list[str]:
        return sorted(
            {
                dependency.target_service
                for dependency in self.services[name].unique_dependencies
                if dependency.resolved
                and dependency.target_service in self.services
                and dependency.target_service != name
            }
        )

    def doc(self, name: str) -> ServiceDoc | None:
        return self.docs.get(name)

    def path(self, name: str) -> Path:
        return doc_path(self.options.docs_dir, self.services[name].identity.package, name)

    def callee_notes_for(self, current: str) -> Callable[[str], str | None]:
        """Callee context for *current*: approved or edited text first, then drafts."""

        def note(target: str) -> str | None:
            if target not in self.services:
                return None
            existing = self.doc(target)
            if existing is not None and existing.protected:
                return existing.purpose_line()
            earlier = self.position.get(target, len(self.position)) < self.position[current]
            if earlier:
                with self.lock:
                    generated = self.generated.get(target)
                if generated:
                    return generated
            if existing is not None:
                return existing.purpose_line()
            return None

        return note

    def external_note(self, target: str) -> str | None:
        system = self.options.external_systems.match(target)
        return system_label(system) if system is not None else None

    # One service -----------------------------------------------------------------------

    def describe(self, name: str) -> DescribeResult:
        service = self.services[name]
        facts = self.facts[name]
        comments = load_flow_comments(self.options.scan_root, service, self.options.config)
        deterministic = deterministic_facts(service, facts, comments, self.external_note)
        current_hash = facts_hash(deterministic)
        facts_markdown = render_facts_block(service, facts)
        path = self.path(name)
        existing = self.doc(name)

        if existing is not None and (
            existing.protected
            or (existing.facts_hash == current_hash and not self.options.redo_drafts)
        ):
            existing.facts_markdown = facts_markdown
            existing.current_facts_hash = current_hash
            write_doc(path, existing)
            outcome = (
                DescribeOutcome.PROTECTED if existing.protected else DescribeOutcome.UNCHANGED
            )
            if not existing.protected:
                line = existing.purpose_line()
                if line:
                    with self.lock:
                        self.generated[name] = line
            return DescribeResult(name, outcome, path)

        opaque = service.service_type is ServiceType.OPAQUE
        template = OPAQUE_PROMPT_TEMPLATE if opaque else USER_PROMPT_TEMPLATE
        prompt_facts, shortened = fit_facts(
            service,
            self.callee_notes_for(name),
            comments,
            self.options.num_ctx,
            facts_text=facts.text(),
            external_note=self.external_note,
            overhead_chars=len(SYSTEM_PROMPT) + len(template),
            num_predict=DESCRIBE_NUM_PREDICT,
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": template.format(facts=prompt_facts)},
        ]
        narrative, from_cache, failure = DESCRIBE_SPEC.ask(
            self.session, messages, prompt_facts
        )
        if narrative is not None and opaque:
            narrative = replace(
                narrative,
                steps=opaque_steps(service),
                error_handling=OPAQUE_ERROR_HANDLING,
            )
        if narrative is None:
            outcome, note = failure
            if existing is not None:
                existing.facts_markdown = facts_markdown
                existing.current_facts_hash = current_hash
                write_doc(path, existing)
            return DescribeResult(name, outcome, path if existing else None, note, shortened)

        doc = new_doc(
            name,
            service.identity.package,
            narrative,
            model=self.options.model,
            facts=deterministic,
            facts_markdown=facts_markdown,
        )
        if existing is not None:
            doc.notes = existing.notes
            doc.extra_front_matter = existing.extra_front_matter
        write_doc(path, doc)
        line = doc.purpose_line()
        if line:
            with self.lock:
                self.generated[name] = line
        outcome = DescribeOutcome.CACHED if from_cache else DescribeOutcome.GENERATED
        return DescribeResult(name, outcome, path, None, shortened)


def opaque_steps(service: FlowService) -> tuple[str, ...]:
    """The steps of an adapter or other opaque service, written by the tool from its facts."""
    if service.adapter is None:
        source_type = service.source_service_type or "opaque"
        return (f"Not analysed: the implementation of this `{source_type}` service is not read.",)
    # "JDBC adapter service (template `Select`): selects rows from ..." -> "Selects rows from ..."
    operation = (adapter_sentence(service) or "").split(": ", 1)[-1]
    return (operation[:1].upper() + operation[1:],)


def parse_narrative(content: str) -> Narrative | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    return narrative_from_payload(payload)


def narrative_from_payload(payload: Any) -> Narrative | None:
    if not isinstance(payload, dict):
        return None
    texts: dict[str, str] = {}
    for name, limit in FIELD_LIMITS.items():
        value = payload.get(name)
        if not isinstance(value, str):
            return None
        texts[name] = clean_text(value, limit)
    steps_value = payload.get("steps")
    comment = payload.get("designer_comment")
    if not isinstance(steps_value, list) or not isinstance(comment, str):
        return None
    steps = tuple(
        clean_text(step, MAX_STEP_CHARS)
        for step in steps_value[:MAX_STEPS]
        if isinstance(step, str)
    )
    # Small models sometimes emit punctuation-only items such as ",".
    steps = tuple(step for step in steps if sum(char.isalpha() for char in step) >= 3)
    if not texts["purpose"]:
        return None
    return Narrative(
        purpose=texts["purpose"],
        usage=texts["usage"],
        data_effects=texts["data_effects"],
        steps=steps,
        error_handling=texts["error_handling"],
        designer_comment=clean_text(comment.replace("`", ""), MAX_DESIGNER_COMMENT_CHARS),
    )


def narrative_text(narrative: Narrative) -> str:
    return "\n".join(
        [
            narrative.purpose,
            narrative.usage,
            narrative.data_effects,
            *narrative.steps,
            narrative.error_handling,
            narrative.designer_comment,
        ]
    )


def narrative_payload(narrative: Narrative) -> dict[str, Any]:
    return {
        "purpose": narrative.purpose,
        "usage": narrative.usage,
        "data_effects": narrative.data_effects,
        "steps": list(narrative.steps),
        "error_handling": narrative.error_handling,
        "designer_comment": narrative.designer_comment,
    }


DESCRIBE_SPEC: AnswerSpec[Narrative] = AnswerSpec(
    prompt_version=DESCRIBE_PROMPT_VERSION,
    schema=DESCRIBE_SCHEMA,
    num_predict=DESCRIBE_NUM_PREDICT,
    from_payload=lambda payload: narrative_from_payload(payload),
    to_payload=lambda narrative: narrative_payload(narrative),
    text_of=lambda narrative: narrative_text(narrative),
)


def clean_text(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    if flat[:1] in {"#", ">", "-", "*", "+", "|"}:
        flat = "\\" + flat
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    sentence_end = cut.rfind(". ")
    return cut[: sentence_end + 1] if sentence_end > limit // 2 else cut.rstrip() + "..."
