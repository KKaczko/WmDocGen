"""Add new sample files to tests/fixtures/checksums.sha256 (never changes existing entries).

After copying a new export into `samples/jdbcadapter/<name>/` (its node.ndf and the JSON
Integration Server exported), run:

    uv run python scripts/add_sample_checksums.py

Files already listed keep their recorded hash, so a changed sample still fails
`tests/fixtures/test_fixture_checksums.py`; only files the manifest does not list yet are
added. The decoder's golden test picks up every sample folder by itself.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "fixtures" / "checksums.sha256"
ROOTS = ("samples/PGP", "samples/Synthetic", "samples/jdbcadapter")


def main() -> int:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    entries = {line.split("  ", 1)[1]: line for line in lines if line.strip()}
    added = []
    for root in ROOTS:
        for path in sorted((ROOT / root).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if relative not in entries:
                entries[relative] = f"{sha256(path.read_bytes()).hexdigest()}  {relative}"
                added.append(relative)
    ordered = [entries[key] for key in sorted(entries)]
    MANIFEST.write_text("\n".join(ordered) + "\n", encoding="utf-8", newline="\n")
    for relative in added:
        print(f"added {relative}")
    print(f"{len(added)} file(s) added, {len(ordered)} listed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
