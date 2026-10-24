"""Package and server overviews.

Two layers, like service descriptions:

- Deterministic package facts (:func:`summarize_packages`): the services of each package, the
  entry points through which work reaches it from outside (artifacts and processes that name a
  service, callers in other packages, services nothing calls), the data and systems its
  services touch, and the packages it calls and is called by. The site's package pages render
  these directly.
- Model-written overview files, drafted from those facts plus the Purpose lines of the
  services: `<docs-dir>/<Package>/_package.md` per package and `<docs-dir>/_server.md` for the
  whole server, written from the package overviews. They follow the rules of service
  descriptions: drafts until approved, never overwritten once approved or edited, and reported
  as "approved, facts changed" when their facts change. Purpose lines are context, not facts,
  so rewording a service description does not mark an approved overview as changed.
"""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wm_doc.describer import (
    AnswerSpec,
    DescribeError,
    DescribeOptions,
    DescribeOutcome,
    DescribeResult,
    DescribeStats,
    ModelSession,
    ProgressCallback,
    clean_text,
    open_session,
    system_prompt,
)
from wm_doc.effects import ServiceFacts, compute_service_facts, entry_markers
from wm_doc.ir import AnalysisResult, ServiceType
from wm_doc.ollama_provider import ModelProvider
from wm_doc.render.service_summary import render_service_summary
from wm_doc.service_docs import (
    PACKAGE_OVERVIEW_PREFIX,
    SERVER_OVERVIEW,
    DocState,
    ServiceDoc,
    facts_hash,
    load_service_docs,
    new_doc,
    overview_doc_path,
    read_doc,
    write_doc,
)
from wm_doc.summarizer import CHARS_PER_TOKEN, PROMPT_MARGIN_TOKENS

OVERVIEW_PROMPT_VERSION = "overview-prompt.v1"
OVERVIEW_NUM_PREDICT = 1536
MAX_OVERVIEW_ITEMS = 10
MAX_ITEM_CHARS = 240
OVERVIEW_FIELD_LIMITS = {"purpose": 700, "entry_points": 700, "systems_and_data": 900}
MAX_CALLERS_PER_ENTRY = 3
MAX_SERVER_ROWS = 40
NO_CALLERS = "no callers in the analysed packages"
OTHER_PACKAGE_PREFIX = "package "
TYPE_LABELS = {ServiceType.FLOW: "FLOW", ServiceType.JAVA: "Java", ServiceType.OPAQUE: "other"}

OVERVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "purpose": {"type": "string"},
        "items": {"type": "array", "items": {"type": "string"}},
        "entry_points": {"type": "string"},
        "systems_and_data": {"type": "string"},
    },
    "required": ["purpose", "items", "entry_points", "systems_and_data"],
    "additionalProperties": False,
}

OVERVIEW_SYSTEM_PROMPT = (
    "You write overview documentation for webMethods Integration Server packages. You are "
    "given facts established by static analysis, including one-line purposes of services. "
    "Use only these facts. Do not invent systems, users, schedules, tables or business rules. "
    "Copy package, service, document and system names exactly as written; never translate or "
    "shorten them. If the business purpose is not clear from the facts, describe what the "
    "code does technically."
)

PACKAGE_PROMPT_TEMPLATE = (
    "Facts about one package:\n```\n{facts}\n```\n"
    "Return JSON with these fields, in English:\n"
    "- purpose: two or three sentences on what this package is for.\n"
    "- items: three to eight short items, the main capabilities of the package.\n"
    "- entry_points: one to three sentences on how work enters the package (triggers and other "
    "artifacts, calls from other packages, services nothing calls).\n"
    "- systems_and_data: one to three sentences on the systems, messages, files and data the "
    "package touches."
)

