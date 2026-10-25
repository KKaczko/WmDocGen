"""Write an explorer bundle as deterministic files next to the prebuilt app.

Layout under the output folder:

    index.html, assets/        the prebuilt app (copied from wm_doc/explorer/app)
    THIRD-PARTY.txt            licences of the bundled libraries
    data/manifest.json         contract version, dataset, disclosure, counts, digest
    data/search.json           search index
    data/services/<id>.json    one file per service

Only these names are ever removed or replaced. The output folder may not be inside the
analysed packages folder (or contain it): analysed packages are never written to.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from wm_doc.explorer.build import ExplorerBundle
from wm_doc.output_cleanup import remove_managed_path

APP_DIR = Path(__file__).with_name("app")
DATA_DIR = "data"
STAGING_DIR = ".data-staging"
APP_FILES = ("index.html", "assets", "THIRD-PARTY.txt")


class ExplorerOutputError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(f"{code}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


@dataclass(frozen=True)
class WriteReport:
    data_files: int
    data_bytes: int
    digest: str
    app_included: bool


def check_output_location(output: Path, packages_root: Path) -> None:
    """Refuse an output folder that overlaps the analysed packages folder."""
    out = output.resolve()
    root = packages_root.resolve()
    if out == root or root in out.parents:
        raise ExplorerOutputError(
            "OUTPUT_INSIDE_PACKAGES",
            "The explorer output folder must be outside the analysed packages folder.",
        )
    if out in root.parents:
        raise ExplorerOutputError(
            "PACKAGES_INSIDE_OUTPUT",
            "The analysed packages folder must not be inside the explorer output folder.",
        )


def dump(model: BaseModel) -> bytes:
    payload = model.model_dump(mode="json", by_alias=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (text + "\n").encode("utf-8")


def render_data_files(bundle: ExplorerBundle) -> dict[str, bytes]:
    """Relative path under data/ -> file bytes, with the manifest digest filled in."""
    files: dict[str, bytes] = {"search.json": dump(bundle.search)}
    for identifier, detail in bundle.services.items():
        files[f"services/{identifier}.json"] = dump(detail)
    lines = "".join(
        f"{path} {hashlib.sha256(files[path]).hexdigest()}\n" for path in sorted(files)
    )
    digest = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    files["manifest.json"] = dump(bundle.manifest.model_copy(update={"digest": digest}))
    return files


def write_explorer(output: Path, bundle: ExplorerBundle, packages_root: Path) -> WriteReport:
    check_output_location(output, packages_root)
    output.mkdir(parents=True, exist_ok=True)
    files = render_data_files(bundle)

    remove_managed_path(output, Path(STAGING_DIR))
    staging = output / STAGING_DIR
    for relative, content in files.items():
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    remove_managed_path(output, Path(DATA_DIR))
    staging.rename(output / DATA_DIR)

    for name in APP_FILES:
        remove_managed_path(output, Path(name))
    app_included = (APP_DIR / "index.html").is_file()
    if app_included:
        for name in APP_FILES:
            source = APP_DIR / name
            if source.is_dir():
                shutil.copytree(source, output / name)
            elif source.is_file():
                shutil.copyfile(source, output / name)

    manifest = json.loads(files["manifest.json"])
    return WriteReport(
        data_files=len(files),
        data_bytes=sum(len(content) for content in files.values()),
        digest=str(manifest["digest"]),
        app_included=app_included,
    )
