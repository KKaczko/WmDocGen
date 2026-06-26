from __future__ import annotations

import os
import re
import shutil
import struct
import subprocess
import tempfile
import zlib
from dataclasses import dataclass, field, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from lxml import etree

GRAPH_RENDER_TIMEOUT_SECONDS = 30
DIAGNOSTIC_LIMIT = 300
SVG_MAX_BYTES = 25 * 1024 * 1024
PNG_MAX_BYTES = 25 * 1024 * 1024

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
GRAPHVIZ_SVG_DOCTYPE_RE = re.compile(
    rb"""<!DOCTYPE\s+svg\s+PUBLIC\s+(['"])-//W3C//DTD SVG 1\.1//EN\1\s+"""
    rb"""(['"])http://www\.w3\.org/Graphics/SVG/1\.1/DTD/svg11\.dtd\2\s*>""",
    re.IGNORECASE,
)
XML_DECLARATION_RE = re.compile(rb"^\s*<\?xml\s+[^?]*\?>", re.IGNORECASE)
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
FRAGMENT_HREF_RE = re.compile(r"^#[A-Za-z_][A-Za-z0-9_.:-]*$")
STYLE_FRAGMENT_URL_RE = re.compile(r"url\(\s*(['\"]?)#[A-Za-z_][A-Za-z0-9_.:-]*\1\s*\)")
WINDOWS_ABSOLUTE_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>]+")
POSIX_ABSOLUTE_RE = re.compile(r"(?<!:)\/(?:[^\/\s\"'<>]+\/)+[^\/\s\"'<>]+")
SECRET_KEY_VALUE_RE = re.compile(
    r"""(?ix)
    (?P<key_quote>["']?)
    (?P<key>[A-Za-z][A-Za-z0-9_-]*)
    (?P=key_quote)
    (?P<separator>\s*[:=]\s*)
    (?P<value>
        "(?:[^"\\]|\\.)*" |
        '(?:[^'\\]|\\.)*' |
        [^\s,;]+(?:\s+(?![A-Za-z][A-Za-z0-9_-]*\s*[:=])[^\s,;]+){0,3}
    )
    """
)
AUTHORIZATION_RE = re.compile(
    r"(?i)\b(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)"
)
BEARER_RE = re.compile(r"(?i)\b(bearer\s+)([^\s,;]+)")
JDBC_RE = re.compile(r"(?i)\bjdbc:[^\s\"'<>]+")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REDACTED_DIAGNOSTIC_VALUE = "[REDACTED]"
SECRET_KEY_COMPACT_NAMES = {
    "apikey",
    "authorization",
    "bearer",
    "clientsecret",
    "idtoken",
    "password",
    "passphrase",
    "passwd",
    "pwd",
    "refreshtoken",
    "secret",
    "token",
}
SECRET_KEY_SUFFIX_PARTS = {
    "password",
    "passphrase",
    "passwd",
    "pwd",
    "secret",
    "token",
}


class GraphRenderMode(StrEnum):
    NONE = "none"
    SVG = "svg"
    PNG = "png"
    BOTH = "both"


class GraphRenderFormat(StrEnum):
    SVG = "svg"
    PNG = "png"


class GraphRenderStatus(StrEnum):
    RENDERED = "rendered"
    FAILED = "failed"


class GraphRenderFailureCode(StrEnum):
    EXECUTABLE_NOT_FOUND = "EXECUTABLE_NOT_FOUND"
    EXECUTABLE_NOT_RUNNABLE = "EXECUTABLE_NOT_RUNNABLE"
    PROBE_TIMEOUT = "PROBE_TIMEOUT"
    RENDER_TIMEOUT = "RENDER_TIMEOUT"
    RENDER_NONZERO_EXIT = "RENDER_NONZERO_EXIT"
    OUTPUT_EMPTY = "OUTPUT_EMPTY"
    OUTPUT_TOO_LARGE = "OUTPUT_TOO_LARGE"
    OUTPUT_READ_FAILED = "OUTPUT_READ_FAILED"
    OUTPUT_WRITE_FAILED = "OUTPUT_WRITE_FAILED"
    OUTPUT_REPLACE_FAILED = "OUTPUT_REPLACE_FAILED"
    OUTPUT_UNSAFE_SVG = "OUTPUT_UNSAFE_SVG"
    OUTPUT_INVALID_SVG = "OUTPUT_INVALID_SVG"
    OUTPUT_INVALID_PNG = "OUTPUT_INVALID_PNG"
    TEMP_FILE_FAILED = "TEMP_FILE_FAILED"
    TEMP_CLEANUP_FAILED = "TEMP_CLEANUP_FAILED"