SERVER_PROMPT_TEMPLATE = (
    "Facts about an Integration Server and its packages:\n```\n{facts}\n```\n"
    "Return JSON with these fields, in English:\n"
    "- purpose: two or three sentences on what this server does overall.\n"
    "- items: three to ten items, one per business area, naming the packages involved.\n"
    "- entry_points: one to three sentences on how work enters the server.\n"
    "- systems_and_data: one to three sentences on the external systems, messaging and data "
    "the server works with."
)


@dataclass(frozen=True)
class PackageEntry:
    """A service that work reaches from outside its package, and from where."""

    service: str
    reached_from: tuple[str, ...]


@dataclass(frozen=True)
class EffectRow:
    action: str
    object: str
    where: str
    services: tuple[str, ...]


@dataclass(frozen=True)
class PackageSummary:
    name: str
    services: tuple[str, ...]
    service_types: dict[str, str]
    document_count: int
    entries: tuple[PackageEntry, ...]
    effects: tuple[EffectRow, ...]
    calls_into: tuple[tuple[str, int], ...]
    called_from: tuple[tuple[str, int], ...]

    def type_counts(self) -> Counter[str]:
        return Counter(self.service_types.values())


@dataclass(frozen=True)
class OverviewNarrative:
    kind: str  # "package" or "server"
    purpose: str
    items: tuple[str, ...]
    entry_points: str
    systems_and_data: str

    def markdown(self) -> str:
        heading = "## Main capabilities" if self.kind == "package" else "## Business areas"
        items = "\n".join(f"- {item}" for item in self.items) or "-"
        return (
            f"## Purpose\n\n{self.purpose}\n\n{heading}\n\n{items}\n\n"
            f"## Entry points\n\n{self.entry_points}\n\n"
            f"## Systems and data\n\n{self.systems_and_data}\n"
        )


def summarize_packages(
    analysis: AnalysisResult, facts: Mapping[str, ServiceFacts]
) -> dict[str, PackageSummary]:
    """Deterministic facts per package, built from the per-service facts."""
    package_of = {s.identity.full_name: s.identity.package for s in analysis.services}
    markers = entry_markers(analysis)
    summaries: dict[str, PackageSummary] = {}
    for package in analysis.packages:
        services = sorted(package.services, key=lambda s: s.identity.full_name.casefold())
        entries: list[PackageEntry] = []
        effect_services: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        calls_into: Counter[str] = Counter()
        called_from: Counter[str] = Counter()
        for service in services:
            name = service.identity.full_name
            service_facts = facts.get(name)
            callers = service_facts.callers if service_facts is not None else ()
            outside = [caller for caller in callers if package_of.get(caller) != package.name]
            reached = [f"{kind} {marker}" for kind, marker in markers.get(name, [])]
            reached += [
                f"{OTHER_PACKAGE_PREFIX}{package_of.get(caller, '?')} (`{caller}`)"
                for caller in outside[:MAX_CALLERS_PER_ENTRY]
            ]
            if len(outside) > MAX_CALLERS_PER_ENTRY:
                reached.append(f"{len(outside) - MAX_CALLERS_PER_ENTRY} more outside callers")
            if not callers and not reached:
                reached.append(NO_CALLERS)
            if reached:
                entries.append(PackageEntry(name, tuple(reached)))
            for caller in outside:
                called_from[package_of[caller]] += 1
            for dependency in service.unique_dependencies:
                target_package = package_of.get(dependency.target_service)
                if dependency.resolved and target_package and target_package != package.name:
                    calls_into[target_package] += 1
            for effect in service_facts.effects if service_facts is not None else ():
                # Own effects only: callees' effects are counted on the callee's package, and
                # signature documents describe a single service.
                if effect.via or not effect.propagates:
                    continue
                effect_services[(effect.action, effect.object, effect.where)].add(name)
        effects = sorted(
            (
                EffectRow(action, obj, where, tuple(sorted(users, key=str.casefold)))
                for (action, obj, where), users in effect_services.items()
            ),
            key=lambda row: (-len(row.services), row.action, row.object, row.where),
        )
        summaries[package.name] = PackageSummary(
            name=package.name,
            services=tuple(s.identity.full_name for s in services),
            service_types={
                s.identity.full_name: TYPE_LABELS.get(s.service_type, s.service_type.value)
                for s in services
            },
            document_count=len(package.document_types),
            entries=tuple(entries),
            effects=tuple(effects),
            calls_into=_sorted_counts(calls_into),
            called_from=_sorted_counts(called_from),
        )
    return summaries


