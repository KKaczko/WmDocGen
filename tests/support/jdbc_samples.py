"""The real JDBC adapter samples (`samples/jdbcadapter/`) placed into a test package.

`samples/` stays read-only: the node.ndf files are copied byte for byte into a temporary
packages folder, under the namespace their `node.idf` names (`kkaczk.jdbcadapter`).
"""

from __future__ import annotations

import base64
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "samples" / "jdbcadapter"
NAMESPACE = "kkaczk.jdbcadapter"


def sample_dirs() -> list[Path]:
    """Every sample folder that holds a node.ndf and a reference JSON."""
    return sorted(
        path
        for path in SAMPLES.iterdir()
        if path.is_dir() and (path / "node.ndf").is_file() and _reference(path) is not None
    )


def _reference(folder: Path) -> Path | None:
    found = sorted(folder.glob("*.json"))
    return found[0] if found else None


def reference_json(folder: Path) -> object:
    reference = _reference(folder)
    assert reference is not None
    return json.loads(reference.read_text(encoding="utf-8"))


def property_blob(folder: Path) -> str:
    text = (folder / "node.ndf").read_text(encoding="utf-8")
    match = re.search(r'<value name="IRTNODE_PROPERTY">([^<]*)</value>', text)
    assert match is not None
    return match.group(1)


def property_bytes(folder: Path) -> bytes:
    return base64.b64decode(property_blob(folder))


def install_samples(root: Path, package: str = "JdbcSamples") -> dict[str, str]:
    """Copy the sample adapter services into `root/<package>`; folder -> full service name."""
    names: dict[str, str] = {}
    for folder in sample_dirs():
        target = root / package / "ns" / Path(*NAMESPACE.split(".")) / folder.name
        target.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(folder / "node.ndf", target / "node.ndf")
        names[folder.name] = f"{NAMESPACE}:{folder.name}"
    return names