@dataclass
class GraphAsset:
    title: str
    scope: str
    dot_path: str
    rendered_paths: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphRenderResult:
    dot_path: str
    requested_format: GraphRenderFormat
    rendered_path: str | None
    status: GraphRenderStatus
    failure_reason: str | None = None
    failure_code: GraphRenderFailureCode | None = None
    secondary_failure_code: GraphRenderFailureCode | None = None
    secondary_failure_reason: str | None = None


class GraphvizRunner(Protocol):
    def __call__(
        self,
        args: list[str],
        *,
        cwd: Path,
        timeout: int,
        capture_output: bool,
        text: bool,
        shell: bool,
    ) -> subprocess.CompletedProcess[str]:
        """Run a Graphviz subprocess."""


def run_subprocess(
    args: list[str],
    *,
    cwd: Path,
    timeout: int,
    capture_output: bool,
    text: bool,
    shell: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        timeout=timeout,
        capture_output=capture_output,
        text=text,
        shell=shell,
        check=False,
    )


def build_graph_assets(output_dir: Path, dot_paths: list[Path]) -> list[GraphAsset]:
    assets = [
        _asset_for_dot(output_dir, path)
        for path in sorted(dot_paths, key=lambda item: _relative_path(output_dir, item).casefold())
    ]
    return assets


def render_graphs(
    output_dir: Path,
    assets: list[GraphAsset],
    mode: GraphRenderMode,
    *,
    graphviz_dot: Path | None = None,
    runner: GraphvizRunner = run_subprocess,
    timeout: int = GRAPH_RENDER_TIMEOUT_SECONDS,
) -> list[GraphRenderResult]:
    formats = _formats_for_mode(mode)
    if not formats:
        return []
    try:
        executable = _resolve_graphviz_executable(graphviz_dot)
        _probe_graphviz(executable, output_dir, runner, timeout)
    except GraphRenderException as exc:
        return [
            GraphRenderResult(
                dot_path=asset.dot_path,
                requested_format=requested_format,
                rendered_path=None,
                status=GraphRenderStatus.FAILED,
                failure_reason=exc.safe_message,
                failure_code=exc.code,
            )
            for asset in assets
            for requested_format in formats
        ]

    results: list[GraphRenderResult] = []
    for asset in assets:
        for requested_format in formats:
            result = _render_one(output_dir, asset, requested_format, executable, runner, timeout)
            if result.status == GraphRenderStatus.RENDERED and result.rendered_path is not None:
                asset.rendered_paths[requested_format.value] = result.rendered_path
            results.append(result)
    return results


def graph_render_failures(results: list[GraphRenderResult]) -> list[GraphRenderResult]:
    return [result for result in results if result.status == GraphRenderStatus.FAILED]


def rendered_count(assets: list[GraphAsset], requested_format: GraphRenderFormat) -> int:
    return sum(1 for asset in assets if requested_format.value in asset.rendered_paths)


def _asset_for_dot(output_dir: Path, path: Path) -> GraphAsset:
    relative = _relative_path(output_dir, path)
    if relative == "graphs/dependencies.dot":
        return GraphAsset(
            title="Service dependency graph",
            scope="Global",
            dot_path=relative,
        )
    if relative == "graphs/documents.dot":
        return GraphAsset(
            title="Document Type graph",
            scope="Global",
            dot_path=relative,
        )
    if relative == "graphs/scope.dot":
        return GraphAsset(
            title="Focused publication service graph",
            scope="Focused publication",
            dot_path=relative,
        )
    if relative == "graphs/scope-documents.dot":
        return GraphAsset(
            title="Focused publication document graph",
            scope="Focused publication",
            dot_path=relative,
        )
    if relative.startswith("graphs/processes/"):
        process_id = Path(relative).stem
        return GraphAsset(
            title=f"Process call graph: {process_id}",
            scope="Process",
            dot_path=relative,
        )
    return GraphAsset(title=Path(relative).stem, scope="Graph", dot_path=relative)