def service_purposes(
    analysis: AnalysisResult, docs: Mapping[str, ServiceDoc]
) -> dict[str, str]:
    """Purpose line per service: from its description file, else its deterministic summary."""
    purposes: dict[str, str] = {}
    for service in analysis.services:
        name = service.identity.full_name
        doc = docs.get(name)
        line = doc.purpose_line() if doc is not None else None
        if not line:
            summary = " ".join(render_service_summary(service).split())
            end = summary.find(". ")
            line = summary[: end + 1] if end > 0 else summary
        purposes[name] = line
    return purposes


def package_facts_text(
    summary: PackageSummary,
    purposes: Mapping[str, str] | None = None,
    max_chars: int | None = None,
) -> str:
    """Plain-text package facts. Without `purposes` this is what the facts hash covers."""
    counts = summary.type_counts()
    header = (
        f"package {summary.name}: {_services_count(len(summary.services))} "
        f"({counts.get('FLOW', 0)} FLOW, {counts.get('Java', 0)} Java, "
        f"{counts.get('other', 0)} other), {_count(summary.document_count, 'document type')}"
    )

    def purpose_of(name: str) -> str:
        purpose = purposes.get(name) if purposes is not None else None
        return f" | purpose: {purpose}" if purpose else ""

    entries = [
        f"  {entry.service}: {'; '.join(entry.reached_from)}{purpose_of(entry.service)}"
        for entry in summary.entries
    ]
    # Entry points already carry their purpose; each purpose line is sent once.
    entry_names = {entry.service for entry in summary.entries}
    services = [
        f"  {name} [{summary.service_types[name]}]"
        + ("" if name in entry_names else purpose_of(name))
        for name in summary.services
    ]
    effects = [
        f"  {row.action}: {row.object} -> {row.where} ({_services_count(len(row.services))})"
        for row in summary.effects
    ]
    tail = [
        "calls into other packages: " + _counts_text(summary.calls_into),
        "called from other packages: " + _counts_text(summary.called_from),
    ]
    sections = [
        ("entry points (reached from outside the package):", entries),
        ("services:", services),
        ("data and systems touched by the package's own services:", effects),
    ]
    return _fit_sections(header, sections, tail, max_chars, trim_order=(1, 2, 0))


def server_facts_text(
    summaries: Mapping[str, PackageSummary],
    package_purposes: Mapping[str, str] | None = None,
    max_chars: int | None = None,
) -> str:
    """Plain-text server facts. Without `package_purposes` this is what the hash covers."""
    ordered = sorted(summaries.values(), key=lambda summary: summary.name.casefold())
    header = f"server: {len(ordered)} packages, {sum(len(s.services) for s in ordered)} services"

    def purpose_of(name: str) -> str:
        purpose = package_purposes.get(name) if package_purposes is not None else None
        return f" | purpose: {purpose}" if purpose else ""

    packages = [
        f"  {summary.name}: {_services_count(len(summary.services))}, "
        f"{_count(len(summary.entries), 'entry point')}{purpose_of(summary.name)}"
        for summary in ordered
    ]
    calls = [
        f"  {summary.name} -> {target} ({count} calls)"
        for summary in ordered
        for target, count in summary.calls_into
    ]
    touched: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    kinds: Counter[str] = Counter()
    for summary in ordered:
        for row in summary.effects:
            # Calls to external systems are grouped by system, not by the service called.
            obj = "" if row.action == "calls" else row.object
            touched[(row.action, obj, row.where)].add(summary.name)
        for entry in summary.entries:
            for reached in entry.reached_from:
                kinds[_entry_kind(reached)] += 1
    rows = sorted(touched.items(), key=lambda item: (-len(item[1]), *item[0]))
    data = [
        f"  {action}: {obj + ' -> ' if obj else ''}{where} "
        f"(packages: {', '.join(sorted(users, key=str.casefold))})"
        for (action, obj, where), users in rows[:MAX_SERVER_ROWS]
    ]
    if len(rows) > MAX_SERVER_ROWS:
        data.append(f"  ... and {len(rows) - MAX_SERVER_ROWS} more")
    kind_lines = [f"  {kind}: {count}" for kind, count in sorted(kinds.items())]
    sections = [
        ("packages:", packages),
        ("calls between packages:", calls),
        ("data, systems and messaging touched:", data),
        ("entry points by kind:", kind_lines),
    ]
    return _fit_sections(header, sections, [], max_chars, trim_order=(1, 2, 0))


