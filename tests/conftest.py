"""Test-wide settings."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from wm_doc.analysis_cache import CACHE_DIR_ENV


@pytest.fixture()
def out_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A folder outside `tmp_path`, for tests whose packages folder is `tmp_path` itself.

    Commands refuse to write into the packages folder they analyse.
    """
    return tmp_path_factory.mktemp("out")


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