def _relative_path(output_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(output_dir.resolve()).as_posix()


def _formats_for_mode(mode: GraphRenderMode) -> list[GraphRenderFormat]:
    if mode == GraphRenderMode.NONE:
        return []
    if mode == GraphRenderMode.SVG:
        return [GraphRenderFormat.SVG]
    if mode == GraphRenderMode.PNG:
        return [GraphRenderFormat.PNG]
    return [GraphRenderFormat.SVG, GraphRenderFormat.PNG]


def _resolve_graphviz_executable(graphviz_dot: Path | None) -> str:
    if graphviz_dot is not None:
        return str(graphviz_dot)
    executable = shutil.which("dot")
    if executable is None:
        raise GraphRenderException(
            GraphRenderFailureCode.EXECUTABLE_NOT_FOUND,
            "Graphviz dot executable was not found on PATH.",
        )
    return executable


def _probe_graphviz(
    executable: str,
    output_dir: Path,
    runner: GraphvizRunner,
    timeout: int,
) -> None:
    try:
        completed = runner(
            [executable, "-V"],
            cwd=output_dir,
            timeout=timeout,
            capture_output=True,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise GraphRenderException(
            GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE,
            "Graphviz dot executable was unavailable.",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise GraphRenderException(
            GraphRenderFailureCode.PROBE_TIMEOUT,
            "Graphviz dot probe timed out.",
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise GraphRenderException(
            GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE,
            "Graphviz dot executable could not be started.",
            diagnostic=str(exc),
            output_dir=output_dir,
        ) from exc
    if completed.returncode != 0:
        diagnostic = _safe_diagnostic(completed.stderr or completed.stdout, output_dir)
        raise GraphRenderException(
            GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE,
            "Graphviz dot probe failed.",
            exit_code=completed.returncode,
            diagnostic=diagnostic,
        )


def _render_one(
    output_dir: Path,
    asset: GraphAsset,
    requested_format: GraphRenderFormat,
    executable: str,
    runner: GraphvizRunner,
    timeout: int,
) -> GraphRenderResult:
    dot_path = Path(asset.dot_path)
    rendered_path = dot_path.with_suffix(f".{requested_format.value}")
    final_path = output_dir / rendered_path
    temp_path: Path | None = None
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = _temporary_output_path(final_path)
    except OSError as exc:
        return _failed(
            asset,
            requested_format,
            GraphRenderFailureCode.TEMP_FILE_FAILED,
            "Graphviz render output temporary file could not be prepared.",
            diagnostic=str(exc),
            output_dir=output_dir,
        )
    args = [
        executable,
        f"-T{requested_format.value}",
        dot_path.as_posix(),
        "-o",
        temp_path.resolve().relative_to(output_dir.resolve()).as_posix(),
    ]
    try:
        completed = runner(
            args,
            cwd=output_dir,
            timeout=timeout,
            capture_output=True,
            text=True,
            shell=False,
        )
        if completed.returncode != 0:
            diagnostic = _safe_diagnostic(completed.stderr or completed.stdout, output_dir)
            return _finish_render_result(
                _failed(
                    asset,
                    requested_format,
                    GraphRenderFailureCode.RENDER_NONZERO_EXIT,
                    "Graphviz render failed.",
                    exit_code=completed.returncode,
                    diagnostic=diagnostic,
                ),
                temp_path,
                output_dir,
            )
        try:
            size = temp_path.stat().st_size
        except OSError as exc:
            return _finish_render_result(
                _failed(
                    asset,
                    requested_format,
                    GraphRenderFailureCode.OUTPUT_READ_FAILED,
                    "Graphviz output file could not be inspected.",
                    diagnostic=str(exc),
                    output_dir=output_dir,
                ),
                temp_path,
                output_dir,
            )
        if size == 0:
            return _finish_render_result(
                _failed(
                    asset,
                    requested_format,
                    GraphRenderFailureCode.OUTPUT_EMPTY,
                    "Graphviz produced an empty output file.",
                ),
                temp_path,
                output_dir,
            )
        if requested_format == GraphRenderFormat.SVG:
            validation = _validate_and_normalize_svg(temp_path, size, output_dir)
        else:
            validation = _validate_png(temp_path, size, output_dir)
        if validation is not None:
            return _finish_render_result(
                _failed(
                    asset,
                    requested_format,
                    validation.code,
                    validation.message,
                    diagnostic=validation.diagnostic,
                    output_dir=output_dir,
                ),
                temp_path,
                output_dir,
            )
        try:
            temp_path.replace(final_path)
        except OSError as exc:
            return _finish_render_result(
                _failed(
                    asset,
                    requested_format,
                    GraphRenderFailureCode.OUTPUT_REPLACE_FAILED,
                    "Graphviz output file could not be published.",
                    diagnostic=str(exc),
                    output_dir=output_dir,
                ),
                temp_path,
                output_dir,
            )
        return _finish_render_result(
            GraphRenderResult(
                dot_path=asset.dot_path,
                requested_format=requested_format,
                rendered_path=rendered_path.as_posix(),
                status=GraphRenderStatus.RENDERED,
            ),
            temp_path,
            output_dir,
        )
    except FileNotFoundError:
        return _finish_render_result(
            _failed(
                asset,
                requested_format,
                GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE,
                "Graphviz dot executable was unavailable.",
            ),
            temp_path,
            output_dir,
        )
    except subprocess.TimeoutExpired:
        return _finish_render_result(
            _failed(
                asset,
                requested_format,
                GraphRenderFailureCode.RENDER_TIMEOUT,
                "Graphviz render timed out.",
            ),
            temp_path,
            output_dir,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return _finish_render_result(
            _failed(
                asset,
                requested_format,
                GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE,
                "Graphviz render process could not be started.",
                diagnostic=str(exc),
                output_dir=output_dir,
            ),
            temp_path,
            output_dir,
        )


def _temporary_output_path(final_path: Path) -> Path:
    handle, name = tempfile.mkstemp(
        prefix=f".{final_path.name}.",
        suffix=".tmp",
        dir=final_path.parent,
    )
    os.close(handle)
    path = Path(name)
    path.unlink(missing_ok=True)
    return path


def _finish_render_result(
    result: GraphRenderResult,
    temp_path: Path,
    output_dir: Path,
) -> GraphRenderResult:
    cleanup_failure = _cleanup_temp_path(temp_path, output_dir)
    if cleanup_failure is None:
        return result
    secondary_reason = _failure_reason(
        cleanup_failure.code,
        cleanup_failure.message,
        diagnostic=(
            _safe_diagnostic(cleanup_failure.diagnostic, output_dir)
            if cleanup_failure.diagnostic
            else None
        ),
    )
    if result.status == GraphRenderStatus.RENDERED:
        return replace(
            result,
            rendered_path=None,
            status=GraphRenderStatus.FAILED,
            failure_code=cleanup_failure.code,
            failure_reason=secondary_reason,
            secondary_failure_code=cleanup_failure.code,
            secondary_failure_reason=secondary_reason,
        )
    primary_reason = result.failure_reason or "Graph render failed."
    return replace(
        result,
        failure_reason=f"{primary_reason} Secondary: {secondary_reason}",
        secondary_failure_code=cleanup_failure.code,
        secondary_failure_reason=secondary_reason,
    )


def _cleanup_temp_path(temp_path: Path, output_dir: Path) -> _ValidationFailure | None:
    try:
        temp_path.unlink(missing_ok=True)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return _ValidationFailure(
            GraphRenderFailureCode.TEMP_CLEANUP_FAILED,
            "Graphviz temporary output cleanup failed.",
            str(exc),
        )
    return None


def _failed(
    asset: GraphAsset,
    requested_format: GraphRenderFormat,
    code: GraphRenderFailureCode,
    message: str,
    *,
    exit_code: int | None = None,
    diagnostic: str | None = None,
    output_dir: Path | None = None,
) -> GraphRenderResult:
    if output_dir is not None and diagnostic is not None:
        diagnostic = _safe_diagnostic(diagnostic, output_dir)
    return GraphRenderResult(
        dot_path=asset.dot_path,
        requested_format=requested_format,
        rendered_path=None,
        status=GraphRenderStatus.FAILED,
        failure_reason=_failure_reason(code, message, exit_code, diagnostic),
        failure_code=code,
    )


@dataclass(frozen=True)
class _ValidationFailure:
    code: GraphRenderFailureCode
    message: str
    diagnostic: str | None = None


def _validate_and_normalize_svg(
    path: Path,
    size: int,
    output_dir: Path,
) -> _ValidationFailure | None:
    if size > SVG_MAX_BYTES:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_TOO_LARGE,
            "Graphviz SVG output exceeded the supported size limit.",
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_READ_FAILED,
            "Graphviz SVG output could not be read.",
            str(exc),
        )
    normalized_or_failure = _normalize_svg_bytes(raw, output_dir)
    if isinstance(normalized_or_failure, _ValidationFailure):
        return normalized_or_failure
    try:
        path.write_bytes(normalized_or_failure)
    except OSError as exc:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_WRITE_FAILED,
            "Graphviz SVG output could not be normalized.",
            str(exc),
        )
    return None


def _normalize_svg_bytes(raw: bytes, output_dir: Path) -> bytes | _ValidationFailure:
    if b"\x00" in raw:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_INVALID_SVG,
            "Graphviz SVG output was not valid XML.",
        )
    if re.search(rb"<!ENTITY\b", raw, re.IGNORECASE):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output declared XML entities.",
        )
    stripped_doctype = _strip_known_graphviz_doctype(raw)
    if isinstance(stripped_doctype, _ValidationFailure):
        return stripped_doctype
    if _has_processing_instruction(stripped_doctype):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output contained an unsupported processing instruction.",
        )
    parser = etree.XMLParser(
        resolve_entities=False,
        load_dtd=False,
        no_network=True,
        dtd_validation=False,
        recover=False,
        huge_tree=False,
        remove_comments=True,
        remove_pis=False,
    )
    try:
        root = etree.fromstring(stripped_doctype, parser)
    except etree.XMLSyntaxError as exc:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_INVALID_SVG,
            "Graphviz SVG output was not valid XML.",
            _xml_error_label(exc),
        )
    root_local = _local_name(root.tag)
    root_ns = _namespace_uri(root.tag)
    if root_local != "svg" or (root_ns not in {"", SVG_NAMESPACE}):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_INVALID_SVG,
            "Graphviz SVG output did not contain an SVG root element.",
        )
    unsafe = _unsafe_svg_tree_reason(root, output_dir)
    if unsafe is not None:
        return unsafe
    return etree.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=False,
    )