def _entry_kind(reached: str) -> str:
    if reached == NO_CALLERS:
        return "services with no callers"
    if reached.startswith(OTHER_PACKAGE_PREFIX) or reached.endswith("more outside callers"):
        return "calls from other packages"
    return reached.split(" `", 1)[0]


def _fit_sections(
    header: str,
    sections: list[tuple[str, list[str]]],
    tail: list[str],
    max_chars: int | None,
    *,
    trim_order: tuple[int, ...],
) -> str:
    """Join sections; to fit `max_chars`, drop trailing lines of sections in `trim_order`."""
    kept = [list(lines) for _title, lines in sections]
    hidden = [0] * len(sections)

    def render() -> str:
        out = [header]
        for index, (title, _lines) in enumerate(sections):
            out.append(title)
            out.extend(kept[index] or ([] if hidden[index] else ["  none"]))
            if hidden[index]:
                out.append(f"  ... {hidden[index]} more, left out to fit the context window")
        out.extend(tail)
        return "\n".join(out)

    text = render()
    if max_chars is None:
        return text
    for index in trim_order:
        while len(text) > max_chars and kept[index]:
            # Remove lines in chunks so very long lists are trimmed in few renders.
            excess = len(text) - max_chars
            drop = 1
            while drop < len(kept[index]) and sum(
                len(line) + 1 for line in kept[index][-drop:]
            ) < excess:
                drop += 1
            del kept[index][-drop:]
            hidden[index] += drop
            text = render()
    return text


def facts_markdown_block(kind: str, facts_text: str) -> str:
    return (
        "## Facts\n\n"
        f"Generated by wm-doc from the analysed {kind}; refreshed on every run.\n\n"
        f"```text\n{facts_text}\n```"
    )


def overview_from_payload(payload: Any, kind: str) -> OverviewNarrative | None:
    if not isinstance(payload, dict):
        return None
    texts: dict[str, str] = {}
    for name, limit in OVERVIEW_FIELD_LIMITS.items():
        value = payload.get(name)
        if not isinstance(value, str):
            return None
        texts[name] = clean_text(value, limit)
    items_value = payload.get("items")
    if not isinstance(items_value, list) or not texts["purpose"]:
        return None
    cleaned = [
        clean_text(item, MAX_ITEM_CHARS)
        for item in items_value[:MAX_OVERVIEW_ITEMS]
        if isinstance(item, str)
    ]
    return OverviewNarrative(
        kind=kind,
        purpose=texts["purpose"],
        items=tuple(item for item in cleaned if sum(char.isalpha() for char in item) >= 3),
        entry_points=texts["entry_points"],
        systems_and_data=texts["systems_and_data"],
    )


def overview_payload(narrative: OverviewNarrative) -> dict[str, Any]:
    return {
        "purpose": narrative.purpose,
        "items": list(narrative.items),
        "entry_points": narrative.entry_points,
        "systems_and_data": narrative.systems_and_data,
    }


