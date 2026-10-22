"""M12 phase 5: shared Ollama server behind a proxy, provider probe, parallel describe."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from test_describe import FakeProvider, grounded

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.describer import DescribeOptions, DescribeOutcome, describe_services
from wm_doc.ollama_provider import (
    OllamaBusinessEnrichmentProvider,
    OllamaProviderError,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.provider_probe import probe_provider

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
TOKEN = "proxy-token"


class _Proxy(BaseHTTPRequestHandler):
    """A proxy at /ollama that checks a bearer token; `native` decides if /api is forwarded."""

    native = True
    seen: list[dict[str, Any]] = []

    def log_message(self, *args: Any) -> None:
        return

    def _send(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorised(self) -> bool:
        if self.headers.get("Authorization") == f"Bearer {TOKEN}":
            return True
        self._send(401, {"error": "unauthorized"})
        return False

    def do_GET(self) -> None:
        _Proxy.seen.append({"method": "GET", "path": self.path})
        if not self._authorised():
            return
        if self.path == "/ollama/api/version" and _Proxy.native:
            self._send(200, {"version": "0.40.8"})
        elif self.path == "/ollama/api/tags" and _Proxy.native:
            self._send(200, {"models": [{"name": "m", "model": "m", "digest": "sha256:x"}]})
        elif self.path == "/ollama/v1/models":
            self._send(200, {"data": [{"id": "m"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        _Proxy.seen.append({"method": "POST", "path": self.path, "body": body})
        if not self._authorised():
            return
        if self.path == "/ollama/api/chat" and _Proxy.native:
            self._send(
                200,
                {"message": {"role": "assistant", "content": "{}"}, "prompt_eval_count": 5},
            )
        elif self.path == "/ollama/api/show" and _Proxy.native:
            self._send(200, {"model_info": {"qwen35.context_length": 262144}})
        else:
            self._send(404, {"error": "not found"})


@pytest.fixture()
def proxy() -> Iterator[str]:
    _Proxy.seen = []
    _Proxy.native = True
    server = HTTPServer(("127.0.0.1", 0), _Proxy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/ollama"
    server.shutdown()


def test_native_client_reaches_a_proxied_server_with_a_token(proxy: str) -> None:
    provider = OllamaBusinessEnrichmentProvider(proxy, api_key=TOKEN)

    check = provider.check("m")
    result = provider.generate(
        ProviderGenerationRequest(
            model="m", messages=[], schema={}, timeout_seconds=5, num_ctx=16384, num_predict=99
        )
    )

    assert check.model_found
    assert result.metrics["prompt_eval_count"] == 5
    chat = next(item for item in _Proxy.seen if item["path"] == "/ollama/api/chat")
    assert chat["body"]["options"]["num_ctx"] == 16384
    assert chat["body"]["options"]["num_predict"] == 99


def test_native_client_refuses_token_over_plain_http_to_a_remote_host() -> None:
    with pytest.raises(OllamaProviderError, match="requires https"):
        OllamaBusinessEnrichmentProvider(
            "http://ollama.example.com/ollama", allow_remote_provider=True, api_key=TOKEN
        )


def test_default_loopback_client_still_requires_the_root_url() -> None:
    with pytest.raises(OllamaProviderError, match="provider root"):
        OllamaBusinessEnrichmentProvider("http://localhost:11434/ollama")


def test_probe_recommends_native_api_when_forwarded(proxy: str) -> None:
    report = probe_provider(proxy, api_key=TOKEN, model="m", allow_remote_provider=False)

    assert report.native_ok and report.openai_ok
    assert report.context_length == 262144
    assert any("Use the native API" in line for line in report.lines)
    assert all(TOKEN not in line for line in report.lines)


def test_probe_recommends_v1_with_num_ctx_when_only_v1_is_forwarded(proxy: str) -> None:
    _Proxy.native = False

    report = probe_provider(proxy, api_key=TOKEN, model="m", allow_remote_provider=False)

    assert not report.native_ok and report.openai_ok
    assert any("--provider openai-compatible" in line for line in report.lines)
    assert any("OLLAMA_CONTEXT_LENGTH" in line for line in report.lines)


def test_probe_without_token_reports_failure(proxy: str) -> None:
    report = probe_provider(proxy, api_key=None, model=None, allow_remote_provider=False)

    assert not report.native_ok and not report.openai_ok
    assert report.lines[-1].startswith("Neither API answered")


def _options(docs: Path, **overrides: Any) -> DescribeOptions:
    values: dict[str, Any] = {
        "model": "fake-model",
        "scan_root": SAMPLES,
        "config": load_config(None),
        "docs_dir": docs,
        "no_cache": True,
    }
    values.update(overrides)
    return DescribeOptions(**values)


def test_parallel_describe_writes_the_same_files_as_sequential(tmp_path: Path) -> None:
    analysis = analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)
    every = [s.identity.full_name for p in analysis.packages for s in p.services]

    sequential, _ = describe_services(
        analysis, every, FakeProvider(), _options(tmp_path / "sequential")
    )
    parallel, _ = describe_services(
        analysis, every, FakeProvider(), _options(tmp_path / "parallel", parallel=4)
    )

    assert [r.service for r in parallel] == [r.service for r in sequential]
    assert all(r.outcome is DescribeOutcome.GENERATED for r in parallel)
    for result in sequential:
        assert result.path is not None
        twin = tmp_path / "parallel" / result.path.relative_to(tmp_path / "sequential")
        assert twin.read_bytes() == result.path.read_bytes(), result.service


class _OversizedPromptProvider(FakeProvider):
    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        result = super().generate(request)
        # The /v1 API reports usage.prompt_tokens instead of prompt_eval_count.
        return ProviderGenerationResult(
            content=result.content,
            provider_kind="openai-compatible",
            model=result.model,
            ollama_version=None,
            model_digest=None,
            metrics={"prompt_tokens": 99_999},
        )


def test_truncation_guard_reads_openai_usage(tmp_path: Path) -> None:
    analysis = analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)

    results, stats = describe_services(
        analysis,
        ["pgp.services.common:readConfig"],
        _OversizedPromptProvider(grounded),
        _options(tmp_path / "docs"),
    )

    assert results[0].outcome is DescribeOutcome.FAILED
    assert "cut off" in (results[0].note or "")
    assert stats.prompt_tokens == [99_999]
