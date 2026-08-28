from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from wm_doc.business_result_schema import BusinessEnrichmentErrorCode
from wm_doc.ollama_provider import (
    OllamaProviderError,
    ProviderGenerationRequest,
)
from wm_doc.openai_compatible_provider import (
    OpenAICompatibleProvider,
    resolve_api_key,
)

TOKEN = "secret-token"


class _Handler(BaseHTTPRequestHandler):
    seen: dict[str, Any] = {}

    def log_message(self, *args: Any) -> None:  # keep test output clean
        return

    def _send(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        _Handler.seen["get_path"] = self.path
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._send(401, {"error": "unauthorized"})
            return
        self._send(200, {"data": [{"id": "test-model"}]})

    def do_POST(self) -> None:
        _Handler.seen["post_path"] = self.path
        _Handler.seen["authorization"] = self.headers.get("Authorization")
        length = int(self.headers.get("Content-Length", 0))
        _Handler.seen["body"] = json.loads(self.rfile.read(length))
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._send(401, {"error": "unauthorized"})
            return
        self._send(
            200,
            {
                "choices": [{"message": {"role": "assistant", "content": '{"claims":[]}'}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            },
        )


@pytest.fixture()
def endpoint() -> Any:
    _Handler.seen = {}
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/ollama/v1"
    server.shutdown()


def test_bearer_token_and_openai_shape(endpoint: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """An Ollama server behind an authenticating proxy must be reachable.

    The native client cannot do this: it rejects URL paths and sends no credentials.
    """
    monkeypatch.setenv("OLLAMA_API_KEY", TOKEN)
    provider = OpenAICompatibleProvider(endpoint, api_key=resolve_api_key("OLLAMA_API_KEY"))

    assert provider.base_url.endswith("/ollama/v1")
    assert provider.check("test-model").model_found

    result = provider.generate(
        ProviderGenerationRequest(
            model="test-model",
            messages=[{"role": "user", "content": "hi"}],
            schema={"type": "object"},
            timeout_seconds=10,
        )
    )

    assert _Handler.seen["get_path"] == "/ollama/v1/models"
    assert _Handler.seen["post_path"] == "/ollama/v1/chat/completions"
    assert _Handler.seen["authorization"] == f"Bearer {TOKEN}"
    assert _Handler.seen["body"]["response_format"]["type"] == "json_schema"
    assert result.content == '{"claims":[]}'
    assert result.metrics["prompt_tokens"] == 11


def test_rejected_token_does_not_leak(endpoint: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_API_KEY", "wrong-token")
    provider = OpenAICompatibleProvider(endpoint, api_key=resolve_api_key("OLLAMA_API_KEY"))

    with pytest.raises(OllamaProviderError) as caught:
        provider.check("test-model")

    assert caught.value.code is BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE
    assert "wrong-token" not in caught.value.safe_message
    assert "API key environment variable" in caught.value.safe_message


def test_token_to_remote_host_requires_https() -> None:
    """A bearer token over plain HTTP to a remote host would be on the wire in clear."""
    with pytest.raises(OllamaProviderError):
        OpenAICompatibleProvider(
            "http://10.0.0.50/ollama/v1", api_key="t", allow_remote_provider=True
        )

    # https is fine, and so is loopback (an SSH tunnel never leaves the machine).
    assert OpenAICompatibleProvider(
        "https://server/ollama/v1", api_key="t", allow_remote_provider=True
    ).base_url == "https://server/ollama/v1"
    assert OpenAICompatibleProvider("http://localhost:11434/v1", api_key="t").base_url


def test_missing_env_var_yields_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OLLAMA_API_KEY", raising=False)
    assert resolve_api_key("OLLAMA_API_KEY") is None
    assert resolve_api_key(None) is None