def _strip_known_graphviz_doctype(raw: bytes) -> bytes | _ValidationFailure:
    doctype_markers = list(re.finditer(rb"<!DOCTYPE\b", raw, re.IGNORECASE))
    if not doctype_markers:
        return raw
    doctype_match = GRAPHVIZ_SVG_DOCTYPE_RE.search(raw)
    if doctype_match is None or len(doctype_markers) != 1:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output used an unsupported DOCTYPE.",
        )
    return raw[: doctype_match.start()] + raw[doctype_match.end() :]


def _has_processing_instruction(raw: bytes) -> bool:
    without_declaration = XML_DECLARATION_RE.sub(b"", raw, count=1)
    return re.search(rb"<\?", without_declaration) is not None


def _unsafe_svg_tree_reason(
    root: etree._Element,
    output_dir: Path,
) -> _ValidationFailure | None:
    unsafe_elements = {
        "script",
        "foreignobject",
        "iframe",
        "object",
        "embed",
        "style",
        "animate",
        "animatemotion",
        "animatetransform",
        "set",
    }
    for element in root.iter():
        if not isinstance(element.tag, str):
            return _ValidationFailure(
                GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
                "Graphviz SVG output contained an unsupported XML node.",
            )
        local = _local_name(element.tag)
        if local in unsafe_elements:
            return _ValidationFailure(
                GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
                f"Graphviz SVG output contained an unsafe `{local}` element.",
            )
        for attr_name, attr_value in element.attrib.items():
            attr_local = _local_name(attr_name)
            if attr_local.startswith("on"):
                return _ValidationFailure(
                    GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
                    "Graphviz SVG output contained an event handler attribute.",
                )
            uri_failure = _unsafe_svg_attribute_value(attr_local, attr_value, output_dir)
            if uri_failure is not None:
                return uri_failure
        text_failure = _unsafe_svg_text(element.text, output_dir)
        if text_failure is not None:
            return text_failure
        tail_failure = _unsafe_svg_text(element.tail, output_dir)
        if tail_failure is not None:
            return tail_failure
    return None