def overview_text(narrative: OverviewNarrative) -> str:
    return "\n".join(
        [narrative.purpose, *narrative.items, narrative.entry_points, narrative.systems_and_data]
    )


def _overview_spec(kind: str) -> AnswerSpec[OverviewNarrative]:
    return AnswerSpec(
        prompt_version=OVERVIEW_PROMPT_VERSION,
        schema=OVERVIEW_SCHEMA,
        num_predict=OVERVIEW_NUM_PREDICT,
        from_payload=lambda payload: overview_from_payload(payload, kind),
        to_payload=overview_payload,
        text_of=overview_text,
    )


PACKAGE_SPEC = _overview_spec("package")
SERVER_SPEC = _overview_spec("server")


def overview_states(
    analysis: AnalysisResult,
    docs_dir: Path,
    facts: Mapping[str, ServiceFacts],
) -> dict[str, DocState]:
    """`package:<P>` and `server` -> the state of their overview files."""
    summaries = summarize_packages(analysis, facts)
    states: dict[str, DocState] = {}
    for name, summary in sorted(summaries.items(), key=lambda item: item[0].casefold()):
        doc = read_doc(overview_doc_path(docs_dir, name))
        current = facts_hash(package_facts_text(summary))
        states[f"{PACKAGE_OVERVIEW_PREFIX}{name}"] = (
            DocState.MISSING if doc is None else doc.state(current)
        )
    doc = read_doc(overview_doc_path(docs_dir, None))
    current = facts_hash(server_facts_text(summaries))
    states[SERVER_OVERVIEW] = DocState.MISSING if doc is None else doc.state(current)
    return states


def package_overview_docs(docs_dir: Path, names: Iterable[str]) -> dict[str, ServiceDoc]:
    docs: dict[str, ServiceDoc] = {}
    for name in names:
        doc = read_doc(overview_doc_path(docs_dir, name))
        if doc is not None:
            docs[name] = doc
    return docs


@dataclass(frozen=True)
class _Job:
    key: str
    package: str
    path: Path
    facts: str  # hashed and shown in the facts block
    prompt_facts: str  # facts plus purpose lines, fitted to the context window
    template: str
    spec: AnswerSpec[OverviewNarrative]
    kind: str


def describe_overviews(
    analysis: AnalysisResult,
    packages: Iterable[str],
    provider: ModelProvider,
    options: DescribeOptions,
    *,
    server: bool = False,
    progress: ProgressCallback | None = None,
) -> tuple[list[DescribeResult], DescribeStats]:
    """Write the selected package overviews, then the server overview when asked."""
    if not options.model.strip():
        raise DescribeError("--model must not be blank.")
    known = {package.name for package in analysis.packages}
    wanted = sorted(set(packages), key=str.casefold)
    unknown = [name for name in wanted if name not in known]
    if unknown:
        raise DescribeError(f"Unknown package(s): {', '.join(unknown[:5])}.")
    session = open_session(provider, options)
    facts = compute_service_facts(analysis, options.external_systems)
    summaries = summarize_packages(analysis, facts)
    purposes = service_purposes(
        analysis, load_service_docs(options.docs_dir, analysis.services)
    )
    budget = _budget_chars(
        options.num_ctx, len(system_prompt(OVERVIEW_SYSTEM_PROMPT, options.instructions)) + 800
    )
    total = len(wanted) + (1 if server else 0)
    results: list[DescribeResult] = []

    def report(result: DescribeResult) -> None:
        session.stats.add(result)
        results.append(result)
        if progress is not None:
            progress(len(results), total, result)

    jobs = [
        _Job(
            key=f"{PACKAGE_OVERVIEW_PREFIX}{name}",
            package=name,
            path=overview_doc_path(options.docs_dir, name),
            facts=package_facts_text(summaries[name]),
            prompt_facts=package_facts_text(summaries[name], purposes, budget),
            template=PACKAGE_PROMPT_TEMPLATE,
            spec=PACKAGE_SPEC,
            kind="package",
        )
        for name in wanted
    ]
    if options.parallel > 1 and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=options.parallel) as pool:
            for result in pool.map(lambda job: _describe_one(job, session, options), jobs):
                report(result)
    else:
        for job in jobs:
            report(_describe_one(job, session, options))
    if server:
        # Package overviews written above are read back here, so the server prompt sees them.
        package_purposes = {
            name: line
            for name, doc in package_overview_docs(options.docs_dir, summaries).items()
            if (line := doc.purpose_line())
        }
        job = _Job(
            key=SERVER_OVERVIEW,
            package="",
            path=overview_doc_path(options.docs_dir, None),
            facts=server_facts_text(summaries),
            prompt_facts=server_facts_text(summaries, package_purposes, budget),
            template=SERVER_PROMPT_TEMPLATE,
            spec=SERVER_SPEC,
            kind="server",
        )
        report(_describe_one(job, session, options))
    return results, session.stats


