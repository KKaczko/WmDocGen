from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Annotated

import typer

from wm_doc.analysis_cache import analyze_cached, default_analysis_cache_dir
from wm_doc.builtins import PlatformServicesError, use_platform_catalog
from wm_doc.config import AppConfig, load_config
from wm_doc.describer import (
    MAX_INSTRUCTIONS_CHARS,
    STATE_ORDER,
    DescribeError,
    DescribeOptions,
    DescribeOutcome,
    DescribeResult,
    DescribeStats,
    DetailLevel,
    approve_docs,
    collect_states,
    current_facts_hashes,
    describe_services,
    export_designer_comments,
    render_status,
)
from wm_doc.discovery import scan_path
from wm_doc.effects import compute_service_facts
from wm_doc.explorer.build import ExplorerOptions, build_bundle
from wm_doc.explorer.contract import DescriptionsShown
from wm_doc.explorer.ids import IdCollisionError
from wm_doc.explorer.inputs import explorer_inputs
from wm_doc.explorer.serve import is_loopback, make_server
from wm_doc.explorer.synthetic import write_demo_descriptions, write_demo_packages
from wm_doc.explorer.write import ExplorerOutputError, check_output_location, write_explorer
from wm_doc.external_systems import (
    EMPTY_CATALOG,
    ExternalSystemCatalog,
    ExternalSystemsError,
    load_external_systems,
)
from wm_doc.graph_publish import (
    GRAPH_RENDER_TIMEOUT_SECONDS,
    GraphAsset,
    GraphRenderFormat,
    GraphRenderMode,
    GraphRenderResult,
    GraphvizRunner,
    build_graph_assets,
    graph_render_failures,
    render_graphs,
    rendered_count,
    run_subprocess,
)
from wm_doc.ir import AnalysisResult
from wm_doc.ollama_provider import (
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_TIMEOUT_SECONDS,
    ModelProvider,
    OllamaProvider,
    OllamaProviderError,
)
from wm_doc.openai_compatible_provider import (
    OpenAICompatibleProvider,
    resolve_api_key,
)
from wm_doc.output_cleanup import OutputCleanupError
from wm_doc.output_cleanup import remove_managed_path as _remove_managed_path
from wm_doc.overviews import (
    describe_overviews,
    overview_states,
    package_overview_docs,
    progress_label,
    service_purposes,
    summarize_packages,
)
from wm_doc.provider_probe import probe_provider
from wm_doc.render.analysis_json import write_analysis_json
from wm_doc.render.artifact_markdown import write_artifact_inventory
from wm_doc.render.catalogue_markdown import SERVICE_CATALOGUE, write_service_catalogue
from wm_doc.render.document_markdown import write_document_markdown
from wm_doc.render.dot import (
    write_dependency_dot,
    write_document_dot,
    write_process_dots,
    write_scope_document_dot,
    write_scope_dot,
    write_scoped_process_dot,
)
from wm_doc.render.graph_markdown import write_graph_index
from wm_doc.render.index_markdown import (
    write_analysis_limitations,
    write_documentation_index,
)
from wm_doc.render.json import render_inventory_json
from wm_doc.render.markdown import render_inventory_markdown
from wm_doc.render.package_markdown import (
    render_packages_index_section,
    render_server_overview_section,
    write_package_markdown,
)
from wm_doc.render.platform_markdown import write_platform_services
from wm_doc.render.process_markdown import (
    write_entrypoint_candidates_markdown,
    write_process_markdown,
)
from wm_doc.render.scope_markdown import (
    write_scope_json,
    write_scope_markdown,
    write_scoped_document_markdown,
    write_scoped_entrypoints_markdown,
    write_scoped_index_markdown,
    write_scoped_process_markdown,
    write_scoped_service_markdown,
)
from wm_doc.render.service_graph import ServiceGraphContext, write_service_graphs
from wm_doc.render.service_markdown import service_markdown_filenames, write_service_markdown
from wm_doc.scope_analysis import (
    ScopeRequest,
    ScopeResult,
    ScopeSelectorType,
    build_focused_scope,
    services_for_scope,
    validate_scope_request,
)
from wm_doc.service_docs import (
    DocState,
    doc_path,
    iter_docs,
    load_service_docs,
    overview_doc_path,
    read_doc,
)
from wm_doc.shapes import render_shapes
from wm_doc.stats import render_stats
from wm_doc.summarizer import DEFAULT_NUM_CTX
from wm_doc.summarizer import default_cache_dir as default_describe_cache_dir

app = typer.Typer(
    help="Offline deterministic static inventory for webMethods Integration Server packages."
)

IncludePackageOption = Annotated[
    list[str] | None,
    typer.Option(
        "--include-package",
        help="Only analyse packages whose directory name matches this glob (repeatable).",
    ),
]
ExcludePackageOption = Annotated[
    list[str] | None,
    typer.Option(
        "--exclude-package",
        help="Also skip packages whose directory name matches this glob (repeatable).",
    ),
]
AllPackagesOption = Annotated[
    bool,
    typer.Option(
        "--all-packages",
        help="Do not skip Wm*, Default or system packages by default.",
    ),
]


ExternalSystemsOption = Annotated[
    Path | None,
    typer.Option(
        "--external-systems",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="YAML catalog naming the systems behind namespaces outside the analysed packages.",
    ),
]


def _load_external_systems_or_exit(path: Path | None) -> ExternalSystemCatalog:
    try:
        return load_external_systems(path)
    except ExternalSystemsError as exc:
        typer.echo(f"EXTERNAL_SYSTEMS_INVALID: {exc}", err=True)
        raise typer.Exit(code=2) from exc


PlatformServicesOption = Annotated[
    Path | None,
    typer.Option(
        "--platform-services",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="YAML file adding or overriding descriptions of platform (pub.*, wm.*) services.",
    ),
]


def _use_platform_services_or_exit(path: Path | None) -> None:
    """Start every command from the shipped platform catalog plus the user's file."""
    try:
        use_platform_catalog(path)
    except PlatformServicesError as exc:
        typer.echo(f"PLATFORM_SERVICES_INVALID: {exc}", err=True)
        raise typer.Exit(code=2) from exc


NoAnalysisCacheOption = Annotated[
    bool,
    typer.Option(
        "--no-analysis-cache",
        help="Analyse from scratch instead of reusing the last analysis of unchanged packages.",
    ),
]


def _analyze(
    packages_path: Path,
    config: AppConfig,
    processes_file: Path | None = None,
    *,
    no_cache: bool = False,
) -> AnalysisResult:
    analysis, reused = analyze_cached(
        packages_path,
        config,
        processes_file,
        processes_file_explicit=processes_file is not None,
        cache_dir=None if no_cache else default_analysis_cache_dir(),
    )
    if reused:
        typer.echo(
            "Reused the cached analysis: no package file changed since the last run.", err=True
        )
    return analysis


def _with_package_selection(
    config: AppConfig,
    include: list[str] | None,
    exclude: list[str] | None,
    all_packages: bool,
) -> AppConfig:
    selection = config.packages
    if all_packages:
        selection = selection.model_copy(update={"exclude": [], "skipSystemPackages": False})
    if include:
        selection = selection.model_copy(update={"include": list(include)})
    if exclude:
        selection = selection.model_copy(update={"exclude": [*selection.exclude, *exclude]})
    return config.model_copy(update={"packages": selection})


GRAPHVIZ_RUNNER: GraphvizRunner = run_subprocess
MANAGED_ROOT_FILES = (
    "analysis.json",
    "index.md",
    "entrypoints.md",
    "scope.json",
    "scope.md",
    "LIMITATIONS.md",
    # Outputs of the summarize prototype; still cleaned so old directories do not keep them.
    "ai-summaries.json",
    "ai-summaries.md",
    "artifacts.md",
    "platform-services.md",
    "service-catalogue.md",
)
MANAGED_ROOT_DIRS = ("services", "documents", "processes", "graphs", "packages")