def _unsafe_svg_attribute_value(
    attr_local: str,
    value: str,
    output_dir: Path,
) -> _ValidationFailure | None:
    stripped = CONTROL_RE.sub(" ", value).strip()
    folded = stripped.casefold()
    if "javascript:" in folded or "vbscript:" in folded or "file://" in folded:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output contained an unsafe URI.",
        )
    if _contains_absolute_local_path(stripped, output_dir):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output contained an absolute local path.",
        )
    if "url(" in folded and STYLE_FRAGMENT_URL_RE.fullmatch(stripped) is None:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output contained an unsafe URL reference.",
        )
    if attr_local in {"href", "src"}:
        if stripped and not FRAGMENT_HREF_RE.fullmatch(stripped):
            return _ValidationFailure(
                GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
                "Graphviz SVG output contained an unexpected external href.",
            )
    elif URL_SCHEME_RE.match(stripped):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output contained an unexpected URI-bearing attribute.",
        )
    return None


def _unsafe_svg_text(text: str | None, output_dir: Path) -> _ValidationFailure | None:
    if text is None:
        return None
    if _contains_absolute_local_path(text, output_dir):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
            "Graphviz SVG output contained an absolute local path.",
        )
    return None


def _contains_absolute_local_path(value: str, output_dir: Path) -> bool:
    output_label = str(output_dir.resolve())
    cleaned = value.replace(output_label, "<output>")
    return WINDOWS_ABSOLUTE_RE.search(cleaned) is not None or POSIX_ABSOLUTE_RE.search(
        cleaned
    ) is not None


