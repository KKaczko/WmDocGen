from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

HTTP_TIMEOUT_SECONDS = 600
HTTP_CONNECT_TIMEOUT_SECONDS = 5
MAX_PROVIDER_RESPONSE_BYTES = 4 * 1024 * 1024
TEMPERATURE = 0
NUM_PREDICT = 2048
# Default when a request does not set its own context size. Ollama otherwise allocates the
# model's full advertised context (131072+ tokens), which can push a small model into
# paging on memory-constrained machines. `describe` sets num_ctx per request.
NUM_CTX = 8192


class ProviderErrorCode(StrEnum):
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    PROVIDER_FAILED = "PROVIDER_FAILED"
    RESPONSE_INVALID = "RESPONSE_INVALID"
    TIMEOUT = "TIMEOUT"

CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SECRET_KEY_VALUE_RE = re.compile(
    r"(?ix)"
    r"(?P<key_quote>['\"]?)"
    r"(?P<key>[A-Za-z0-9_.-]*(?:password|passwd|pwd|passphrase|token|api[-_]?key|"
    r"client[-_]?secret)[A-Za-z0-9_.-]*)"
    r"(?P=key_quote)\s*(?P<separator>[:=]\s*)"
    r"(?P<value>['\"]?)[^\s,|}\]]+"
)
AUTHORIZATION_RE = re.compile(r"(?i)(authorization\s*[:=]\s*)[^\s,|}\]]+")
BEARER_RE = re.compile(r"(?i)(bearer\s+)[^\s,|}\]]+")
WINDOWS_ABSOLUTE_RE = re.compile(r"\b[A-Za-z]:[\\/][^\s|}\]]+")
POSIX_ABSOLUTE_RE = re.compile(r"(?<![\w.])/(?:Users|home|tmp|var|etc|mnt|opt)/[^\s|}\]]*")
DIAGNOSTIC_LIMIT = 300


@dataclass(frozen=True)
class ProviderCheckResult:
    provider_kind: str
    model: str
    ollama_version: str | None
    model_digest: str | None
    model_found: bool
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderGenerationRequest:
    model: str
    messages: list[dict[str, str]]
    schema: dict[str, Any]
    timeout_seconds: int
    # Optional per-request overrides; None keeps the provider defaults (NUM_CTX/NUM_PREDICT).
    num_ctx: int | None = None
    num_predict: int | None = None


@dataclass(frozen=True)
class ProviderGenerationResult:
    content: str
    provider_kind: str
    model: str
    ollama_version: str | None
    model_digest: str | None
    metrics: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1


class ModelProvider(Protocol):
    def check(self, model: str) -> ProviderCheckResult:
        """Validate that the provider is reachable and the model is installed."""

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        """Generate JSON that matches the request schema."""


