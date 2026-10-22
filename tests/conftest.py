"""Test-wide settings."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from wm_doc.analysis_cache import CACHE_DIR_ENV


@pytest.fixture(autouse=True, scope="session")
def _isolated_analysis_cache(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Keep CLI runs from writing analysis caches into the user's cache folder."""
    previous = os.environ.get(CACHE_DIR_ENV)
    os.environ[CACHE_DIR_ENV] = str(tmp_path_factory.mktemp("analysis-cache"))
    yield
    if previous is None:
        os.environ.pop(CACHE_DIR_ENV, None)
    else:
        os.environ[CACHE_DIR_ENV] = previous