def _validate_png(path: Path, size: int, output_dir: Path) -> _ValidationFailure | None:
    if size > PNG_MAX_BYTES:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_TOO_LARGE,
            "Graphviz PNG output exceeded the supported size limit.",
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_READ_FAILED,
            "Graphviz PNG output could not be read.",
            str(exc),
        )
    return _png_validation_failure(raw)


def _png_validation_failure(raw: bytes) -> _ValidationFailure | None:
    if not raw.startswith(PNG_SIGNATURE):
        return _ValidationFailure(
            GraphRenderFailureCode.OUTPUT_INVALID_PNG,
            "Graphviz PNG output had an invalid PNG signature.",
        )
    offset = len(PNG_SIGNATURE)
    chunk_index = 0
    seen_idat = False
    while offset < len(raw):
        if offset + 12 > len(raw):
            return _invalid_png("Graphviz PNG output contained a truncated chunk.")
        length = int.from_bytes(raw[offset : offset + 4], "big")
        chunk_type = raw[offset + 4 : offset + 8]
        if not all(65 <= byte <= 90 or 97 <= byte <= 122 for byte in chunk_type):
            return _invalid_png("Graphviz PNG output contained an invalid chunk type.")
        data_start = offset + 8
        data_end = data_start + length
        crc_end = data_end + 4
        if data_end < data_start or crc_end > len(raw):
            return _invalid_png("Graphviz PNG output contained a truncated chunk.")
        chunk_data = raw[data_start:data_end]
        expected_crc = int.from_bytes(raw[data_end:crc_end], "big")
        actual_crc = zlib.crc32(chunk_type)
        actual_crc = zlib.crc32(chunk_data, actual_crc) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            return _invalid_png("Graphviz PNG output contained an invalid chunk CRC.")
        if chunk_index == 0:
            if chunk_type != b"IHDR" or length != 13:
                return _invalid_png("Graphviz PNG output did not start with a valid IHDR chunk.")
            width, height = struct.unpack(">II", chunk_data[:8])
            if width == 0 or height == 0:
                return _invalid_png("Graphviz PNG output had invalid image dimensions.")
        elif chunk_type == b"IHDR":
            return _invalid_png("Graphviz PNG output contained multiple IHDR chunks.")
        if chunk_type == b"IDAT":
            seen_idat = True
        if chunk_type == b"IEND":
            if length != 0:
                return _invalid_png("Graphviz PNG output had an invalid IEND chunk.")
            if not seen_idat:
                return _invalid_png("Graphviz PNG output had no image data chunk.")
            if crc_end != len(raw):
                return _invalid_png("Graphviz PNG output had trailing data after IEND.")
            return None
        offset = crc_end
        chunk_index += 1
    return _invalid_png("Graphviz PNG output was missing an IEND chunk.")


