"""Print the document an adapter node's `IRTNODE_PROPERTY` holds, as IS would export it.

Developer tool for checking the decoder against Integration Server (offline, read-only):

    uv run python scripts/decode_adapter.py path/to/node.ndf
    uv run python scripts/decode_adapter.py path/to/node.ndf --compare path/to/expected.json
    uv run python scripts/decode_adapter.py samples/jdbcadapter            # every sample folder

The JSON has the shape of `pub.json:documentToJSONString`: compact, keys in document order,
document and array classes left out, Integers as numbers. Values of secret-like keys
(`password`, ...) are printed as `<redacted>` unless `--show-secrets` is given. `--compare`
compares the whole document with an exported JSON (order of keys free, order of lists and
value types exact) and prints only the paths that differ, never their values. Unconfirmed
readings the decoder needed are printed on stderr. Exit code 1 when a file cannot be decoded
or a comparison differs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wm_doc.idata_binary import IDataBinaryError, decode_base64, decode_idata_hypotheses, to_plain
from wm_doc.secret_guard import is_secret_name
from wm_doc.values import parse_values_file, scalar_value

REDACTED = "<redacted>"


def _redacted(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: REDACTED if is_secret_name(key) else _redacted(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    return value


def _differences(actual: object, expected: object, path: str = "$") -> list[str]:
    if type(actual) is not type(expected):
        return [f"{path}: type {type(actual).__name__} != {type(expected).__name__}"]
    if isinstance(actual, dict) and isinstance(expected, dict):
        found = [f"{path}.{key}: missing in the decoded document" for key in expected
                 if key not in actual]
        found += [f"{path}.{key}: not in the exported JSON" for key in actual
                  if key not in expected]
        for key in actual:
            if key in expected:
                found += _differences(actual[key], expected[key], f"{path}.{key}")
        return found
    if isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            return [f"{path}: {len(actual)} items != {len(expected)}"]
        found = []
        for index, (left, right) in enumerate(zip(actual, expected, strict=True)):
            found += _differences(left, right, f"{path}[{index}]")
        return found
    return [] if actual == expected else [f"{path}: values differ"]


def _decode(node: Path) -> tuple[object, tuple[str, ...]]:
    blob = scalar_value(parse_values_file(node), "IRTNODE_PROPERTY")
    if not blob:
        raise IDataBinaryError("absent", "the node has no IRTNODE_PROPERTY value")
    decoded = decode_idata_hypotheses(decode_base64(blob))
    return to_plain(decoded.document), decoded.hypotheses


def _one(node: Path, compare: Path | None, show_secrets: bool) -> bool:
    try:
        document, hypotheses = _decode(node)
    except IDataBinaryError as error:
        print(f"{node}: not decoded: {error.code}: {error}", file=sys.stderr)
        return False
    if hypotheses:
        print(f"{node}: unconfirmed readings used: {', '.join(hypotheses)}", file=sys.stderr)
    if compare is None:
        shown = document if show_secrets else _redacted(document)
        print(json.dumps(shown, ensure_ascii=False, separators=(",", ":")))
        return True
    expected = json.loads(compare.read_text(encoding="utf-8"))
    differences = _differences(document, expected)
    if not differences:
        print(f"{node}: equal to {compare.name}")
        return True
    print(f"{node}: {len(differences)} difference(s) from {compare.name}:")
    for line in differences:
        print(f"  {line}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print or compare an adapter node's document.")
    parser.add_argument("path", type=Path, help="a node.ndf, or a folder of sample folders")
    parser.add_argument("--compare", type=Path, help="the JSON Integration Server exported")
    parser.add_argument("--show-secrets", action="store_true", help="print secret-like values")
    args = parser.parse_args(argv)
    if args.path.is_dir():
        # samples/jdbcadapter: every folder, at any depth, with a node.ndf and an exported JSON.
        folders = sorted(
            node.parent
            for node in args.path.rglob("node.ndf")
            if node.is_file() and any(node.parent.glob("*.json"))
        )
        results = [
            _one(folder / "node.ndf", sorted(folder.glob("*.json"))[0], False)
            for folder in folders
        ]
        return 0 if results and all(results) else 1
    return 0 if _one(args.path, args.compare, args.show_secrets) else 1


if __name__ == "__main__":
    raise SystemExit(main())
