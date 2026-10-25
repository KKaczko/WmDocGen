"""Gather what `build_bundle` reads: facts, description files and their review states.

The states are computed exactly as `wm-doc status` computes them (current facts hashes),
so "approved, facts changed" means the same in the explorer as in the status report.
"""

from __future__ import annotations

from pathlib import Path

from wm_doc.config import AppConfig
from wm_doc.describer import current_facts_hashes
from wm_doc.effects import compute_service_facts
from wm_doc.explorer.build import ExplorerInputs
from wm_doc.external_systems import EMPTY_CATALOG, ExternalSystemCatalog
from wm_doc.ir import AnalysisResult
from wm_doc.overviews import overview_states, package_overview_docs
from wm_doc.service_docs import load_service_docs


def explorer_inputs(
    analysis: AnalysisResult,
    packages_root: Path,
    config: AppConfig,
    external_systems: ExternalSystemCatalog = EMPTY_CATALOG,
    docs_dir: Path | None = None,
) -> ExplorerInputs:
    facts = compute_service_facts(analysis, external_systems)
    if docs_dir is None:
        return ExplorerInputs(analysis=analysis, facts=facts, external_systems=external_systems)
    docs = load_service_docs(docs_dir, analysis.services)
    hashes = current_facts_hashes(
        analysis, packages_root, config, external_systems, facts=facts, only=set(docs)
    )
    return ExplorerInputs(
        analysis=analysis,
        facts=facts,
        service_docs=docs,
        service_states={name: doc.state(hashes.get(name)) for name, doc in docs.items()},
        overview_docs=package_overview_docs(docs_dir, [p.name for p in analysis.packages]),
        overview_states=overview_states(analysis, docs_dir, facts),
        external_systems=external_systems,
    )