def _describe_one(job: _Job, session: ModelSession, options: DescribeOptions) -> DescribeResult:
    existing = read_doc(job.path)
    current = facts_hash(job.facts)
    block = facts_markdown_block(job.kind, job.facts)
    shortened = "left out to fit the context window" in job.prompt_facts
    if existing is not None and (
        existing.protected or (existing.facts_hash == current and not options.redo_drafts)
    ):
        _refresh_facts(job.path, existing, block, current)
        outcome = DescribeOutcome.PROTECTED if existing.protected else DescribeOutcome.UNCHANGED
        return DescribeResult(job.key, outcome, job.path)
    messages = [
        {"role": "system", "content": system_prompt(OVERVIEW_SYSTEM_PROMPT, options.instructions)},
        {"role": "user", "content": job.template.format(facts=job.prompt_facts)},
    ]
    started = time.perf_counter()
    narrative, from_cache, (outcome, note) = job.spec.ask(session, messages, job.prompt_facts)
    seconds = None if from_cache else time.perf_counter() - started
    if narrative is None:
        if existing is not None:
            _refresh_facts(job.path, existing, block, current)
        return DescribeResult(job.key, outcome, None, note, shortened, seconds)
    doc = new_doc(
        job.key, job.package, narrative, model=options.model, facts=job.facts, facts_markdown=block
    )
    if existing is not None:
        doc.notes = existing.notes
        doc.extra_front_matter = existing.extra_front_matter
    write_doc(job.path, doc)
    outcome = DescribeOutcome.CACHED if from_cache else DescribeOutcome.GENERATED
    return DescribeResult(job.key, outcome, job.path, None, shortened, seconds)


def _refresh_facts(path: Path, doc: ServiceDoc, block: str, current: str) -> None:
    doc.facts_markdown = block
    doc.current_facts_hash = current
    write_doc(path, doc)


def _budget_chars(num_ctx: int, overhead_chars: int) -> int:
    tokens = num_ctx - OVERVIEW_NUM_PREDICT - PROMPT_MARGIN_TOKENS
    return max(tokens * CHARS_PER_TOKEN - overhead_chars, 1000)


def _sorted_counts(counts: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counts.items(), key=lambda item: item[0].casefold()))


def _counts_text(counts: tuple[tuple[str, int], ...]) -> str:
    return ", ".join(f"{name} ({count} calls)" for name, count in counts) or "none"


def _services_count(count: int) -> str:
    return _count(count, "service")


def _count(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def progress_label(result: DescribeResult) -> str:
    """Human label for an overview key in progress output."""
    if result.service == SERVER_OVERVIEW:
        return "server overview"
    return f"package {result.service.removeprefix(PACKAGE_OVERVIEW_PREFIX)}"