def _invalid_png(message: str) -> _ValidationFailure:
    return _ValidationFailure(GraphRenderFailureCode.OUTPUT_INVALID_PNG, message)


def _local_name(name: str) -> str:
    try:
        return etree.QName(name).localname.casefold()
    except ValueError:
        return name.rsplit("}", 1)[-1].casefold()


def _namespace_uri(name: str) -> str:
    try:
        return etree.QName(name).namespace or ""
    except ValueError:
        return ""


def _xml_error_label(exc: etree.XMLSyntaxError) -> str:
    message = str(exc).splitlines()[0] if str(exc) else "XML syntax error"
    return message[:120]


def _failure_reason(
    code: GraphRenderFailureCode,
    message: str,
    exit_code: int | None = None,
    diagnostic: str | None = None,
) -> str:
    parts = [f"{code.value}: {message}"]
    if exit_code is not None:
        parts.append(f"Exit code: {exit_code}.")
    if diagnostic:
        parts.append(f"Diagnostic: {diagnostic}")
    return " ".join(parts)


def _safe_diagnostic(text: str, output_dir: Path) -> str:
    cleaned = CONTROL_RE.sub(" ", text)
    cleaned = cleaned.replace(str(output_dir.resolve()), "<output>")
    cleaned = WINDOWS_ABSOLUTE_RE.sub("<path>", cleaned)
    cleaned = POSIX_ABSOLUTE_RE.sub("<path>", cleaned)
    cleaned = SECRET_KEY_VALUE_RE.sub(_redact_secret_key_value, cleaned)
    cleaned = JDBC_RE.sub("<redacted:connection-string>", cleaned)
    cleaned = AUTHORIZATION_RE.sub(
        lambda match: f"{match.group(1)}{REDACTED_DIAGNOSTIC_VALUE}",
        cleaned,
    )
    cleaned = BEARER_RE.sub(
        lambda match: f"{match.group(1)}{REDACTED_DIAGNOSTIC_VALUE}",
        cleaned,
    )
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > DIAGNOSTIC_LIMIT:
        return cleaned[:DIAGNOSTIC_LIMIT] + "..."
    return cleaned


def _redact_secret_key_value(match: re.Match[str]) -> str:
    key = match.group("key")
    if not _is_secret_diagnostic_key(key):
        return match.group(0)
    return (
        f"{match.group('key_quote')}{key}{match.group('key_quote')}"
        f"{match.group('separator')}{REDACTED_DIAGNOSTIC_VALUE}"
    )


def _is_secret_diagnostic_key(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    parts = [part for part in normalized.split("_") if part]
    compact = "".join(parts)
    if compact in SECRET_KEY_COMPACT_NAMES:
        return True
    if parts and parts[-1] in SECRET_KEY_SUFFIX_PARTS:
        return True
    return len(parts) >= 2 and parts[-1] == "key" and parts[-2] in {"api", "private"}


class GraphRenderException(Exception):
    def __init__(
        self,
        code: GraphRenderFailureCode,
        safe_message: str,
        *,
        exit_code: int | None = None,
        diagnostic: str | None = None,
        output_dir: Path | None = None,
    ) -> None:
        if output_dir is not None and diagnostic is not None:
            diagnostic = _safe_diagnostic(diagnostic, output_dir)
        message = _failure_reason(code, safe_message, exit_code, diagnostic)
        super().__init__(message)
        self.code = code
        self.safe_message = message