def _default_provider_factory(
    ollama_url: str,
    *,
    allow_remote_provider: bool,
    connect_timeout_seconds: int,
    timeout_seconds: int,
    provider_kind: str = "ollama",
    api_key_env: str | None = None,
) -> ModelProvider:
    if provider_kind == "openai-compatible":
        # Shared Ollama servers sit behind a proxy that terminates TLS and checks a
        # bearer token; the token is read from the environment, never from a flag.
        return OpenAICompatibleProvider(
            ollama_url,
            api_key=resolve_api_key(api_key_env),
            allow_remote_provider=allow_remote_provider,
            connect_timeout_seconds=connect_timeout_seconds,
            timeout_seconds=timeout_seconds,
        )
    return OllamaProvider(
        ollama_url,
        allow_remote_provider=allow_remote_provider,
        connect_timeout_seconds=connect_timeout_seconds,
        timeout_seconds=timeout_seconds,
        # The native API can sit behind the same authenticating proxy; the token still
        # comes only from the environment variable.
        api_key=resolve_api_key(api_key_env) if api_key_env else None,
    )


DESCRIBE_PROVIDER_FACTORY = _default_provider_factory


@app.callback()
def main() -> None:
    """Offline deterministic static inventory for webMethods packages."""


@app.command()
def scan(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for inventory outputs.")
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    ] = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
) -> None:
    """Discover packages and artifact candidates without executing analyzed code."""
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    inventory = scan_path(packages_path, app_config.packages)
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(render_inventory_json(inventory), encoding="utf-8")
    (output / "fixture-inventory.md").write_text(
        render_inventory_markdown(inventory), encoding="utf-8"
    )
    typer.echo(
        f"Scanned {len(inventory.packages)} package(s); wrote {output / 'inventory.json'} "
        f"and {output / 'fixture-inventory.md'}."
    )


@app.command()
def stats(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Also write the report to this Markdown file."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    ] = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
    platform_services_file: PlatformServicesOption = None,
) -> None:
    """Print counts and names (no code or values) to plan documentation of a server."""
    _use_platform_services_or_exit(platform_services_file)
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    report = render_stats(_analyze(packages_path, app_config, no_cache=no_analysis_cache))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    typer.echo(report)


@app.command("probe-shapes")
def probe_shapes(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Also write the report to this Markdown file."),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    ] = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
) -> None:
    """Print node.ndf key paths of triggers, descriptors and adapters (no values)."""
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    analysis = _analyze(packages_path, app_config, no_cache=no_analysis_cache)
    report = render_shapes(analysis, packages_path)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
    typer.echo(report)


@app.command("provider-probe")
def provider_probe_command(
    url: Annotated[
        str,
        typer.Option("--url", help="Server URL, e.g. https://server/ollama or .../ollama/v1."),
    ],
    model: Annotated[
        str | None, typer.Option("--model", help="Also check that this model is installed.")
    ] = None,
    api_key_env: Annotated[
        str | None,
        typer.Option(
            "--api-key-env",
            help="Environment variable holding the bearer token (never passed as a flag).",
        ),
    ] = None,
    allow_remote_provider: Annotated[
        bool,
        typer.Option("--allow-remote-provider", help="Allow non-loopback server URLs."),
    ] = False,
    timeout_seconds: Annotated[
        int, typer.Option("--timeout-seconds", help="Timeout per request in seconds.")
    ] = 10,
) -> None:
    """Report whether a server answers on the native or the OpenAI-compatible API."""
    api_key = resolve_api_key(api_key_env) if api_key_env else None
    if api_key_env and not api_key:
        typer.echo(f"Environment variable {api_key_env} is not set or empty.", err=True)
        raise typer.Exit(code=2)
    report = probe_provider(
        url,
        api_key=api_key,
        model=model,
        allow_remote_provider=allow_remote_provider,
        timeout_seconds=timeout_seconds,
    )
    for line in report.lines:
        typer.echo(line)
    if not (report.native_ok or report.openai_ok):
        raise typer.Exit(code=1)


@app.command()
def analyze(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for analysis outputs.")
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    ] = None,
    processes_file: Annotated[
        Path | None,
        typer.Option(
            "--processes-file",
            help="Optional processes.yml catalog for user-authored process entrypoints.",
        ),
    ] = None,
    render_graphs_mode: Annotated[
        GraphRenderMode,
        typer.Option(
            "--render-graphs",
            help="Render generated DOT graphs with Graphviz.",
        ),
    ] = GraphRenderMode.NONE,
    graphviz_dot: Annotated[
        Path | None,
        typer.Option(
            "--graphviz-dot",
            help="Optional path to the Graphviz dot executable.",
        ),
    ] = None,
    target_service: Annotated[
        list[str] | None,
        typer.Option(
            "--target-service",
            help="Publish a focused scope rooted at one exact canonical service name.",
        ),
    ] = None,
    target_namespace: Annotated[
        list[str] | None,
        typer.Option(
            "--target-namespace",
            help="Publish a focused scope rooted at a namespace prefix and descendants.",
        ),
    ] = None,
    target_package: Annotated[
        list[str] | None,
        typer.Option(
            "--target-package",
            help="Publish a focused scope rooted at one exact package identity.",
        ),
    ] = None,
    target_process: Annotated[
        list[str] | None,
        typer.Option(
            "--target-process",
            help="Publish a focused scope rooted at one exact processes.yml process id.",
        ),
    ] = None,
    dependency_depth: Annotated[
        str,
        typer.Option(
            "--dependency-depth",
            help="Focused publication dependency depth: 0, 1, N, or all.",
        ),
    ] = "all",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Include full mapping, FLOW outline, call and source-evidence detail.",
        ),
    ] = False,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
    external_systems_file: ExternalSystemsOption = None,
    platform_services_file: PlatformServicesOption = None,
    docs_dir: Annotated[
        Path | None,
        typer.Option(
            "--docs-dir",
            help="Show the per-service descriptions from this directory on service pages and "
            "write service-catalogue.md.",
        ),
    ] = None,
) -> None:
    """Analyze supported services and emit deterministic technical outputs."""
    try:
        scope_request = _scope_request_from_cli(
            target_service=target_service,
            target_namespace=target_namespace,
            target_package=target_package,
            target_process=target_process,
            dependency_depth=dependency_depth,
        )
    except ScopeCliError as exc:
        typer.echo(f"{exc.code}: {exc.safe_message}", err=True)
        raise typer.Exit(code=2) from exc
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    external_catalog = _load_external_systems_or_exit(external_systems_file)
    _use_platform_services_or_exit(platform_services_file)
    analysis = _analyze(
        packages_path, app_config, processes_file, no_cache=no_analysis_cache
    )
    if scope_request is not None:
        process_catalog_available = _process_catalog_available(packages_path, processes_file)
        scope_output = build_focused_scope(
            analysis,
            scope_request,
            process_catalog_available=process_catalog_available,
        )
        if not scope_output.should_publish or scope_output.scope is None:
            code_suffix = f" [{scope_output.code}]" if scope_output.code is not None else ""
            typer.echo(
                f"Focused publication scope failed{code_suffix}:\n"
                f"{scope_output.message or 'scope could not be resolved'}",
                err=True,
            )
            raise typer.Exit(code=scope_output.exit_code or 1)
        graph_failures = _write_scoped_outputs(
            output,
            analysis,
            scope_output.scope,
            render_graphs_mode,
            graphviz_dot,
            verbose=verbose,
        )
        if graph_failures:
            _echo_graph_failures(graph_failures)
            raise typer.Exit(code=1)
        if scope_output.exit_code:
            typer.echo(
                "Focused publication completed with scope findings that require attention.",
                err=True,
            )
            raise typer.Exit(code=scope_output.exit_code)
        return
    report, graph_failures = _write_full_outputs(
        output,
        analysis,
        render_graphs_mode,
        graphviz_dot,
        verbose=verbose,
        docs_dir=docs_dir,
        external_systems=external_catalog,
    )
    typer.echo(report)
    if graph_failures:
        _echo_graph_failures(graph_failures)
        raise typer.Exit(code=1)


