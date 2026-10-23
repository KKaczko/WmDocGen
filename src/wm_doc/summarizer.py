"""Shared helpers for model prompts about one service.

- :func:`fit_facts` renders the richest pseudo-code view (see :mod:`wm_doc.pseudocode`) that
  fits the model's context window, dropping mapping detail first and then trailing lines.
- :func:`unknown_names` is the grounding check: every identifier-shaped name in an answer
  must occur in the facts that were sent.

The per-service workflow that uses them lives in :mod:`wm_doc.describer`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path

from wm_doc.ir import FlowService
from wm_doc.pseudocode import (
    DETAIL_LADDER,
    FULL_DETAIL,
    MINIMAL_DETAIL,
    render_pseudocode,
)

DEFAULT_NUM_CTX = 16384
DEFAULT_NUM_PREDICT = 1024
PROMPT_MARGIN_TOKENS = 256
# Deliberately pessimistic: identifier-heavy pseudo-code averages 3.5-4 characters per
# token, so estimating 3 keeps prompts inside the window without asking the server.
CHARS_PER_TOKEN = 3
DEFAULT_OVERHEAD_CHARS = 2000

_NAME_RE = re.compile(r"[A-Za-z_$][\w$]*(?:[.:/][A-Za-z_$][\w$]*)*")
_SPLIT_RE = re.compile(r"[.:/]")
_COMMON_ABBREVIATIONS = {"e.g", "i.e", "etc", "vs"}


def default_cache_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        return Path(local_app_data) / "wm-doc" / "service-docs-cache"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "wm-doc" / "service-docs-cache"
    return Path.home() / ".cache" / "wm-doc" / "service-docs-cache"


def fit_facts(
    service: FlowService,
    callee_note: Callable[[str], str | None],
    comments: Mapping[str, str],
    num_ctx: int,
    *,
    facts_text: str | None = None,
    external_note: Callable[[str], str | None] | None = None,
    overhead_chars: int = DEFAULT_OVERHEAD_CHARS,
    num_predict: int = DEFAULT_NUM_PREDICT,
    callee_outputs: Callable[[str], str | None] | None = None,
) -> tuple[str, bool]:
    """Render the richest pseudo-code that fits the context window.

    `overhead_chars` is the size of the instructions sent around the facts and
    `num_predict` the tokens reserved for the answer. Returns the facts and whether
    anything was left out to make them fit.
    """
    budget_tokens = num_ctx - num_predict - PROMPT_MARGIN_TOKENS
    budget_chars = max(budget_tokens * CHARS_PER_TOKEN - overhead_chars, 1000)
    for detail in DETAIL_LADDER:
        facts = render_pseudocode(
            service,
            callee_note,
            comments=comments,
            detail=detail,
            facts_text=facts_text,
            external_note=external_note,
            callee_outputs=callee_outputs,
        )
        if len(facts) <= budget_chars:
            return facts, detail is not FULL_DETAIL
    facts = render_pseudocode(
        service,
        callee_note,
        comments=comments,
        detail=MINIMAL_DETAIL,
        facts_text=facts_text,
        external_note=external_note,
        callee_outputs=callee_outputs,
    )
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
        if folded in full_names or _is_part_of_a_fact_name(folded, full_names):
            continue  # e.g. config.xml from ./packages/PGP/config/config.xml
        pieces = [piece for piece in _SPLIT_RE.split(folded) if piece]
        if "/" in candidate and all(piece in parts for piece in pieces):
            continue  # a pipeline path whose segments all occur in the facts
        if len(pieces) == 1 and folded in parts:
            continue
        if candidate not in unknown:
            unknown.append(candidate)
    return unknown


def _is_part_of_a_fact_name(candidate: str, full_names: set[str]) -> bool:
    """True when *candidate* is a run of whole segments inside a name from the facts."""
    for name in full_names:
        start = name.find(candidate)
        while start >= 0:
            end = start + len(candidate)
            before_ok = start == 0 or name[start - 1] in ".:/"
            after_ok = end == len(name) or name[end] in ".:/"
            if before_ok and after_ok:
                return True
            start = name.find(candidate, start + 1)
    return False


def _is_prose_alternatives(token: str) -> bool:
    """`public/private` or `encryption/decryption`: plain words joined by a slash."""
    if "/" not in token or any(separator in token for separator in ".:"):
        return False
    pieces = [piece for piece in token.split("/") if piece]
    return len(pieces) > 1 and all(piece.isalpha() and piece.islower() for piece in pieces)


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
    if _is_prose_alternatives(token):
        return False
    if any(separator in token for separator in ".:/"):
        return True
    if "_" in token or "$" in token or any(char.isdigit() for char in token):
        return True
    return any(char.isupper() for char in token[1:])
