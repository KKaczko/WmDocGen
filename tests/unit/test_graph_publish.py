from __future__ import annotations

import os
import shutil
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

import wm_doc.graph_publish as graph_publish
from wm_doc.graph_publish import (
    GraphRenderFailureCode,
    GraphRenderMode,
    GraphRenderStatus,
    build_graph_assets,
    render_graphs,
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _minimal_png(width: int = 1, height: int = 1) -> bytes:
    scanline = b"\x00" + (b"\x00\x00\x00\xff" * max(width, 1))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(scanline))
        + _png_chunk(b"IEND", b"")
    )


def _png_without_idat() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IEND", b"")


def _corrupt_png_crc(png_bytes: bytes) -> bytes:
    return png_bytes[:-1] + bytes([png_bytes[-1] ^ 0xFF])


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(chunk_type)
    crc = zlib.crc32(data, crc) & 0xFFFFFFFF
    return len(data).to_bytes(4, "big") + chunk_type + data + crc.to_bytes(4, "big")


def test_graphviz_render_success_uses_argument_lists_and_records_assets(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    assets = build_graph_assets(tmp_path, [dot_path])
    runner = FakeGraphvizRunner()

    results = render_graphs(
        tmp_path,
        assets,
        GraphRenderMode.BOTH,
        graphviz_dot=Path("dot"),
        runner=runner,
    )

    assert [result.status for result in results] == [
        GraphRenderStatus.RENDERED,
        GraphRenderStatus.RENDERED,
    ]
    assert (tmp_path / "graphs" / "dependencies.svg").read_text(encoding="utf-8").startswith(
        "<?xml"
    )
    assert (tmp_path / "graphs" / "dependencies.png").read_bytes().startswith(b"\x89PNG")
    assert assets[0].rendered_paths == {
        "svg": "graphs/dependencies.svg",
        "png": "graphs/dependencies.png",
    }
    assert all(call["shell"] is False for call in runner.calls)
    assert runner.calls[1]["args"][:3] == ["dot", "-Tsvg", "graphs/dependencies.dot"]
    assert runner.calls[2]["args"][:3] == ["dot", "-Tpng", "graphs/dependencies.dot"]
    assert not list(tmp_path.rglob("*.tmp"))


def test_graphviz_missing_executable_fails_all_requested_formats(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    assets = build_graph_assets(tmp_path, [dot_path])
    runner = FakeGraphvizRunner(probe_exception=FileNotFoundError())

    results = render_graphs(
        tmp_path,
        assets,
        GraphRenderMode.BOTH,
        graphviz_dot=Path("missing-dot"),
        runner=runner,
    )

    assert [result.status for result in results] == [
        GraphRenderStatus.FAILED,
        GraphRenderStatus.FAILED,
    ]
    assert all(
        result.failure_code == GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE
        for result in results
    )
    assert not (tmp_path / "graphs" / "dependencies.svg").exists()
    assert not (tmp_path / "graphs" / "dependencies.png").exists()


def test_graphviz_probe_failure_sanitizes_and_truncates_diagnostics(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    assets = build_graph_assets(tmp_path, [dot_path])
    runner = FakeGraphvizRunner(
        probe_returncode=1,
        probe_stderr=("D:\\Dev\\secondWM\\secret\\dot.exe " + "x" * 400),
    )

    result = render_graphs(
        tmp_path,
        assets,
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=runner,
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_reason is not None
    assert "D:\\Dev" not in result.failure_reason
    assert "<path>" in result.failure_reason
    assert result.failure_reason.endswith("...")


def test_graphviz_render_failures_clean_partial_outputs(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    assets = build_graph_assets(tmp_path, [dot_path])
    runner = FakeGraphvizRunner(render_returncode=1, write_before_failure=True)

    result = render_graphs(
        tmp_path,
        assets,
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=runner,
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert not (tmp_path / "graphs" / "dependencies.svg").exists()
    assert not list(tmp_path.rglob("*.tmp"))


def test_graphviz_timeout_empty_output_and_unsafe_svg_are_failures(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")

    timeout_result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(render_exception=subprocess.TimeoutExpired("dot", 30)),
    )[0]
    assert timeout_result.status == GraphRenderStatus.FAILED
    assert timeout_result.failure_code == GraphRenderFailureCode.RENDER_TIMEOUT
    assert "timed out" in (timeout_result.failure_reason or "")

    empty_result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.PNG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(empty_output=True),
    )[0]
    assert empty_result.status == GraphRenderStatus.FAILED
    assert empty_result.failure_code == GraphRenderFailureCode.OUTPUT_EMPTY
    assert "empty" in (empty_result.failure_reason or "")

    unsafe_result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(svg_text='<svg><script>alert("x")</script></svg>'),
    )[0]
    assert unsafe_result.status == GraphRenderStatus.FAILED
    assert unsafe_result.failure_code == GraphRenderFailureCode.OUTPUT_UNSAFE_SVG


@pytest.mark.parametrize(
    "svg_text",
    [
        "not svg",
        "<html />",
        "<svg /><svg />",
        '<svg><script>alert("x")</script></svg>',
        "<svg><foreignObject /></svg>",
        "<svg><iframe /></svg>",
        "<svg><object /></svg>",
        "<svg><embed /></svg>",
        "<svg><style>a{background:url(http://example.invalid/x)}</style></svg>",
        '<svg onload="alert(1)" />',
        '<svg><a href="javascript:alert(1)" /></svg>',
        '<svg><a href="https://example.invalid/x" /></svg>',
        '<svg><image href="file:///etc/passwd" /></svg>',
        '<svg><path d="url(C:/Users/admin/secret)" /></svg>',
        '<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY x "secret">]><svg />',
        '<?process secret?><svg />',
    ],
)
def test_graphviz_svg_validation_rejects_malformed_or_unsafe_output(
    tmp_path, svg_text
) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(svg_text=svg_text),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code in {
        GraphRenderFailureCode.OUTPUT_INVALID_SVG,
        GraphRenderFailureCode.OUTPUT_UNSAFE_SVG,
    }
    assert not (tmp_path / "graphs" / "dependencies.svg").exists()


def test_graphviz_svg_validation_accepts_graphviz_doctype_and_normalizes_output(
    tmp_path,
) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    svg_text = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN"
 "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">
<!-- Generated by graphviz -->
<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="10pt" height="10pt">
  <g id="graph0"><a xlink:href="#safe"><text>label</text></a></g>
</svg>
"""

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(svg_text=svg_text),
    )[0]

    assert result.status == GraphRenderStatus.RENDERED
    rendered = (tmp_path / "graphs" / "dependencies.svg").read_text(encoding="utf-8")
    assert "<!DOCTYPE" not in rendered
    assert "Generated by graphviz" not in rendered
    assert rendered.startswith("<?xml")


def test_graphviz_svg_validation_enforces_size_limit(tmp_path, monkeypatch) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    monkeypatch.setattr(graph_publish, "SVG_MAX_BYTES", 8)

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(svg_text="<svg><g /></svg>"),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.OUTPUT_TOO_LARGE


@pytest.mark.parametrize(
    "png_bytes",
    [
        b"not png",
        b"\x89PNG\r\n\x1a\n",
        _minimal_png(width=0, height=1),
        _png_without_idat(),
        _minimal_png()[:-1],
        _minimal_png() + b"trailing",
        _corrupt_png_crc(_minimal_png()),
    ],
)
def test_graphviz_png_validation_rejects_malformed_output(tmp_path, png_bytes) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.PNG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(png_bytes=png_bytes),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.OUTPUT_INVALID_PNG
    assert not (tmp_path / "graphs" / "dependencies.png").exists()


def test_graphviz_png_validation_enforces_size_limit(tmp_path, monkeypatch) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    monkeypatch.setattr(graph_publish, "PNG_MAX_BYTES", 16)

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.PNG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(png_bytes=_minimal_png()),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.OUTPUT_TOO_LARGE


@pytest.mark.parametrize(
    "exception",
    [
        PermissionError("access denied"),
        OSError("not runnable"),
        subprocess.SubprocessError("subprocess failed"),
    ],
)
def test_graphviz_probe_os_errors_are_safe_failures(tmp_path, exception) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(probe_exception=exception),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE


def test_graphviz_render_os_errors_are_safe_failures(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(render_exception=PermissionError("access denied")),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.EXECUTABLE_NOT_RUNNABLE
    assert not list(tmp_path.rglob("*.tmp"))


def test_graphviz_publish_replace_failure_is_reported_without_traceback(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    (tmp_path / "graphs" / "dependencies.svg").mkdir()

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.OUTPUT_REPLACE_FAILED
    assert not list(tmp_path.rglob("*.tmp"))


def test_graphviz_diagnostics_redact_secret_like_values(tmp_path) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    variants = [
        ("password=hunter2", "hunter2"),
        ("password: colon-secret", "colon-secret"),
        ("password = spaced-secret", "spaced-secret"),
        ('"password":"double-quoted-secret"', "double-quoted-secret"),
        ("'password':'single-quoted-secret'", "single-quoted-secret"),
        ("token=abc123", "abc123"),
        ("passwd=AnotherSecret", "AnotherSecret"),
        ("PASSWD=UpperSecret", "UpperSecret"),
        ("access_token=private-token", "private-token"),
        ("ACCESS_TOKEN=upper-private-token", "upper-private-token"),
        ("access-token=hyphen-private-token", "hyphen-private-token"),
        ("oauth_access_token=oauth-secret", "oauth-secret"),
        ("service_access_token=service-secret", "service-secret"),
        ("refresh_token=refresh-secret", "refresh-secret"),
        ("refresh-token=refresh-hyphen-secret", "refresh-hyphen-secret"),
        ("id_token=id-secret", "id-secret"),
        ("id-token=id-hyphen-secret", "id-hyphen-secret"),
        ("api_key=api-secret", "api-secret"),
        ("api-key=api-hyphen-secret", "api-hyphen-secret"),
        ("apikey=api-compact-secret", "api-compact-secret"),
        ("private_api_key=private-api-secret", "private-api-secret"),
        ("client_secret=clientSecretValue", "clientSecretValue"),
        ("client-secret=clientHyphenValue", "clientHyphenValue"),
        ("database_password=db-secret", "db-secret"),
        ("user_passwd=user-secret", "user-secret"),
        ("pwd=tiny-secret", "tiny-secret"),
        ("passphrase=phrase-secret", "phrase-secret"),
        ("'api-key': 'quoted-secret'", "quoted-secret"),
        ("private_key = multi word secret", "multi word secret"),
        ("authorization=bearer auth-equals-secret", "auth-equals-secret"),
        ("Authorization: Bearer should-not-leak", "should-not-leak"),
    ]

    for diagnostic, secret in variants:
        runner = FakeGraphvizRunner(
            render_returncode=1,
            render_stderr=(
                f"failed {diagnostic} tokenizer=lexer passwordPolicy=minimum "
                "secretary=assistant node_id=ordinary "
                "jdbc:wm://host.example:5555/path D:\\Dev\\secondWM\\secret.txt"
            ),
        )

        result = render_graphs(
            tmp_path,
            build_graph_assets(tmp_path, [dot_path]),
            GraphRenderMode.SVG,
            graphviz_dot=Path("dot"),
            runner=runner,
        )[0]

        assert result.status == GraphRenderStatus.FAILED
        assert result.failure_code == GraphRenderFailureCode.RENDER_NONZERO_EXIT
        reason = result.failure_reason or ""
        assert secret not in reason
        assert "jdbc:wm://host.example:5555" not in reason
        assert "D:\\Dev" not in reason
        assert "tokenizer=lexer" in reason
        assert "passwordPolicy=minimum" in reason
        assert "secretary=assistant" in reason
        assert "node_id=ordinary" in reason
        assert "[REDACTED]" in reason
        assert "<redacted:connection-string>" in reason


def test_graphviz_temp_cleanup_failure_is_reported_as_secondary(
    tmp_path, monkeypatch
) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    temp_path = tmp_path / "graphs" / ".manual.svg.tmp"

    def fake_temporary_output_path(_final_path: Path) -> Path:
        return temp_path

    original_unlink = Path.unlink

    def unlink_with_cleanup_failure(self: Path, *args: object, **kwargs: object) -> None:
        if self == temp_path:
            raise PermissionError("cleanup denied password=cleanup-secret")
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(graph_publish, "_temporary_output_path", fake_temporary_output_path)
    monkeypatch.setattr(Path, "unlink", unlink_with_cleanup_failure)

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(svg_text="not svg"),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.OUTPUT_INVALID_SVG
    assert result.secondary_failure_code == GraphRenderFailureCode.TEMP_CLEANUP_FAILED
    assert result.secondary_failure_reason is not None
    assert "TEMP_CLEANUP_FAILED" in result.failure_reason
    assert "cleanup-secret" not in result.failure_reason
    assert temp_path.exists()


def test_graphviz_missing_temp_cleanup_is_not_reported_as_secondary(
    tmp_path, monkeypatch
) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    temp_path = tmp_path / "graphs" / ".manual.svg.tmp"

    def fake_temporary_output_path(_final_path: Path) -> Path:
        return temp_path

    original_unlink = Path.unlink

    def unlink_as_missing(self: Path, *args: object, **kwargs: object) -> None:
        if self == temp_path:
            raise FileNotFoundError(str(self))
        original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(graph_publish, "_temporary_output_path", fake_temporary_output_path)
    monkeypatch.setattr(Path, "unlink", unlink_as_missing)

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        GraphRenderMode.SVG,
        graphviz_dot=Path("dot"),
        runner=FakeGraphvizRunner(svg_text="not svg"),
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == GraphRenderFailureCode.OUTPUT_INVALID_SVG
    assert result.secondary_failure_code is None
    assert result.secondary_failure_reason is None


@pytest.mark.parametrize(
    ("case", "mode", "expected_code"),
    [
        ("timeout", GraphRenderMode.SVG, GraphRenderFailureCode.RENDER_TIMEOUT),
        ("invalid_png", GraphRenderMode.PNG, GraphRenderFailureCode.OUTPUT_INVALID_PNG),
        ("replace_failure", GraphRenderMode.SVG, GraphRenderFailureCode.OUTPUT_REPLACE_FAILED),
    ],
)
def test_graphviz_temp_cleanup_failure_preserves_primary_failures(
    tmp_path,
    monkeypatch,
    case: str,
    mode: GraphRenderMode,
    expected_code: GraphRenderFailureCode,
) -> None:
    dot_path = _write_dot(tmp_path, "graphs/dependencies.dot")
    suffix = ".png" if mode == GraphRenderMode.PNG else ".svg"
    temp_path = tmp_path / "graphs" / f".manual{suffix}.tmp"
    final_path = tmp_path / "graphs" / f"dependencies{suffix}"

    def fake_temporary_output_path(_final_path: Path) -> Path:
        return temp_path

    original_unlink = Path.unlink

    def unlink_with_cleanup_failure(self: Path, *args: object, **kwargs: object) -> None:
        if self == temp_path:
            raise OSError("cleanup failed access_token=cleanup-secret")
        original_unlink(self, *args, **kwargs)

    if case == "timeout":
        runner = FakeGraphvizRunner(
            render_exception=subprocess.TimeoutExpired(["dot"], timeout=30),
            write_before_failure=True,
        )
    elif case == "invalid_png":
        runner = FakeGraphvizRunner(png_bytes=b"not a png")
    else:
        final_path.mkdir()
        runner = FakeGraphvizRunner()

    monkeypatch.setattr(graph_publish, "_temporary_output_path", fake_temporary_output_path)
    monkeypatch.setattr(Path, "unlink", unlink_with_cleanup_failure)

    result = render_graphs(
        tmp_path,
        build_graph_assets(tmp_path, [dot_path]),
        mode,
        graphviz_dot=Path("dot"),
        runner=runner,
    )[0]

    assert result.status == GraphRenderStatus.FAILED
    assert result.failure_code == expected_code
    assert result.secondary_failure_code == GraphRenderFailureCode.TEMP_CLEANUP_FAILED
    assert "cleanup-secret" not in (result.failure_reason or "")
    assert "TEMP_CLEANUP_FAILED" in (result.failure_reason or "")


def test_real_graphviz_smoke_when_available(tmp_path) -> None:
    graphviz_dot = os.environ.get("WM_DOC_TEST_GRAPHVIZ_DOT") or shutil.which("dot")
    if graphviz_dot is None:
        pytest.skip("Graphviz dot is not installed.")
    dot_path = _write_dot(tmp_path, "graphs/smoke.dot")
    assets = build_graph_assets(tmp_path, [dot_path])

    results = render_graphs(
        tmp_path,
        assets,
        GraphRenderMode.SVG,
        graphviz_dot=Path(graphviz_dot),
    )

    assert [result.status for result in results] == [GraphRenderStatus.RENDERED]
    assert (tmp_path / "graphs" / "smoke.svg").exists()
    assert "<!DOCTYPE" not in (tmp_path / "graphs" / "smoke.svg").read_text(
        encoding="utf-8"
    )


def _write_dot(root: Path, relative_path: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("digraph g {\n  a -> b;\n}\n", encoding="utf-8")
    return path


class FakeGraphvizRunner:
    def __init__(
        self,
        *,
        probe_exception: Exception | None = None,
        render_exception: Exception | None = None,
        probe_returncode: int = 0,
        render_returncode: int = 0,
        probe_stderr: str = "dot - graphviz",
        render_stderr: str = "render failed",
        svg_text: str = "<svg><g /></svg>",
        png_bytes: bytes | None = None,
        empty_output: bool = False,
        write_before_failure: bool = False,
    ) -> None:
        self.probe_exception = probe_exception
        self.render_exception = render_exception
        self.probe_returncode = probe_returncode
        self.render_returncode = render_returncode
        self.probe_stderr = probe_stderr
        self.render_stderr = render_stderr
        self.svg_text = svg_text
        self.png_bytes = png_bytes if png_bytes is not None else _minimal_png()
        self.empty_output = empty_output
        self.write_before_failure = write_before_failure
        self.calls: list[dict[str, object]] = []

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
        self.calls.append(
            {
                "args": args,
                "cwd": cwd,
                "timeout": timeout,
                "capture_output": capture_output,
                "text": text,
                "shell": shell,
            }
        )
        if args[1] == "-V":
            if self.probe_exception is not None:
                raise self.probe_exception
            return subprocess.CompletedProcess(
                args,
                self.probe_returncode,
                stdout="",
                stderr=self.probe_stderr,
            )
        if self.render_exception is not None:
            raise self.render_exception
        output_path = cwd / args[args.index("-o") + 1]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if self.write_before_failure or self.render_returncode == 0:
            if not self.empty_output:
                if args[1] == "-Tsvg":
                    output_path.write_text(self.svg_text, encoding="utf-8")
                else:
                    output_path.write_bytes(self.png_bytes)
            else:
                output_path.write_bytes(b"")
        return subprocess.CompletedProcess(
            args,
            self.render_returncode,
            stdout="",
            stderr=self.render_stderr,
        )