DocsDirOption = Annotated[
    Path,
    typer.Option("--docs-dir", help="Directory of per-service description files."),
]


ModelOption = Annotated[str, typer.Option("--model", help="Installed Ollama model to use.")]
ConfigOption = Annotated[
    Path | None,
    typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
]
ProcessesFileOption = Annotated[
    Path | None,
    typer.Option("--processes-file", help="Optional processes.yml catalog."),
]
DetailOption = Annotated[
    DetailLevel,
    typer.Option(
        "--detail",
        case_sensitive=False,
        help=(
            "How much each description says: brief (main steps only, fastest), standard "
            "(adds the detailed flow), thorough (standard, then a check that the detailed "
            "flow names every call that matters, with one more request to add missing ones) "
            "or deep (the detailed flow, written after the model reasons about the facts; "
            "thinking-capable models only, several times slower; use --num-ctx 32768)."
        ),
    ),
]
InstructionsOption = Annotated[
    Path | None,
    typer.Option(
        "--instructions",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help=(
            "Text file with your own extra instructions for the model (style, audience, "
            f"terms to use), at most {MAX_INSTRUCTIONS_CHARS} characters. They never "
            "override the rules: only the facts, names copied exactly."
        ),
    ),
]


def _read_instructions_or_exit(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        typer.echo("INSTRUCTIONS_INVALID: the file could not be read as UTF-8 text.", err=True)
        raise typer.Exit(code=2) from exc
    if not text:
        typer.echo("INSTRUCTIONS_INVALID: the file is empty.", err=True)
        raise typer.Exit(code=2)
    if len(text) > MAX_INSTRUCTIONS_CHARS:
        typer.echo(
            f"INSTRUCTIONS_INVALID: the file has {len(text)} characters; the limit is "
            f"{MAX_INSTRUCTIONS_CHARS}.",
            err=True,
        )
        raise typer.Exit(code=2)
    return text


def _duration(seconds: float) -> str:
    """42 s, 3 min 05 s, 2 h 07 min."""
    whole = int(round(seconds))
    if whole < 60:
        return f"{whole} s"
    if whole < 3600:
        return f"{whole // 60} min {whole % 60:02d} s"
    return f"{whole // 3600} h {whole % 3600 // 60:02d} min"


def _progress_line(position: int, total: int, label: str, result: DescribeResult) -> str:
    note = f" ({result.note})" if result.note else ""
    took = f" [{_duration(result.seconds)}]" if result.seconds is not None else ""
    return f"[{position}/{total}] {label}: {result.outcome.value}{note}{took}"


KeepUnverifiedOption = Annotated[
    bool,
    typer.Option(
        "--keep-unverified",
        help=(
            "Still write a draft whose answer names things the facts do not contain (after "
            "the retry), marked with those names. Answers that fail the disclosure scan are "
            "never kept."
        ),
    ),
]
RedoDraftsOption = Annotated[
    bool,
    typer.Option(
        "--redo-drafts",
        help="Regenerate unedited drafts even when their facts did not change.",
    ),
]
OllamaUrlOption = Annotated[str, typer.Option("--ollama-url", help="Ollama provider URL.")]
TimeoutOption = Annotated[
    int, typer.Option("--timeout-seconds", help="Per-request timeout in seconds.")
]
AllowRemoteProviderOption = Annotated[
    bool,
    typer.Option("--allow-remote-provider", help="Allow non-loopback Ollama provider URLs."),
]
NumCtxOption = Annotated[
    int,
    typer.Option(
        "--num-ctx",
        min=4096,
        help="Model context window in tokens. Larger fits bigger services but uses more "
        "memory on the Ollama host.",
    ),
]
NoCacheOption = Annotated[bool, typer.Option("--no-cache", help="Disable cache reads and writes.")]
RefreshOption = Annotated[
    bool, typer.Option("--refresh", help="Ignore cached drafts and ask the model again.")
]
CacheDirOption = Annotated[
    Path | None, typer.Option("--cache-dir", help="Cache directory for validated drafts.")
]
ProviderKindOption = Annotated[
    str,
    typer.Option(
        "--provider",
        help="'ollama' (native API, also through a proxy path) or 'openai-compatible' "
        "(the /v1 API; set --num-ctx to the server's configured context length).",
    ),
]
ApiKeyEnvOption = Annotated[
    str | None,
    typer.Option(
        "--api-key-env",
        help="Environment variable holding a bearer token for a proxied server. The token "
        "is never read from a flag.",
    ),
]
ParallelOption = Annotated[
    int,
    typer.Option(
        "--parallel",
        min=1,
        max=16,
        help="Requests in flight at once; useful only if the server runs several in "
        "parallel (OLLAMA_NUM_PARALLEL).",
    ),
]


@app.command()
def describe(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    model: ModelOption,
    docs_dir: DocsDirOption = Path("service-docs"),
    service: Annotated[
        list[str] | None,
        typer.Option("--service", help="Describe this service (repeatable)."),
    ] = None,
    namespace: Annotated[
        str | None,
        typer.Option("--namespace", help="Describe every service under this namespace."),
    ] = None,
    package: Annotated[
        str | None, typer.Option("--package", help="Describe every service in this package.")
    ] = None,
    all_services: Annotated[
        bool, typer.Option("--all", help="Describe every analysed service.")
    ] = False,
    with_callees: Annotated[
        bool,
        typer.Option(
            "--with-callees",
            help="Also describe the services the selection calls (callees are done first).",
        ),
    ] = False,
    redo_drafts: RedoDraftsOption = False,
    keep_unverified: KeepUnverifiedOption = False,
    detail: DetailOption = DetailLevel.STANDARD,
    instructions_file: InstructionsOption = None,
    config: ConfigOption = None,
    processes_file: ProcessesFileOption = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
    external_systems_file: ExternalSystemsOption = None,
    platform_services_file: PlatformServicesOption = None,
    ollama_url: OllamaUrlOption = "http://localhost:11434",
    timeout_seconds: TimeoutOption = HTTP_TIMEOUT_SECONDS,
    allow_remote_provider: AllowRemoteProviderOption = False,
    num_ctx: NumCtxOption = DEFAULT_NUM_CTX,
    no_cache: NoCacheOption = False,
    refresh: RefreshOption = False,
    cache_dir: CacheDirOption = None,
    provider_kind: ProviderKindOption = "ollama",
    api_key_env: ApiKeyEnvOption = None,
    parallel: ParallelOption = 1,
) -> None:
    """Write or refresh per-service description files with a local model, callees first."""
    if not model.strip():
        typer.echo("DESCRIBE_INPUT_INVALID: --model must not be blank.", err=True)
        raise typer.Exit(code=2)
    selectors = sum(
        1 for chosen in (bool(service), namespace is not None, package is not None, all_services)
        if chosen
    )
    if selectors != 1:
        typer.echo(
            "DESCRIBE_INPUT_INVALID: choose exactly one of --service, --namespace, --package "
            "or --all.",
            err=True,
        )
        raise typer.Exit(code=2)
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    external_catalog = _load_external_systems_or_exit(external_systems_file)
    _use_platform_services_or_exit(platform_services_file)
    analysis = _analyze(
        packages_path, app_config, processes_file, no_cache=no_analysis_cache
    )
    selected = _describe_selection(
        analysis,
        packages_path,
        processes_file,
        services=service or [],
        namespace=namespace,
        package=package,
        all_services=all_services,
        with_callees=with_callees,
    )

    instructions = _read_instructions_or_exit(instructions_file)

    def report_progress(position: int, total: int, result: DescribeResult) -> None:
        typer.echo(_progress_line(position, total, result.service, result))

    started = time.perf_counter()

    try:
        provider = _model_provider(
            ollama_url, allow_remote_provider, timeout_seconds, provider_kind, api_key_env
        )
        results, describe_stats = describe_services(
            analysis,
            selected,
            provider,
            DescribeOptions(
                model=model.strip(),
                scan_root=packages_path,
                config=app_config,
                docs_dir=docs_dir,
                cache_dir=None if no_cache else (cache_dir or default_describe_cache_dir()),
                no_cache=no_cache,
                refresh=refresh,
                redo_drafts=redo_drafts,
                keep_unverified=keep_unverified,
                detail=detail,
                instructions=instructions,
                num_ctx=num_ctx,
                timeout_seconds=timeout_seconds,
                external_systems=external_catalog,
                parallel=parallel,
            ),
            progress=report_progress,
        )
    except OllamaProviderError as exc:
        typer.echo(f"{exc.code.value}: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc
    except DescribeError as exc:
        typer.echo(f"DESCRIBE_FAILED: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc
    _echo_generation_summary(
        f"Described {len(selected)} service(s) into {docs_dir} (detail: {detail.value}):",
        describe_stats,
        num_ctx,
        "Next: review the drafts, approve them with `wm-doc approve`, and publish with "
        "`wm-doc analyze ... --docs-dir`.",
        run_seconds=time.perf_counter() - started,
        noun="services",
    )
    if any("timed out" in (result.note or "") for result in results):
        typer.echo(
            "Hint: some requests timed out. Long answers (and --detail deep, where the model "
            "thinks first) need more time: raise --timeout-seconds (for example 1800) or use "
            "a lower --detail."
        )


def _model_provider(
    ollama_url: str,
    allow_remote_provider: bool,
    timeout_seconds: int,
    provider_kind: str,
    api_key_env: str | None,
) -> ModelProvider:
    return DESCRIBE_PROVIDER_FACTORY(
        ollama_url,
        allow_remote_provider=allow_remote_provider,
        connect_timeout_seconds=HTTP_CONNECT_TIMEOUT_SECONDS,
        timeout_seconds=timeout_seconds,
        provider_kind=provider_kind.strip(),
        api_key_env=(api_key_env or "").strip() or None,
    )


def _echo_generation_summary(
    header: str,
    stats: DescribeStats,
    num_ctx: int,
    next_step: str,
    *,
    run_seconds: float | None = None,
    noun: str = "items",
) -> None:
    counts = stats.counts
    tokens = stats.prompt_tokens
    timing = ""
    if stats.model_calls:
        average = stats.model_seconds / stats.model_calls
        speed = (
            f", {stats.answer_tokens / stats.model_seconds:.0f} answer tokens/s"
            if stats.answer_tokens and stats.model_seconds
            else ""
        )
        timing = (
            f"- model time: {_duration(stats.model_seconds)} for {stats.model_calls} "
            f"request(s), {_duration(average)} each on average{speed}\n"
        )
        asked = sum(
            counts.get(outcome, 0)
            for outcome in (
                DescribeOutcome.GENERATED,
                DescribeOutcome.UNVERIFIED,
                DescribeOutcome.REJECTED,
                DescribeOutcome.FAILED,
            )
        )
        if run_seconds and asked:
            per_hour = asked / run_seconds * 3600
            timing += (
                f"- run time: {_duration(run_seconds)}; at this pace about "
                f"{per_hour:.0f} {noun} per hour\n"
            )
    typer.echo(
        f"{header}\n"
        f"- new drafts: {counts.get(DescribeOutcome.GENERATED, 0)} generated, "
        f"{counts.get(DescribeOutcome.CACHED, 0)} from cache\n"
        f"- drafts kept (facts unchanged): {counts.get(DescribeOutcome.UNCHANGED, 0)}\n"
        f"- approved or edited, kept: {counts.get(DescribeOutcome.PROTECTED, 0)}\n"
        f"- rejected by validation: {counts.get(DescribeOutcome.REJECTED, 0)}\n"
        f"- kept with unverified names: {counts.get(DescribeOutcome.UNVERIFIED, 0)}\n"
        f"- generation failed: {counts.get(DescribeOutcome.FAILED, 0)}\n"
        f"- corrective retries: {stats.retried}\n"
        + (
            f"- completeness passes (thorough): {stats.coverage_passes}\n"
            if stats.coverage_passes
            else ""
        )
        + f"- facts shortened to fit: {stats.shortened}\n"
        f"- largest prompt: {max(tokens) if tokens else 'n/a'} tokens of {num_ctx}\n"
        f"{timing}"
        f"{next_step}"
    )


@app.command()
def overview(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    model: ModelOption,
    docs_dir: DocsDirOption = Path("service-docs"),
    package: Annotated[
        list[str] | None,
        typer.Option("--package", help="Write the overview of this package (repeatable)."),
    ] = None,
    all_overviews: Annotated[
        bool, typer.Option("--all", help="Write the overview of every analysed package.")
    ] = False,
    server: Annotated[
        bool,
        typer.Option(
            "--server",
            help="Also write the server overview, from the package overviews (run it after "
            "the package overviews it should use).",
        ),
    ] = False,
    redo_drafts: RedoDraftsOption = False,
    instructions_file: InstructionsOption = None,
    config: ConfigOption = None,
    processes_file: ProcessesFileOption = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
    external_systems_file: ExternalSystemsOption = None,
    platform_services_file: PlatformServicesOption = None,
    ollama_url: OllamaUrlOption = "http://localhost:11434",
    timeout_seconds: TimeoutOption = HTTP_TIMEOUT_SECONDS,
    allow_remote_provider: AllowRemoteProviderOption = False,
    num_ctx: NumCtxOption = DEFAULT_NUM_CTX,
    no_cache: NoCacheOption = False,
    refresh: RefreshOption = False,
    cache_dir: CacheDirOption = None,
    provider_kind: ProviderKindOption = "ollama",
    api_key_env: ApiKeyEnvOption = None,
    parallel: ParallelOption = 1,
) -> None:
    """Write or refresh package overviews, and optionally the server overview."""
    if not model.strip():
        typer.echo("OVERVIEW_INPUT_INVALID: --model must not be blank.", err=True)
        raise typer.Exit(code=2)
    if (package and all_overviews) or not (package or all_overviews or server):
        typer.echo(
            "OVERVIEW_INPUT_INVALID: choose --package (repeatable) or --all, and/or --server.",
            err=True,
        )
        raise typer.Exit(code=2)
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    external_catalog = _load_external_systems_or_exit(external_systems_file)
    _use_platform_services_or_exit(platform_services_file)
    analysis = _analyze(packages_path, app_config, processes_file, no_cache=no_analysis_cache)
    known = {p.name for p in analysis.packages}
    selected = sorted(known, key=str.casefold) if all_overviews else list(package or [])
    missing = [name for name in selected if name not in known]
    if missing:
        typer.echo(
            f"OVERVIEW_INPUT_INVALID: unknown package(s): {', '.join(missing)}", err=True
        )
        raise typer.Exit(code=2)

    instructions = _read_instructions_or_exit(instructions_file)

    def report_progress(position: int, total: int, result: DescribeResult) -> None:
        typer.echo(_progress_line(position, total, progress_label(result), result))

    started = time.perf_counter()

    try:
        provider = _model_provider(
            ollama_url, allow_remote_provider, timeout_seconds, provider_kind, api_key_env
        )
        results, overview_stats = describe_overviews(
            analysis,
            selected,
            provider,
            DescribeOptions(
                model=model.strip(),
                scan_root=packages_path,
                config=app_config,
                docs_dir=docs_dir,
                cache_dir=None if no_cache else (cache_dir or default_describe_cache_dir()),
                no_cache=no_cache,
                refresh=refresh,
                redo_drafts=redo_drafts,
                instructions=instructions,
                num_ctx=num_ctx,
                timeout_seconds=timeout_seconds,
                external_systems=external_catalog,
                parallel=parallel,
            ),
            server=server,
            progress=report_progress,
        )
    except OllamaProviderError as exc:
        typer.echo(f"{exc.code.value}: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc
    except DescribeError as exc:
        typer.echo(f"OVERVIEW_FAILED: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc
    _echo_generation_summary(
        f"Wrote {len(results)} overview(s) into {docs_dir}:",
        overview_stats,
        num_ctx,
        "Next: review the drafts, approve them with `wm-doc approve --service package:<Package>` "
        "or `--service server`, and publish with `wm-doc analyze ... --docs-dir`.",
        run_seconds=time.perf_counter() - started,
        noun="overviews",
    )

def _describe_selection(
    analysis: AnalysisResult,
    packages_path: Path,
    processes_file: Path | None,
    *,
    services: list[str],
    namespace: str | None,
    package: str | None,
    all_services: bool,
    with_callees: bool,
) -> list[str]:
    known = {s.identity.full_name for p in analysis.packages for s in p.services}
    if all_services:
        return sorted(known, key=str.casefold)
    requests: list[ScopeRequest] = []
    depth = None if with_callees else 0
    if services:
        missing = [name for name in services if name not in known]
        if missing:
            typer.echo(
                f"DESCRIBE_INPUT_INVALID: unknown service(s): {', '.join(missing)}", err=True
            )
            raise typer.Exit(code=2)
        if not with_callees:
            return services
        requests = [ScopeRequest(ScopeSelectorType.SERVICE, name, depth) for name in services]
    elif namespace is not None:
        requests = [ScopeRequest(ScopeSelectorType.NAMESPACE, namespace, depth)]
    elif package is not None:
        requests = [ScopeRequest(ScopeSelectorType.PACKAGE, package, depth)]
    selected: set[str] = set()
    catalog_available = _process_catalog_available(packages_path, processes_file)
    for request in requests:
        output = build_focused_scope(
            analysis, request, process_catalog_available=catalog_available
        )
        if output.scope is None:
            typer.echo(
                f"DESCRIBE_INPUT_INVALID: {output.message or 'selection could not be resolved'}",
                err=True,
            )
            raise typer.Exit(code=2)
        selected.update(
            service.identity.full_name for service in services_for_scope(analysis, output.scope)
        )
    return sorted(selected, key=str.casefold)


@app.command()
def approve(
    docs_dir: DocsDirOption = Path("service-docs"),
    service: Annotated[
        list[str] | None, typer.Option("--service", help="Approve this service (repeatable).")
    ] = None,
    package: Annotated[
        str | None, typer.Option("--package", help="Approve every draft in this package.")
    ] = None,
    all_drafts: Annotated[
        bool, typer.Option("--all-drafts", help="Approve every draft in the directory.")
    ] = False,
) -> None:
    """Mark reviewed descriptions as approved; they are never overwritten afterwards."""
    if sum(1 for chosen in (bool(service), package is not None, all_drafts) if chosen) != 1:
        typer.echo(
            "APPROVE_INPUT_INVALID: choose exactly one of --service, --package or --all-drafts.",
            err=True,
        )
        raise typer.Exit(code=2)
    approved, missing = approve_docs(
        docs_dir, services=service or [], package=package, all_drafts=all_drafts
    )
    for name in approved:
        typer.echo(f"approved: {name}")
    for name in missing:
        typer.echo(f"no description file: {name}", err=True)
    typer.echo(f"Approved {len(approved)} description(s) in {docs_dir}.")
    if missing:
        raise typer.Exit(code=1)


@app.command()
def status(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    docs_dir: DocsDirOption = Path("service-docs"),
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    ] = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
    external_systems_file: ExternalSystemsOption = None,
    platform_services_file: PlatformServicesOption = None,
) -> None:
    """Report which services have no, draft, edited, approved or outdated descriptions."""
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    external_catalog = _load_external_systems_or_exit(external_systems_file)
    _use_platform_services_or_exit(platform_services_file)
    analysis = _analyze(packages_path, app_config, no_cache=no_analysis_cache)
    facts = compute_service_facts(analysis, external_catalog)
    # Only services with a description file need their facts hashed; the rest are "missing".
    described = {
        service.identity.full_name
        for service in analysis.services
        if doc_path(docs_dir, service.identity.package, service.identity.full_name).is_file()
    }
    hashes = current_facts_hashes(
        analysis, packages_path, app_config, external_catalog, facts=facts, only=described
    )
    states = collect_states(analysis, docs_dir, hashes)
    overviews = overview_states(analysis, docs_dir, facts)
    orphans = sorted(
        (
            doc.service
            for _path, doc in iter_docs(docs_dir)
            if doc.service not in states and doc.service not in overviews
        ),
        key=str.casefold,
    )
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "STATUS.md").write_text(
        render_status(states, orphans, overviews), encoding="utf-8"
    )
    totals: dict[DocState, int] = {}
    for _package, state in states.values():
        totals[state] = totals.get(state, 0) + 1
    typer.echo(f"Services: {len(states)}")
    for state in STATE_ORDER:
        typer.echo(f"- {state.value}: {totals.get(state, 0)}")
    overview_totals: dict[DocState, int] = {}
    for state in overviews.values():
        overview_totals[state] = overview_totals.get(state, 0) + 1
    typer.echo(f"Overviews (packages and server): {len(overviews)}")
    for state in STATE_ORDER:
        typer.echo(f"- {state.value}: {overview_totals.get(state, 0)}")
    if orphans:
        typer.echo(f"- description files without a service or package: {len(orphans)}")
    typer.echo(f"Wrote {docs_dir / 'STATUS.md'}.")


@app.command("export-comments")
def export_comments(
    docs_dir: DocsDirOption = Path("service-docs"),
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for <Package>.txt files.")
    ] = Path("designer-comments"),
    include_drafts: Annotated[
        bool, typer.Option("--include-drafts", help="Also export unapproved drafts.")
    ] = False,
) -> None:
    """Write Designer comment texts per package; packages themselves are never edited."""
    written = export_designer_comments(docs_dir, output, include_drafts=include_drafts)
    for package, count in written.items():
        typer.echo(f"{output / (package + '.txt')}: {count} comment(s)")
    typer.echo(f"Exported comments for {sum(written.values())} service(s).")


explorer_app = typer.Typer(
    help="Build and serve the interactive explorer: a static web app over the analysis.",
    no_args_is_help=True,
)
app.add_typer(explorer_app, name="explorer")

ExplorerOutputOption = Annotated[
    Path,
    typer.Option(
        "--output",
        "-o",
        help="Folder for the explorer (app and data). Must be outside the packages folder.",
    ),
]


DescriptionsOption = Annotated[
    str,
    typer.Option(
        "--descriptions",
        help="Which descriptions to show: approved (reviewed ones, also when the facts "
        "changed since), all (also unreviewed drafts) or none.",
    ),
]


def _descriptions_or_exit(value: str) -> DescriptionsShown:
    if value == "approved":
        return "approved"
    if value == "all":
        return "all"
    if value == "none":
        return "none"
    typer.echo("EXPLORER_INPUT_INVALID: --descriptions must be approved, all or none.", err=True)
    raise typer.Exit(code=2)


@explorer_app.command("build")
def explorer_build(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: ExplorerOutputOption,
    docs_dir: Annotated[
        Path | None,
        typer.Option("--docs-dir", help="Description files to show (see --descriptions)."),
    ] = None,
    descriptions: DescriptionsOption = "approved",
    dataset_kind: Annotated[
        str,
        typer.Option(
            "--dataset-kind",
            help="private (default; the app warns not to share it) or synthetic (demo data).",
        ),
    ] = "private",
    dataset_label: Annotated[
        str | None, typer.Option("--dataset-label", help="Short label shown in the app.")
    ] = None,
    config: ConfigOption = None,
    processes_file: ProcessesFileOption = None,
    include_package: IncludePackageOption = None,
    exclude_package: ExcludePackageOption = None,
    all_packages: AllPackagesOption = False,
    no_analysis_cache: NoAnalysisCacheOption = False,
    external_systems_file: ExternalSystemsOption = None,
    platform_services_file: PlatformServicesOption = None,
) -> None:
    """Write the explorer for a packages folder: the prebuilt app plus its data files."""
    shown = _descriptions_or_exit(descriptions)
    if dataset_kind not in ("private", "synthetic"):
        typer.echo("EXPLORER_INPUT_INVALID: --dataset-kind must be private or synthetic.", err=True)
        raise typer.Exit(code=2)
    _check_explorer_output_or_exit(output, packages_path)
    app_config = _with_package_selection(
        load_config(config), include_package, exclude_package, all_packages
    )
    external_catalog = _load_external_systems_or_exit(external_systems_file)
    _use_platform_services_or_exit(platform_services_file)
    analysis = _analyze(packages_path, app_config, processes_file, no_cache=no_analysis_cache)
    options = ExplorerOptions(
        dataset_kind="synthetic" if dataset_kind == "synthetic" else "private",
        dataset_label=dataset_label,
        descriptions=shown,
    )
    _write_explorer_or_exit(
        output, packages_path, analysis, app_config, external_catalog, docs_dir, options
    )


@explorer_app.command("demo")
def explorer_demo(
    output: ExplorerOutputOption,
    services: Annotated[
        int,
        typer.Option(
            "--services",
            min=0,
            max=20_000,
            help="Extra generated services on top of the small order-handling server.",
        ),
    ] = 40,
    packages_dir: Annotated[
        Path | None,
        typer.Option(
            "--packages-dir",
            help="Keep the generated synthetic packages in this (new) folder.",
        ),
    ] = None,
    descriptions: DescriptionsOption = "all",
) -> None:
    """Build the explorer from generated synthetic packages: safe to show and share."""
    if packages_dir is not None and packages_dir.exists() and any(packages_dir.iterdir()):
        typer.echo(
            "EXPLORER_INPUT_INVALID: --packages-dir must be a new or empty folder.", err=True
        )
        raise typer.Exit(code=2)
    shown = _descriptions_or_exit(descriptions)
    with tempfile.TemporaryDirectory(prefix="wm-doc-demo-") as temporary:
        root = packages_dir or Path(temporary) / "packages"
        root.mkdir(parents=True, exist_ok=True)
        _check_explorer_output_or_exit(output, root)
        count = write_demo_packages(root, services)
        typer.echo(f"Generated {count} synthetic services.")
        app_config = load_config(None)
        _use_platform_services_or_exit(None)
        analysis = _analyze(root, app_config, None, no_cache=True)
        docs_dir = Path(temporary) / "service-docs"
        described = write_demo_descriptions(docs_dir, analysis, root, app_config)
        typer.echo(f"Wrote {described} synthetic description files (every review state).")
        options = ExplorerOptions(dataset_kind="synthetic", descriptions=shown)
        _write_explorer_or_exit(
            output, root, analysis, app_config, EMPTY_CATALOG, docs_dir, options
        )


@explorer_app.command("serve")
def explorer_serve(
    folder: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    port: Annotated[int, typer.Option("--port", min=1, max=65_535)] = 8765,
    host: Annotated[
        str,
        typer.Option("--host", help="Address to listen on; the default is this computer only."),
    ] = "127.0.0.1",
) -> None:
    """Serve a built explorer folder over HTTP (browsers do not load it from file://)."""
    if not (folder / "index.html").is_file() or not (folder / "data" / "manifest.json").is_file():
        typer.echo(
            "EXPLORER_FOLDER_INVALID: not an explorer folder; run `wm-doc explorer build` first.",
            err=True,
        )
        raise typer.Exit(code=2)
    if not is_loopback(host):
        typer.echo(
            "Warning: listening on a non-loopback address shares the explorer with your network.",
            err=True,
        )
    try:
        server = make_server(folder, host, port)
    except OSError as exc:
        typer.echo(f"EXPLORER_SERVE_FAILED: could not listen on {host}:{port}.", err=True)
        raise typer.Exit(code=1) from exc
    shown = f"[{host}]" if ":" in host else host
    typer.echo(f"Explorer at http://{shown}:{port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _check_explorer_output_or_exit(output: Path, packages_root: Path) -> None:
    try:
        check_output_location(output, packages_root)
    except ExplorerOutputError as exc:
        typer.echo(f"{exc.code}: {exc.safe_message}", err=True)
        raise typer.Exit(code=2) from exc


def _write_explorer_or_exit(
    output: Path,
    packages_path: Path,
    analysis: AnalysisResult,
    app_config: AppConfig,
    external_catalog: ExternalSystemCatalog,
    docs_dir: Path | None,
    options: ExplorerOptions,
) -> None:
    started = time.monotonic()
    inputs = explorer_inputs(analysis, packages_path, app_config, external_catalog, docs_dir)
    try:
        bundle = build_bundle(inputs, options)
        report = write_explorer(output, bundle, packages_path)
    except (ExplorerOutputError, OutputCleanupError, IdCollisionError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    counts = bundle.manifest.counts
    typer.echo(
        f"Explorer data: {counts.services} services in {counts.packages} packages, "
        f"{report.data_files} files, {report.data_bytes / 1_000_000:.1f} MB "
        f"[{_duration(time.monotonic() - started)}]"
    )
    withheld = bundle.manifest.disclosure.withheld_strings
    if withheld:
        typer.echo(f"Withheld {withheld} text(s) that looked like secrets, paths or markup.")
    if not report.app_included:
        typer.echo(
            "Warning: this installation has no prebuilt explorer app; only data was written.",
            err=True,
        )
    typer.echo(f"Open it with: wm-doc explorer serve {output}")


def _service_graph_links(
    output: Path, graph_paths: dict[str, Path], assets: list[GraphAsset]
) -> dict[str, tuple[str, str]]:
    """service -> (image path, DOT path), relative to a service page, for rendered graphs."""
    by_dot = {asset.dot_path: asset for asset in assets}
    links: dict[str, tuple[str, str]] = {}
    for name, path in graph_paths.items():
        relative = path.resolve().relative_to(output.resolve()).as_posix()
        asset = by_dot.get(relative)
        if asset is None:
            continue
        image = asset.rendered_paths.get("svg") or asset.rendered_paths.get("png")
        if image:
            links[name] = (f"../{image}", f"../{relative}")
    return links


def _write_full_outputs(
    output: Path,
    analysis: AnalysisResult,
    render_graphs_mode: GraphRenderMode,
    graphviz_dot: Path | None,
    *,
    verbose: bool,
    docs_dir: Path | None = None,
    external_systems: ExternalSystemCatalog = EMPTY_CATALOG,
) -> tuple[str, list[GraphRenderResult]]:
    """Write the complete (unscoped) documentation set; return the report and failures."""
    output.mkdir(parents=True, exist_ok=True)
    try:
        _clean_generated_output(output)
    except OutputCleanupError as exc:
        typer.echo(f"Output cleanup failed: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc
    write_analysis_json(output / "analysis.json", analysis)
    services = [service for package in analysis.packages for service in package.services]
    documents = [document for package in analysis.packages for document in package.document_types]
    service_docs = load_service_docs(docs_dir, services) if docs_dir is not None else {}
    service_facts = compute_service_facts(analysis, external_systems)
    page_filenames = service_markdown_filenames(services)
    catalogue_path: str | None = None
    if docs_dir is not None:
        write_service_catalogue(
            output, services, service_docs, service_markdown_filenames(services)
        )
        catalogue_path = SERVICE_CATALOGUE
    document_paths = write_document_markdown(
        output,
        documents,
        analysis.document_reference_occurrences,
        analysis.document_dependencies,
        analysis.service_document_dependencies,
        analysis.extraction_policy,
        analysis.process_document_relationships,
        analysis.processes,
    )
    entrypoint_path = write_entrypoint_candidates_markdown(output, analysis)
    dot_path = write_dependency_dot(output, analysis)
    document_dot_path = write_document_dot(output, analysis)
    process_dot_paths = write_process_dots(output, analysis)
    # Per-service call graphs are only useful as images, so they are written when rendering
    # is requested; the default output stays DOT-only and unchanged.
    service_graph_paths: dict[str, Path] = {}
    if render_graphs_mode is not GraphRenderMode.NONE:
        service_graph_paths = write_service_graphs(
            output,
            services,
            service_facts,
            ServiceGraphContext(analysis, external_systems),
            page_filenames,
        )
    dot_paths = [dot_path, document_dot_path, *process_dot_paths, *service_graph_paths.values()]
    graph_assets = build_graph_assets(output, dot_paths)
    graph_results = render_graphs(
        output,
        graph_assets,
        render_graphs_mode,
        graphviz_dot=graphviz_dot,
        runner=GRAPHVIZ_RUNNER,
        timeout=GRAPH_RENDER_TIMEOUT_SECONDS,
    )
    graph_failures = graph_render_failures(graph_results)
    service_paths = write_service_markdown(
        output,
        services,
        analysis.process_service_memberships,
        analysis.processes,
        verbose=verbose,
        service_docs=service_docs,
        service_facts=service_facts,
        service_graphs=_service_graph_links(output, service_graph_paths, graph_assets),
    )
    graph_index_path = write_graph_index(output, graph_assets)
    write_analysis_limitations(output)
    write_artifact_inventory(output, analysis)
    write_platform_services(output, analysis)
    package_summaries = summarize_packages(analysis, service_facts)
    package_overviews = (
        package_overview_docs(docs_dir, package_summaries) if docs_dir is not None else {}
    )
    package_paths = write_package_markdown(
        output,
        package_summaries,
        overviews=package_overviews,
        docs_enabled=docs_dir is not None,
        purposes=service_purposes(analysis, service_docs),
        service_filenames=page_filenames,
    )
    server_doc = read_doc(overview_doc_path(docs_dir, None)) if docs_dir is not None else None
    index_path = write_documentation_index(
        output,
        analysis,
        graph_assets,
        catalogue_path=catalogue_path,
        packages_section=render_packages_index_section(
            package_summaries, package_overviews, docs_enabled=docs_dir is not None
        ),
        server_section=render_server_overview_section(server_doc) if server_doc else None,
    )
    process_paths = write_process_markdown(output, analysis, graph_assets)
    flow_count = sum(1 for service in services if service.service_type.value == "FLOW")
    java_count = sum(1 for service in services if service.service_type.value == "JAVA")
    opaque_count = sum(1 for service in services if service.service_type.value == "OPAQUE")
    metrics = analysis.metrics
    report = (
        f"Packages: {len(analysis.packages)} analysed, "
        f"{len(analysis.excluded_packages)} skipped (listed in artifacts.md)\n"
        "Analyzed services:\n"
        f"- FLOW: {flow_count}\n"
        f"- Java: {java_count}\n"
        f"- Opaque: {opaque_count}\n"
        f"- total: {len(services)}\n"
        "Analysis support status:\n"
        f"- full: {metrics.service_analysis_status_counts.get('FULL', 0)}\n"
        f"- partial: {metrics.service_analysis_status_counts.get('PARTIAL', 0)}\n"
        f"- opaque: {metrics.service_analysis_status_counts.get('OPAQUE', 0)}\n"
        "Opaque service descriptions:\n"
        f"- with source descriptions: {metrics.opaque_service_with_description_count}\n"
        f"- without source descriptions: {metrics.opaque_service_without_description_count}\n"
        "Service call occurrences:\n"
        f"- FLOW: {metrics.flow_call_occurrence_count}\n"
        f"- Java static: {metrics.java_static_call_occurrence_count}\n"
        f"- Java dynamic/partial: {metrics.java_dynamic_call_occurrence_count}\n"
        f"- total promoted calls: {metrics.total_call_occurrence_count}\n"
        "Resolved call targets by type:\n"
        f"- Opaque: {metrics.resolved_call_occurrence_target_type_counts.get('OPAQUE', 0)}\n"
        "Unique service dependencies:\n"
        f"- FLOW-derived: {metrics.flow_unique_dependency_count}\n"
        f"- Java-derived: {metrics.java_unique_dependency_count}\n"
        f"- total: {metrics.total_unique_dependency_count}\n"
        "Resolved unique dependency targets by type:\n"
        f"- Opaque: {metrics.resolved_unique_dependency_target_type_counts.get('OPAQUE', 0)}\n"
        "Processes:\n"
        f"- definitions: {metrics.process_definition_count}\n"
        f"- resolved entrypoints: {metrics.resolved_entrypoint_count}\n"
        f"- unresolved entrypoints: {metrics.unresolved_entrypoint_count}\n"
        f"- technical entrypoint candidates: {metrics.technical_entrypoint_candidate_count}\n"
        f"- service memberships: {metrics.process_service_membership_count}\n"
        f"- dependency edges: {metrics.process_dependency_edge_count}\n"
        f"- unresolved process calls: {metrics.process_unresolved_call_count}\n"
        f"- Processes with findings: {metrics.processes_with_findings_count}\n"
        "Wrote analysis.json, "
        f"{index_path.name}, "
        f"{len(service_paths)} service markdown file(s), "
        f"{len(package_paths)} package markdown file(s), "
        f"{len(document_paths)} document markdown file(s), "
        f"{len(process_paths)} process markdown file(s), "
        f"{entrypoint_path.name}, "
        f"{dot_path.parent.name}/{dot_path.name}, "
        f"{document_dot_path.parent.name}/{document_dot_path.name}, and "
        f"{len(process_dot_paths)} process DOT file(s).\n"
        "Graph publishing:\n"
        f"- DOT graphs generated: {len(dot_paths)}\n"
        f"- SVG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.SVG)}\n"
        f"- PNG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.PNG)}\n"
        f"- Graph render failures: {len(graph_failures)}\n"
        f"- Graph index generated: {'yes' if graph_index_path.exists() else 'no'}"
    )
    return report, graph_failures


def _write_scoped_outputs(
    output: Path,
    analysis: AnalysisResult,
    scope: ScopeResult,
    render_graphs_mode: GraphRenderMode,
    graphviz_dot: Path | None,
    *,
    verbose: bool = False,
) -> list[GraphRenderResult]:
    output.mkdir(parents=True, exist_ok=True)
    try:
        _clean_generated_output(output)
    except OutputCleanupError as exc:
        typer.echo(f"Output cleanup failed: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc

    write_analysis_json(output / "analysis.json", analysis)
    write_analysis_limitations(output)
    write_scope_json(output, scope)
    write_scope_markdown(output, scope)
    services = services_for_scope(analysis, scope)
    service_paths = write_scoped_service_markdown(
        output, analysis, scope, services, verbose=verbose
    )
    document_paths = write_scoped_document_markdown(output, analysis, scope)
    entrypoint_path = write_scoped_entrypoints_markdown(output, scope, analysis)
    dot_paths = [write_scope_dot(output, scope)]
    document_dot_path = write_scope_document_dot(output, scope)
    if document_dot_path is not None:
        dot_paths.append(document_dot_path)
    process_dot_path = write_scoped_process_dot(output, scope)
    if process_dot_path is not None:
        dot_paths.append(process_dot_path)
    graph_assets = build_graph_assets(output, dot_paths)
    graph_results = render_graphs(
        output,
        graph_assets,
        render_graphs_mode,
        graphviz_dot=graphviz_dot,
        runner=GRAPHVIZ_RUNNER,
        timeout=GRAPH_RENDER_TIMEOUT_SECONDS,
    )
    graph_failures = graph_render_failures(graph_results)
    graph_index_path = write_graph_index(output, graph_assets)
    index_path = write_scoped_index_markdown(output, scope, analysis, graph_assets)
    process_paths = write_scoped_process_markdown(output, scope, analysis, graph_assets)
    metrics = scope.metrics
    typer.echo(
        "Full snapshot technical metrics:\n"
        f"- services: {sum(len(package.services) for package in analysis.packages)}\n"
        f"- unique service dependencies: {analysis.metrics.total_unique_dependency_count}\n"
        f"- document types: {analysis.metrics.document_type_count}\n"
        f"- technical entrypoint candidates: "
        f"{analysis.metrics.technical_entrypoint_candidate_count}\n"
        "Focused publication metrics:\n"
        f"- selector type: {metrics.selector_type.value}\n"
        f"- selector value: {_safe_cli_value(metrics.selector_value)}\n"
        f"- dependency depth: {metrics.dependency_depth}\n"
        f"- roots resolved: {metrics.roots_resolved}\n"
        f"- services included: {metrics.services_included}\n"
        f"- root services included: {metrics.root_services_included}\n"
        f"- included resolved dependencies: {metrics.included_resolved_dependencies}\n"
        f"- boundary dependencies: {metrics.boundary_dependencies}\n"
        f"- depth-limit boundaries: "
        f"{metrics.boundary_counts_by_status.get('DEPTH_LIMIT', 0)}\n"
        f"- unresolved static boundaries: "
        f"{metrics.boundary_counts_by_status.get('UNRESOLVED', 0)}\n"
        f"- dynamic boundaries: {metrics.boundary_counts_by_status.get('DYNAMIC', 0)}\n"
        f"- external built-in boundaries: "
        f"{metrics.boundary_counts_by_status.get('EXTERNAL_BUILTIN', 0)}\n"
        f"- documents included: {metrics.documents_included}\n"
        f"- direct documents included: {metrics.direct_documents_included}\n"
        f"- transitive documents included: {metrics.transitive_documents_included}\n"
        f"- processes published: {metrics.processes_published}\n"
        f"- maximum reached depth: {metrics.maximum_reached_depth}\n"
        "Wrote full analysis.json plus focused publication files: "
        f"scope.json, scope.md, {index_path.name}, "
        f"{len(service_paths)} service markdown file(s), "
        f"{len(document_paths)} document markdown file(s), "
        f"{len(process_paths)} process markdown file(s), "
        f"{entrypoint_path.name}.\n"
        "Graph publishing:\n"
        f"- DOT graphs generated: {len(dot_paths)}\n"
        f"- SVG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.SVG)}\n"
        f"- PNG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.PNG)}\n"
        f"- Graph render failures: {len(graph_failures)}\n"
        f"- Graph index generated: {'yes' if graph_index_path.exists() else 'no'}"
    )
    return graph_failures


MAX_LISTED_GRAPH_FAILURES = 20


def _echo_graph_failures(graph_failures: list[GraphRenderResult]) -> None:
    typer.echo("Graph rendering failed:", err=True)
    # With per-service graphs a missing Graphviz fails thousands of renders; list a few.
    for failure in graph_failures[:MAX_LISTED_GRAPH_FAILURES]:
        typer.echo(
            "- "
            f"{failure.dot_path} {failure.requested_format.value}: "
            f"{failure.failure_reason or 'render failed'}",
            err=True,
        )
    hidden = len(graph_failures) - min(len(graph_failures), MAX_LISTED_GRAPH_FAILURES)
    if hidden:
        typer.echo(f"- ... and {hidden} more failed render(s)", err=True)


def _scope_request_from_cli(
    *,
    target_service: list[str] | None,
    target_namespace: list[str] | None,
    target_package: list[str] | None,
    target_process: list[str] | None,
    dependency_depth: str,
) -> ScopeRequest | None:
    selectors: list[tuple[ScopeSelectorType, str]] = []
    for selector_type, values, option_name in (
        (ScopeSelectorType.SERVICE, target_service, "--target-service"),
        (ScopeSelectorType.NAMESPACE, target_namespace, "--target-namespace"),
        (ScopeSelectorType.PACKAGE, target_package, "--target-package"),
        (ScopeSelectorType.PROCESS, target_process, "--target-process"),
    ):
        values = values or []
        if len(values) > 1:
            raise ScopeCliError(
                "SCOPE_SELECTOR_CONFLICT",
                f"{option_name} may be provided at most once in M8a v1.",
            )
        if values:
            selectors.append((selector_type, values[0].strip()))

    depth = _parse_dependency_depth(dependency_depth)
    if len(selectors) > 1:
        raise ScopeCliError(
            "SCOPE_SELECTOR_CONFLICT",
            "M8a v1 accepts exactly one focused publication selector per run.",
        )
    if not selectors:
        if depth is not None:
            raise ScopeCliError(
                "SCOPE_SELECTOR_CONFLICT",
                "--dependency-depth requires a focused publication selector.",
            )
        return None

    selector_type, selector_value = selectors[0]
    request = ScopeRequest(selector_type, selector_value, depth)
    malformed = validate_scope_request(request)
    if malformed is not None:
        raise ScopeCliError(malformed.code, malformed.message)
    return request


def _parse_dependency_depth(value: str) -> int | None:
    normalized = value.strip().casefold()
    if normalized == "all":
        return None
    try:
        parsed = int(normalized, 10)
    except ValueError as exc:
        raise ScopeCliError(
            "SCOPE_TARGET_MALFORMED",
            "--dependency-depth must be 0, a positive integer, or all.",
        ) from exc
    if parsed < 0:
        raise ScopeCliError(
            "SCOPE_TARGET_MALFORMED",
            "--dependency-depth must be 0, a positive integer, or all.",
        )
    return parsed


def _process_catalog_available(packages_path: Path, processes_file: Path | None) -> bool:
    if processes_file is not None:
        return processes_file.exists()
    return (packages_path / "processes.yml").exists()


def _safe_cli_value(value: str) -> str:
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 120:
        return cleaned[:120] + "..."
    return cleaned


class ScopeCliError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(f"{code}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


class BusinessContextCliError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(f"{code}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


def _clean_generated_output(output: Path) -> None:
    for filename in MANAGED_ROOT_FILES:
        _remove_managed_path(output, Path(filename))
    for directory in MANAGED_ROOT_DIRS:
        _remove_managed_path(output, Path(directory))
