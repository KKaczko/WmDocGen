from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import ValidationError

from wm_doc.business_result_schema import (
    BusinessDraft,
    BusinessEnrichmentErrorCode,
    business_draft_json_schema,
)

HTTP_TIMEOUT_SECONDS = 600
HTTP_CONNECT_TIMEOUT_SECONDS = 5
MAX_PROVIDER_RESPONSE_BYTES = 4 * 1024 * 1024
PROMPT_VERSION = "business-enrichment-draft-prompt.v9"
TEMPERATURE = 0
NUM_PREDICT = 2048
# Ollama otherwise allocates the model's full advertised context (131072 tokens for
# qwen3.5), which inflated a 3.4 GB model to 8.9 GB resident and caused paging on
# memory-constrained machines. A business-context prompt runs ~4k tokens, so this
# leaves generous headroom for the prompt plus NUM_PREDICT output tokens.
NUM_CTX = 8192

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
    structured_output_ok: bool
    diagnostics: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProviderGenerationRequest:
    model: str
    messages: list[dict[str, str]]
    schema: dict[str, Any]
    timeout_seconds: int


@dataclass(frozen=True)
class ProviderGenerationResult:
    content: str
    provider_kind: str
    model: str
    ollama_version: str | None
    model_digest: str | None
    metrics: dict[str, Any] = field(default_factory=dict)
    attempts: int = 1


class BusinessEnrichmentProvider(Protocol):
    def check(self, model: str, *, structured_probe: bool = False) -> ProviderCheckResult:
        """Validate provider availability and optionally structured output support."""

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        """Generate structured business enrichment JSON."""


class OllamaProviderError(Exception):
    def __init__(self, code: BusinessEnrichmentErrorCode, safe_message: str) -> None:
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


class OllamaBusinessEnrichmentProvider:
    def __init__(
        self,
        base_url: str,
        *,
        allow_remote_provider: bool = False,
        connect_timeout_seconds: int = HTTP_CONNECT_TIMEOUT_SECONDS,
        timeout_seconds: int = HTTP_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = validate_ollama_url(base_url, allow_remote_provider=allow_remote_provider)
        self.connect_timeout_seconds = connect_timeout_seconds
        self.timeout_seconds = timeout_seconds
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirectHandler(),
        )
        self._last_check: ProviderCheckResult | None = None

    def check(self, model: str, *, structured_probe: bool = False) -> ProviderCheckResult:
        version = self._get_json("/api/version", timeout=self.connect_timeout_seconds)
        tags = self._get_json("/api/tags", timeout=self.connect_timeout_seconds)
        version_value = str(version.get("version", "")) if isinstance(version, dict) else None
        model_digest = _model_digest(tags, model)
        model_found = model_digest is not None
        if not model_found:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.MODEL_NOT_FOUND,
                f"Requested Ollama model `{_safe_label(model)}` was not found.",
            )
        structured_output_ok = True
        if structured_probe:
            structured_output_ok = self._structured_probe(model)
        result = ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version=version_value or None,
            model_digest=model_digest,
            model_found=model_found,
            structured_output_ok=structured_output_ok,
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
                "num_predict": NUM_PREDICT,
                "num_ctx": NUM_CTX,
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
                if attempt == 0 and exc.code == BusinessEnrichmentErrorCode.PROVIDER_FAILED:
                    continue
                raise
        assert last_error is not None
        raise last_error

    def _structured_probe(self, model: str) -> bool:
        evidence_id = "evidence_probe_service"
        schema = business_draft_json_schema()
        schema_text = json.dumps(
            schema,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return only JSON matching the supplied business draft schema. "
                        "Do not include Markdown. Use only the requested evidence id."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Draft schema: {schema_text}\n"
                        "Use this synthetic evidence id exactly: evidence_probe_service. "
                        "Return one direct claim about a service reading configuration. "
                        "The claim must include that evidence id. Return claims as an array; "
                        "inferences, unknowns, and limitations may be empty arrays."
                    ),
                }
            ],
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"temperature": TEMPERATURE, "num_predict": 256, "num_ctx": NUM_CTX},
        }
        response = self._post_json(
            "/api/chat",
            payload,
            timeout=min(self.timeout_seconds, 30),
        )
        content = _message_content(response)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_FAILED,
                "Ollama M8c draft-contract probe returned invalid JSON.",
            ) from exc
        try:
            draft = BusinessDraft.model_validate(parsed)
        except ValidationError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_FAILED,
                "Ollama M8c draft-contract probe did not match the draft schema.",
            ) from exc
        if any(evidence_id in item.evidence_ids for item in draft.claims):
            return True
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_FAILED,
            "Ollama M8c draft-contract probe did not preserve the synthetic evidence id.",
        )

    def _get_json(self, path: str, *, timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(_join_api_url(self.base_url, path), method="GET")
        return self._execute_json_request(request, timeout=timeout)

    def _post_json(self, path: str, payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(
            _join_api_url(self.base_url, path),
            method="POST",
            data=json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        return self._execute_json_request(request, timeout=timeout)

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
                BusinessEnrichmentErrorCode.TIMEOUT,
                "Ollama request timed out.",
            ) from exc
        except urllib.error.HTTPError as exc:
            raw_error = _read_error_body(exc)
            code = (
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE
                if exc.code in {404, 429, 500, 502, 503, 504}
                else BusinessEnrichmentErrorCode.PROVIDER_FAILED
            )
            raise OllamaProviderError(
                code,
                f"Ollama HTTP request failed with status {exc.code}. "
                f"Diagnostic: {_safe_diagnostic(raw_error)}",
            ) from exc
        except urllib.error.URLError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
                f"Ollama provider was unavailable. Diagnostic: {_safe_diagnostic(str(exc.reason))}",
            ) from exc
        except OSError as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
                f"Ollama request failed. Diagnostic: {_safe_diagnostic(str(exc))}",
            ) from exc
        if len(raw) > MAX_PROVIDER_RESPONSE_BYTES:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_FAILED,
                "Ollama response exceeded the supported byte limit.",
            )
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_FAILED,
                "Ollama response was not valid JSON.",
            ) from exc
        if not isinstance(payload, dict):
            raise OllamaProviderError(
                BusinessEnrichmentErrorCode.PROVIDER_FAILED,
                "Ollama response was not a JSON object.",
            )
        payload.setdefault("_wm_doc_elapsed_seconds", round(time.perf_counter() - start, 6))
        return payload


def validate_ollama_url(base_url: str, *, allow_remote_provider: bool = False) -> str:
    parsed = urllib.parse.urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must use http or https.",
        )
    if not allow_remote_provider and parsed.scheme != "http":
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
            "Default Ollama provider access only allows loopback HTTP.",
        )
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.params:
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must not contain credentials, query strings, or fragments.",
        )
    if parsed.path not in {"", "/"}:
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must point to the provider root.",
        )
    host = parsed.hostname
    if not host:
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
            "Ollama URL must include a host.",
        )
    if not allow_remote_provider and host.casefold() not in {"localhost", "127.0.0.1", "::1"}:
        raise OllamaProviderError(
            BusinessEnrichmentErrorCode.PROVIDER_UNAVAILABLE,
            "Remote Ollama providers require --allow-remote-provider.",
        )
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


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
            BusinessEnrichmentErrorCode.PROVIDER_FAILED,
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
