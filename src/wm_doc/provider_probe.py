"""Find out how a (possibly proxied) Ollama server can be reached.

A shared server is often fronted by a proxy that checks a bearer token. Whether that proxy
forwards Ollama's native API (`/api/...`), only the OpenAI-compatible API (`/v1/...`), or
both decides which `--provider` to use and whether `--num-ctx` can be set per request. The
probe tries both and reports what worked, without printing the token.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wm_doc.ollama_provider import OllamaBusinessEnrichmentProvider, OllamaProviderError
from wm_doc.openai_compatible_provider import OpenAICompatibleProvider


@dataclass
class ProbeReport:
    native_ok: bool = False
    openai_ok: bool = False
    model_found: bool | None = None
    context_length: int | None = None
    lines: list[str] = field(default_factory=list)


def _v1_url(url: str) -> str:
    stripped = url.rstrip("/")
    return stripped if stripped.endswith("/v1") else f"{stripped}/v1"


def _native_url(url: str) -> str:
    stripped = url.rstrip("/")
    return stripped[: -len("/v1")] if stripped.endswith("/v1") else stripped


def probe_provider(
    url: str,
    *,
    api_key: str | None,
    model: str | None,
    allow_remote_provider: bool,
    timeout_seconds: int = 10,
) -> ProbeReport:
    report = ProbeReport()
    native_url = _native_url(url)
    openai_url = _v1_url(url)
    try:
        native = OllamaBusinessEnrichmentProvider(
            native_url,
            allow_remote_provider=allow_remote_provider,
            connect_timeout_seconds=timeout_seconds,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
        )
        if model:
            check = native.check(model)
            report.model_found = check.model_found
            try:
                report.context_length = native.model_context_length(model)
            except OllamaProviderError:
                report.context_length = None
            version = check.ollama_version or "unknown version"
        else:
            version_payload = native._get_json("/api/version", timeout=timeout_seconds)
            version = str(version_payload.get("version", "unknown version"))
        report.native_ok = True
        report.lines.append(f"native API ({native_url}/api): OK, Ollama {version}")
    except OllamaProviderError as exc:
        report.lines.append(f"native API ({native_url}/api): not available - {exc.safe_message}")
    try:
        openai = OpenAICompatibleProvider(
            openai_url,
            api_key=api_key,
            allow_remote_provider=allow_remote_provider,
            connect_timeout_seconds=timeout_seconds,
            timeout_seconds=timeout_seconds,
        )
        if model:
            openai.check(model)
            if report.model_found is None:
                report.model_found = True
        else:
            openai._request("/models", None, timeout=timeout_seconds)
        report.openai_ok = True
        report.lines.append(f"OpenAI-compatible API ({openai_url}): OK")
    except OllamaProviderError as exc:
        report.lines.append(
            f"OpenAI-compatible API ({openai_url}): not available - {exc.safe_message}"
        )
    if model and report.model_found:
        report.lines.append(f"model `{model}`: installed")
    if report.context_length:
        report.lines.append(f"model context length: {report.context_length} tokens")
    remote = " --allow-remote-provider" if allow_remote_provider else ""
    key = " --api-key-env <VARIABLE>" if api_key else ""
    if report.native_ok:
        report.lines.append(
            "Use the native API (context size is set per request with --num-ctx):\n"
            f"  wm-doc describe <packages> --model <model> --ollama-url {native_url}{remote}{key}"
        )
    elif report.openai_ok:
        report.lines.append(
            "Use the OpenAI-compatible API. It ignores per-request context sizes, so set "
            "OLLAMA_CONTEXT_LENGTH on the server and pass the same value as --num-ctx:\n"
            f"  wm-doc describe <packages> --model <model> --provider openai-compatible "
            f"--ollama-url {openai_url}{remote}{key} --num-ctx <server value>"
        )
    else:
        report.lines.append(
            "Neither API answered. Check the URL, the token variable and network access."
        )
    return report
