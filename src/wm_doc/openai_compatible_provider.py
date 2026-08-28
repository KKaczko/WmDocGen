"""Access an Ollama server through its OpenAI-compatible endpoint.

Ollama has no authentication of its own, so a shared server is normally fronted by a
reverse proxy that terminates TLS and checks a bearer token, exposing the
OpenAI-compatible surface at a path such as ``https://server/ollama/v1``. The native
`/api/chat` client cannot reach that: it rejects URL paths and sends no credentials.

This provider speaks the OpenAI chat-completions shape and carries an
``Authorization: Bearer`` header. The token is read from an environment variable named
in configuration -- never from a CLI flag, so it stays out of shell history and process
listings -- and is never written to provenance, the cache key, or any diagnostic.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from wm_doc.business_result_schema import BusinessEnrichmentErrorCode
from wm_doc.ollama_provider import (
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    MAX_PROVIDER_RESPONSE_BYTES,
    NUM_PREDICT,
    TEMPERATURE,
    OllamaProviderError,
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
    _NoRedirectHandler,
    _read_error_body,
    _safe_diagnostic,
    _safe_label,
    validate_ollama_url,
)

PROVIDER_KIND = "openai-compatible"
DEFAULT_API_KEY_ENV = "OLLAMA_API_KEY"


def resolve_api_key(api_key_env: str | None) -> str | None:
    """Read the bearer token from the named environment variable."""
    if not api_key_env:
        return None
    value = os.environ.get(api_key_env, "").strip()
    return value or None


class OpenAICompatibleProvider:
    """Satisfies the BusinessEnrichmentProvider protocol over an OpenAI-style API."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        allow_remote_provider: bool = False,
        connect_timeout_seconds: int = HTTP_CONNECT_TIMEOUT_SECONDS,
        timeout_seconds: int = HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = validate_ollama_url(
            base_url,
            allow_remote_provider=allow_remote_provider,
            allow_path=True,
        )
        parsed = urllib.parse.urlparse(self.base_url)
        loopback = (parsed.hostname or "").casefold() in {"localhost", "127.0.0.1", "::1"}
        if api_key and parsed.scheme != "https" and not loopback:
            # A token to loopback (an SSH tunnel, say) never leaves the machine; one to
            # a remote host over plain HTTP is on the wire in clear.
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
                "Sending an API key to a remote host requires https. Use an https URL "
                "or tunnel the endpoint to loopback.",
            )
        self._api_key = api_key
        self.connect_timeout_seconds = connect_timeout_seconds
        self.timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )

    def check(self, model: str, *, structured_probe: bool = False) -> ProviderCheckResult:
        models = self._request("/models", None, timeout=self.connect_timeout_seconds)
        available = _model_ids(models)
        if available and model not in available:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.MODEL_NOT_FOUND,
                f"Requested model `{_safe_label(model)}` was not offered by the endpoint.",
            )
        return ProviderCheckResult(
            provider_kind=PROVIDER_KIND,
            model=model,
            model_found=True,
            model_digest=None,
            ollama_version=None,
            structured_output_ok=True,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        payload: dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": TEMPERATURE,
            "max_tokens": NUM_PREDICT,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "BusinessDraft",
                    "strict": True,
                    "schema": request.schema,
                },
            },
        }
        started = time.perf_counter()
        data = self._request(
            "/chat/completions", payload, timeout=request.timeout_seconds
        )
        content = _message_content(data)
        if content is None:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.RESPONSE_INVALID,
                "Endpoint response did not contain choices[].message.content.",
            )
        usage = data.get("usage") if isinstance(data, dict) else None
        metrics: dict[str, Any] = {
            "_wm_doc_elapsed_seconds": round(time.perf_counter() - started, 3)
        }
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if isinstance(usage.get(key), int):
                    metrics[key] = usage[key]
        return ProviderGenerationResult(
            content=content,
            provider_kind=PROVIDER_KIND,
            model=request.model,
            ollama_version=None,
            model_digest=None,
            metrics=metrics,
            attempts=1,
        )

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None,
        *,
        timeout: int,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            self.base_url.rstrip("/") + path,
            method="POST" if payload is not None else "GET",
            data=(
                json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                if payload is not None
                else None
            ),
            headers=headers,
        )
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except TimeoutError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.TIMEOUT,
                "Provider request timed out.",
            ) from exc
        except urllib.error.HTTPError as exc:
            code = (
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE
                if exc.code in {401, 403, 404, 429, 500, 502, 503, 504}
                else BusinessEnrichmentErrorCode.PROVIDER_FAILED
            )
            hint = " Check the API key environment variable." if exc.code in {401, 403} else ""
            raise OllamaProviderError(
                code,
                f"Provider HTTP request failed with status {exc.code}.{hint} "
                f"Diagnostic: {_safe_diagnostic(_read_error_body(exc))}",
            ) from exc
        except urllib.error.URLError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
                f"Provider was unavailable. Diagnostic: {_safe_diagnostic(str(exc.reason))}",
            ) from exc
        except OSError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
                f"Provider request failed. Diagnostic: {_safe_diagnostic(str(exc))}",
            ) from exc
        if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_FAILED,
                "Provider response exceeded the supported byte limit.",
            )
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.RESPONSE_INVALID,
                "Provider returned a non-JSON response.",
            ) from exc
        if not isinstance(decoded, dict):
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.RESPONSE_INVALID,
                "Provider returned an unexpected JSON payload.",
            )
        return decoded


def _model_ids(payload: dict[str, Any]) -> set[str]:
    entries = payload.get("data")
    if not isinstance(entries, list):
        return set()
    return {
        str(entry["id"])
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("id"), str)
    }


def _message_content(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return content.strip()