class OllamaProviderError(Exception):
    def __init__(self, code: ProviderErrorCode, safe_message: str) -> None:
        super().__init__(f"{code.value}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class OllamaProvider:
    """Ollama's native /api/chat, optionally behind an authenticating proxy."""

    def __init__(
        self,
        base_url: str,
        *,
        allow_remote_provider: bool = False,
        connect_timeout_seconds: int = HTTP_CONNECT_TIMEOUT_SECONDS,
        timeout_seconds: int = HTTP_TIMEOUT_SECONDS,
        api_key: str | None = None,
    ) -> None:
        # A shared server behind an authenticating proxy is reached at a path such as
        # https://server/ollama with a bearer token. The plain loopback default stays
        # root-only and unauthenticated.
        self.base_url = validate_ollama_url(
            base_url,
            allow_remote_provider=allow_remote_provider,
            allow_path=allow_remote_provider or api_key is not None,
        )
        require_token_transport(self.base_url, api_key)
        self._api_key = api_key
        self.connect_timeout_seconds = connect_timeout_seconds
        self.timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )
        self._last_check: ProviderCheckResult | None = None

    def check(self, model: str) -> ProviderCheckResult:
        version = self._get_json("/api/version", timeout=self.connect_timeout_seconds)
        tags = self._get_json("/api/tags", timeout=self.connect_timeout_seconds)
        version_value = str(version.get("version", "")) if isinstance(version, dict) else None
        model_digest = _model_digest(tags, model)
        model_found = model_digest is not None
        if not model_found:
            raise OllamaProviderError(
                ProviderErrorCode.MODEL_NOT_FOUND,
                f"Requested Ollama model `{_safe_label(model)}` was not found.",
            )
        result = ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version=version_value or None,
            model_digest=model_digest,
            model_found=model_found,
            diagnostics=[],
        )
        self._last_check = result
        return result

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        check = self._last_check
        if check is None or check.model != request.model:
            check = self.check(request.model)
        payload = {
            "model": request.model,
            "messages": request.messages,
            "format": request.schema,
            "stream": False,
            "think": False,
            "options": {
                "temperature": TEMPERATURE,
                "num_predict": request.num_predict or NUM_PREDICT,
                "num_ctx": request.num_ctx or NUM_CTX,
            },
        }
        attempts = 0
        last_error: OllamaProviderError | None = None
        for attempt in range(2):
            attempts = attempt + 1
            try:
                response = self._post_json(
                    "/api/chat",
                    payload,
                    timeout=request.timeout_seconds,
                )
                return _generation_result(response, check, attempts)
            except OllamaProviderError as exc:
                last_error = exc
                if attempt == 0 and exc.code == ProviderErrorCode.PROVIDER_FAILED:
                    continue
                raise
        assert last_error is not None
        raise last_error

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = dict(extra or {})
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _get_json(self, path: str, *, timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(
            _join_api_url(self.base_url, path), method="GET", headers=self._headers()
        )
        return self._execute_json_request(request, timeout=timeout)

    def _post_json(self, path: str, payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(
            _join_api_url(self.base_url, path),
            method="POST",
            data=json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            headers=self._headers(
                {"Content-Type": "application/json", "Accept": "application/json"}
            ),
        )
        return self._execute_json_request(request, timeout=timeout)

    def model_context_length(self, model: str) -> int | None:
        """The context length the model advertises via /api/show, when available."""
        info = self._post_json("/api/show", {"model": model}, timeout=self.connect_timeout_seconds)
        model_info = info.get("model_info") if isinstance(info, dict) else None
        if not isinstance(model_info, dict):
            return None
        for key, value in sorted(model_info.items()):
            if str(key).endswith(".context_length") and isinstance(value, int):
                return value
        return None

    def _execute_json_request(
        self,
        request: urllib.request.Request,
        *,
        timeout: int,
    ) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            with self._opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_PROVIDER_RESPONSE_BYTES + 1)
        except TimeoutError as exc:
            raise OllamaProviderError(
                ProviderErrorCode.TIMEOUT,
                "Ollama request timed out.",
            ) from exc
        except urllib.error.HTTPError as exc:
            raw_error = _read_error_body(exc)
            code = (
                ProviderErrorCode.PROVIDER_UNAVAILABLE
                if exc.code in {404, 429, 500, 502, 503, 504}
                else ProviderErrorCode.PROVIDER_FAILED
            )
            raise OllamaProviderError(
                code,
                f"Ollama HTTP request failed with status {exc.code}. "
                f"Diagnostic: {_safe_diagnostic(raw_error)}",
            ) from exc
        except urllib.error.URLError as exc:
            raise OllamaProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                f"Ollama provider was unavailable. Diagnostic: {_safe_diagnostic(str(exc.reason))}",
            ) from exc
        except OSError as exc:
            raise OllamaProviderError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                f"Ollama request failed. Diagnostic: {_safe_diagnostic(str(exc))}",
            ) from exc
        if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
            raise OllamaProviderError(
                ProviderErrorCode.PROVIDER_FAILED,
                "Ollama response exceeded the supported byte limit.",
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaProviderError(
                ProviderErrorCode.PROVIDER_FAILED,
                "Ollama response was not valid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise OllamaProviderError(
                ProviderErrorCode.PROVIDER_FAILED,
                "Ollama response was not a JSON object.",
            )
        payload.setdefault("_wm_doc_elapsed_seconds", round(time.perf_counter() - start, 6))
        return payload


def validate_ollama_url(
    base_url: str,
    *,
    allow_remote_provider: bool = False,
    allow_path: bool = False,
) -> str:
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must use http or https.",
        )
    if not allow_remote_provider and parsed.scheme != "http":
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Default Ollama provider access only allows loopback HTTP.",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.params:
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must not contain credentials, query strings, or fragments.",
        )
    if not allow_path and parsed.path not in {"", "/"}:
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must point to the provider root.",
        )
    host = parsed.hostname
    if not host:
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must include a host.",
        )
    if not allow_remote_provider and host.casefold() not in {"localhost", "127.0.0.1", "::1"}:
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Remote Ollama providers require --allow-remote-provider.",
        )
    path = parsed.path.rstrip("/") if allow_path else ""
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, "", "", ""))


LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


def require_token_transport(base_url: str, api_key: str | None) -> None:
    """Refuse to send a token to a remote host over plain HTTP.

    A token to loopback (an SSH tunnel, say) never leaves the machine; one to a remote host
    over plain HTTP would be on the wire in clear.
    """
    if not api_key:
        return
    parsed = urllib.parse.urlparse(base_url)
    loopback = (parsed.hostname or "").casefold() in LOOPBACK_HOSTS
    if parsed.scheme != "https" and not loopback:
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Sending an API key to a remote host requires https. Use an https URL "
            "or tunnel the endpoint to loopback.",
        )


def _join_api_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + path


def _model_digest(tags: dict[str, Any], model: str) -> str | None:
    models = tags.get("models") if isinstance(tags, dict) else None
    if not isinstance(models, list):
        return None
    for item in models:
        if not isinstance(item, dict):
            continue
        names = {str(item.get("name", "")), str(item.get("model", ""))}
        if model in names:
            digest = item.get("digest")
            return str(digest) if digest else None
    return None


def _generation_result(
    response: dict[str, Any],
    check: ProviderCheckResult,
    attempts: int,
) -> ProviderGenerationResult:
    content = _message_content(response)
    metrics = {
        key: response[key]
        for key in (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "prompt_eval_duration",
            "eval_count",
            "eval_duration",
            "_wm_doc_elapsed_seconds",
        )
        if key in response
    }
    return ProviderGenerationResult(
        content=content,
        provider_kind=check.provider_kind,
        model=check.model,
        ollama_version=check.ollama_version,
        model_digest=check.model_digest,
        metrics=metrics,
        attempts=attempts,
    )


def _message_content(response: dict[str, Any]) -> str:
    message = response.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise OllamaProviderError(
            ProviderErrorCode.PROVIDER_FAILED,
            "Ollama response did not contain message.content.",
        )
    return message["content"]


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read(2048)
    except OSError:
        return ""
    try:
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return ""


def _safe_label(value: str) -> str:
    cleaned = CONTROL_RE.sub(" ", value)
    cleaned = " ".join(cleaned.split())
    return cleaned[:120] + ("..." if len(cleaned) > 120 else "")


def _safe_diagnostic(text: str) -> str:
    cleaned = CONTROL_RE.sub(" ", text)
    cleaned = SECRET_KEY_VALUE_RE.sub(
        lambda match: (
            f"{match.group('key_quote')}{match.group('key')}{match.group('key_quote')}"
            f"{match.group('separator')}[REDACTED]"
        ),
        cleaned,
    )
    cleaned = AUTHORIZATION_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", cleaned)
    cleaned = BEARER_RE.sub(lambda match: f"{match.group(1)}[REDACTED]", cleaned)
    cleaned = WINDOWS_ABSOLUTE_RE.sub("<path>", cleaned)
    cleaned = POSIX_ABSOLUTE_RE.sub("<path>", cleaned)
    cleaned = " ".join(cleaned.split())
    return cleaned[:DIAGNOSTIC_LIMIT] + ("..." if len(cleaned) > DIAGNOSTIC_LIMIT else "")
