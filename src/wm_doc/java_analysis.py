from __future__ import annotations

import base64
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from wm_doc.ir import (
    AnalysisFinding,
    ArtifactCandidate,
    CallOccurrence,
    CallType,
    DependencyKind,
    FindingSeverity,
    FindingStatus,
    InterpretationConfidence,
    JavaCursorScope,
    JavaFragmentKind,
    JavaImport,
    JavaImportProvenance,
    JavaInvocationOccurrence,
    JavaInvocationTargetStatus,
    JavaMethodRange,
    JavaParserMode,
    JavaPipelineAccess,
    JavaPipelineAccessKind,
    JavaReferenceKind,
    JavaServiceAnalysis,
    JavaSourceReference,
    JavaSourceSet,
    JavaSourceStatus,
    JavaTypeCategory,
    JavaTypeReference,
    ServiceIdentity,
    ServiceSignature,
    SourceReference,
    stable_relative_path,
)
from wm_doc.values import parse_values_file
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file

JAVA_INVOKE_APIS = {"doInvoke"}
PIPELINE_READ_METHODS = {"getString", "get", "getIData", "getIDataArray"}
PIPELINE_WRITE_METHODS = {"put"}
PIPELINE_REMOVE_METHODS = {"remove"}
JAVA_MODIFIERS = {
    "abstract",
    "final",
    "native",
    "private",
    "protected",
    "public",
    "static",
    "strictfp",
    "synchronized",
}


@dataclass(frozen=True)
class JavaToken:
    kind: str
    value: str
    offset: int
    line: int
    column: int
    end_line: int
    end_column: int
    ordinal: int


@dataclass(frozen=True)
class JavaImportDecl:
    declaration: str
    imported_name: str
    is_static: bool
    is_wildcard: bool
    order: int
    source: SourceReference


@dataclass(frozen=True)
class JavaMethodCandidate:
    name: str
    tokens: list[JavaToken]
    declaration_tokens: list[JavaToken]
    body_tokens: list[JavaToken]
    body_open: JavaToken
    body_close: JavaToken
    static: bool
    return_type: str | None
    parameter_types: list[str]
    signature_supported: bool
    unsupported_reasons: tuple[str, ...]


@dataclass(frozen=True)
class JavaParseIssue:
    token: JavaToken | None
    message: str


@dataclass(frozen=True)
class JavaMethodSearchResult:
    candidates: list[JavaMethodCandidate]
    parse_issues: list[JavaParseIssue]


@dataclass(frozen=True)
class JavaClassModel:
    package_name: str | None
    class_name: str | None
    imports: list[JavaImportDecl]
    tokens: list[JavaToken]
    class_open: int | None
    class_close: int | None
    partial_parse_issue: JavaParseIssue | None


@dataclass(frozen=True)
class JavaMethodInput:
    tokens: list[JavaToken]
    primary_path: Path
    primary_artifact_type: str
    primary_class_name: str | None
    primary_method_name: str | None
    corroborating_tokens: list[JavaToken]
    corroborating_path: Path | None


@dataclass(frozen=True)
class NestedExecutableRange:
    kind: str
    start: int
    end: int
    token: JavaToken
    skipped_api_count: int


def analyze_java_service(
    *,
    scan_root: Path,
    package_name: str,
    artifact: ArtifactCandidate,
    identity: ServiceIdentity,
    signature: ServiceSignature,
    id_factory: Any,
) -> tuple[JavaServiceAnalysis, list[CallOccurrence]]:
    service_dir = scan_root / artifact.relative_path
    node_path = service_dir / "node.ndf"
    fragment_path = service_dir / "java.frag"
    package_root = scan_root / package_name
    source_root = package_root / "code" / "source"
    expected_package, expected_class = _expected_source_identity(identity.namespace)
    direct_source = (
        source_root / Path(*identity.namespace.split(".")).with_suffix(".java")
        if identity.namespace
        else None
    )
    findings: list[AnalysisFinding] = []
    source_path = _find_source_candidate(
        direct_source, source_root, expected_package, expected_class
    )
    helper_sources = _helper_sources_for_service(source_root, expected_package, expected_class)

    fragment_body: str | None = None
    fragment_tokens: list[JavaToken] = []
    fragment_kind = JavaFragmentKind.UNKNOWN_FRAGMENT
    if fragment_path.exists():
        try:
            fragment_body = _decode_java_fragment(fragment_path)
            fragment_tokens = tokenize_java(fragment_body)
            fragment_kind = _fragment_kind(fragment_tokens)
        except (XmlParseError, XmlSecurityError, ValueError):
            findings.append(
                _finding(
                    "JAVA_FRAGMENT_MALFORMED",
                    "Java fragment XML, base64, or body could not be parsed safely.",
                    fragment_path,
                    scan_root,
                    "java_frag",
                    FindingSeverity.WARNING,
                )
            )
    source_model: JavaClassModel | None = None
    if source_path is not None and source_path.exists():
        source_model = parse_compilation_unit(
            _read_java_source(source_path), source_path, scan_root
        )

    status = JavaSourceStatus.FRAGMENT_ONLY
    parser_mode = JavaParserMode.FRAGMENT_FALLBACK
    confidence = InterpretationConfidence.RAW_ONLY
    method: JavaMethodCandidate | None = None
    token_match: bool | None = None
    primary_source: SourceReference | None = None
    corroborating_source: SourceReference | None = None
    method_input: JavaMethodInput | None = None

    if source_model is None:
        if not fragment_path.exists():
            findings.append(
                _finding(
                    "JAVA_SOURCE_MISSING",
                    "Complete generated Java source is missing and no java.frag fallback exists.",
                    node_path,
                    scan_root,
                    "java_service",
                    FindingSeverity.WARNING,
                )
            )
            parser_mode = JavaParserMode.METADATA_ONLY
        elif fragment_path.exists():
            findings.append(
                _finding(
                    "JAVA_SOURCE_MISSING",
                    "Complete generated Java source is missing; java.frag fallback is used.",
                    fragment_path,
                    scan_root,
                    "java_frag",
                    FindingSeverity.INFO,
                )
            )
    else:
        assert source_path is not None
        identity_ok = (
            source_model.package_name == expected_package
            and source_model.class_name == expected_class
        )
        if source_model.partial_parse_issue is not None:
            status = JavaSourceStatus.SOURCE_PARTIAL_PARSE
            findings.append(
                _partial_parse_finding(
                    source_model.partial_parse_issue,
                    source_path,
                    scan_root,
                    "Complete Java source structure could not be parsed safely; "
                    "java.frag fallback is used when available.",
                )
            )
        elif not identity_ok:
            status = JavaSourceStatus.SOURCE_IDENTITY_MISMATCH
            findings.append(
                _finding(
                    "JAVA_SOURCE_IDENTITY_MISMATCH",
                    "Complete Java source package or class identity does not match "
                    "service namespace.",
                    source_path,
                    scan_root,
                    "java_source",
                    FindingSeverity.WARNING,
                )
            )
        else:
            method_search = _find_service_method_candidates(source_model, identity.name)
            candidates = method_search.candidates
            method = _select_method(candidates)
            compatible_candidates = [
                candidate for candidate in candidates if candidate.signature_supported
            ]
            if method_search.parse_issues:
                status = JavaSourceStatus.SOURCE_PARTIAL_PARSE
                findings.append(
                    _partial_parse_finding(
                        method_search.parse_issues[0],
                        source_path,
                        scan_root,
                        "Complete Java source method structure could not be parsed safely; "
                        "java.frag fallback is used when available.",
                    )
                )
                method = None
            elif method is None and len(compatible_candidates) > 1:
                status = JavaSourceStatus.SOURCE_METHOD_AMBIGUOUS
                findings.append(
                    _finding(
                        "JAVA_SOURCE_METHOD_AMBIGUOUS",
                        "Multiple compatible Java Service methods match the service name.",
                        source_path,
                        scan_root,
                        "java_source",
                        FindingSeverity.WARNING,
                    )
                )
            elif method is None and candidates:
                status = JavaSourceStatus.SOURCE_METHOD_NOT_FOUND
                findings.append(
                    _unsupported_signature_finding(
                        identity.full_name, candidates[0], source_path, scan_root
                    )
                )
            elif method is None:
                status = JavaSourceStatus.SOURCE_METHOD_NOT_FOUND
                findings.append(
                    _finding(
                        "JAVA_SOURCE_METHOD_NOT_FOUND",
                        "Complete Java source exists but no matching service method was found.",
                        source_path,
                        scan_root,
                        "java_source",
                        FindingSeverity.WARNING,
                    )
                )
            elif not fragment_path.exists():
                status = JavaSourceStatus.SOURCE_ONLY
                parser_mode = JavaParserMode.COMPLETE_SOURCE
                confidence = InterpretationConfidence.PARTIALLY_INTERPRETED
                findings.append(
                    _finding(
                        "JAVA_FRAGMENT_MISSING",
                        "Complete Java source is available but java.frag is missing.",
                        source_path,
                        scan_root,
                        "java_source",
                        FindingSeverity.INFO,
                    )
                )
            elif _token_values(method.body_tokens) == _token_values(fragment_tokens):
                status = JavaSourceStatus.SOURCE_AND_FRAGMENT_MATCH
                parser_mode = JavaParserMode.COMPLETE_SOURCE
                confidence = InterpretationConfidence.CONFIRMED
                token_match = True
            else:
                status = JavaSourceStatus.SOURCE_FRAGMENT_MISMATCH
                token_match = False
                findings.append(
                    _finding(
                        "JAVA_SOURCE_FRAGMENT_MISMATCH",
                        "Complete Java source method and java.frag differ after token "
                        "normalization.",
                        source_path,
                        scan_root,
                        "java_source",
                        FindingSeverity.WARNING,
                    )
                )

    if status in {
        JavaSourceStatus.SOURCE_AND_FRAGMENT_MATCH,
        JavaSourceStatus.SOURCE_ONLY,
    } and method is not None and source_path is not None:
        primary_source = _method_source(method, source_path, scan_root, expected_class)
        if fragment_path.exists() and fragment_tokens:
            corroborating_source = _fragment_source(fragment_path, scan_root, fragment_tokens[0])
        method_input = JavaMethodInput(
            tokens=method.body_tokens,
            primary_path=source_path,
            primary_artifact_type="java_source",
            primary_class_name=expected_class,
            primary_method_name=identity.name,
            corroborating_tokens=fragment_tokens if token_match else [],
            corroborating_path=fragment_path if token_match else None,
        )
    elif fragment_body is not None and fragment_path.exists():
        primary_source = _fragment_source(
            fragment_path, scan_root, fragment_tokens[0] if fragment_tokens else None
        )
        if method is not None and source_path is not None:
            corroborating_source = _method_source(method, source_path, scan_root, expected_class)
        method_input = JavaMethodInput(
            tokens=fragment_tokens,
            primary_path=fragment_path,
            primary_artifact_type="java_frag_body",
            primary_class_name=expected_class,
            primary_method_name=identity.name,
            corroborating_tokens=[],
            corroborating_path=None,
        )
        parser_mode = JavaParserMode.FRAGMENT_FALLBACK
    else:
        parser_mode = JavaParserMode.METADATA_ONLY

    method_range = (
        JavaMethodRange(
            start_line=method.body_open.line,
            start_column=method.body_open.column,
            end_line=method.body_close.end_line,
            end_column=method.body_close.end_column,
            source=_method_source(method, source_path, scan_root, expected_class),
        )
        if method is not None and source_path is not None
        else None
    )
    source_set = JavaSourceSet(
        status=status,
        node_path=stable_relative_path(node_path, scan_root),
        fragment_path=stable_relative_path(fragment_path, scan_root)
        if fragment_path.exists()
        else None,
        complete_source_path=stable_relative_path(source_path, scan_root)
        if source_path is not None and source_path.exists()
        else None,
        related_helper_sources=[stable_relative_path(path, scan_root) for path in helper_sources],
        matched_class=expected_class if method is not None else None,
        matched_method=identity.name if method is not None else None,
        method_range=method_range,
        fragment_kind=fragment_kind,
        token_match=token_match,
        parser_mode=parser_mode,
        confidence=confidence,
        primary_source=primary_source,
        corroborating_source=corroborating_source,
    )

    imports = _java_imports(
        source_model,
        source_path,
        service_dir,
        source_root,
        scan_root,
        identity.full_name,
        id_factory,
        findings,
    )
    referenced_types: list[JavaTypeReference] = []
    pipeline_accesses: list[JavaPipelineAccess] = []
    invocations: list[JavaInvocationOccurrence] = []
    java_calls: list[CallOccurrence] = []
    if method_input is not None:
        nested_ranges = _nested_executable_ranges(method_input.tokens)
        direct_token_indexes = _direct_token_indexes(method_input.tokens, nested_ranges)
        findings.extend(
            _nested_executable_findings(
                method_input, identity.full_name, nested_ranges, scan_root
            )
        )
        referenced_types = _referenced_types(
            method_input,
            imports,
            identity.full_name,
            id_factory,
            scan_root,
            direct_token_indexes,
        )
        pipeline_accesses = _pipeline_accesses(
            method_input,
            identity.full_name,
            id_factory,
            scan_root,
            findings,
            direct_token_indexes,
        )
        invocations, java_calls = _java_invocations(
            method_input,
            identity.full_name,
            id_factory,
            scan_root,
            findings,
            direct_token_indexes,
        )

    analysis_id = id_factory.make(
        "java", artifact.source, identity.package, "java_service", identity.full_name
    )
    metrics = _java_metrics(
        source_set, pipeline_accesses, invocations, java_calls
    )
    return (
        JavaServiceAnalysis(
            id=analysis_id,
            identity=identity,
            source_set=source_set,
            signature=signature,
            imports=imports,
            referenced_types=referenced_types,
            pipeline_accesses=pipeline_accesses,
            invocation_occurrences=invocations,
            findings=sorted(findings, key=lambda finding: (finding.source.path, finding.code)),
            metrics=metrics,
        ),
        java_calls,
    )


def tokenize_java(source: str) -> list[JavaToken]:
    tokens: list[JavaToken] = []
    index = 0
    line = 1
    column = 1
    ordinal = 1
    length = len(source)

    def advance(text: str) -> tuple[int, int]:
        nonlocal line, column
        for char in text:
            if char == "\n":
                line += 1
                column = 1
            else:
                column += 1
        return line, column

    while index < length:
        char = source[index]
        if char.isspace():
            advance(char)
            index += 1
            continue
        if source.startswith("//", index):
            while index < length and source[index] != "\n":
                advance(source[index])
                index += 1
            continue
        if source.startswith("/*", index):
            advance("/*")
            index += 2
            while index + 1 < length and not source.startswith("*/", index):
                advance(source[index])
                index += 1
            if index + 1 < length:
                advance("*/")
                index += 2
            continue

        start_offset = index
        start_line = line
        start_column = column
        if source.startswith('"""', index):
            value, index = _consume_text_block(source, index)
            end_line, end_column = advance(value)
            tokens.append(
                JavaToken(
                    "literal",
                    value,
                    start_offset,
                    start_line,
                    start_column,
                    end_line,
                    end_column,
                    ordinal,
                )
            )
            ordinal += 1
            continue
        if char in {'"', "'"}:
            value, index = _consume_quoted(source, index)
            end_line, end_column = advance(value)
            tokens.append(
                JavaToken(
                    "literal",
                    value,
                    start_offset,
                    start_line,
                    start_column,
                    end_line,
                    end_column,
                    ordinal,
                )
            )
            ordinal += 1
            continue
        if char.isalpha() or char in {"_", "$"}:
            value = char
            index += 1
            while index < length and (source[index].isalnum() or source[index] in {"_", "$"}):
                value += source[index]
                index += 1
            end_line, end_column = advance(value)
            tokens.append(
                JavaToken(
                    "id",
                    value,
                    start_offset,
                    start_line,
                    start_column,
                    end_line,
                    end_column,
                    ordinal,
                )
            )
            ordinal += 1
            continue
        if char.isdigit():
            value = char
            index += 1
            while index < length and (
                source[index].isalnum() or source[index] in {"_", ".", "x", "X"}
            ):
                value += source[index]
                index += 1
            end_line, end_column = advance(value)
            tokens.append(
                JavaToken(
                    "number",
                    value,
                    start_offset,
                    start_line,
                    start_column,
                    end_line,
                    end_column,
                    ordinal,
                )
            )
            ordinal += 1
            continue

        value = _operator_at(source, index)
        index += len(value)
        end_line, end_column = advance(value)
        tokens.append(
            JavaToken(
                "symbol",
                value,
                start_offset,
                start_line,
                start_column,
                end_line,
                end_column,
                ordinal,
            )
        )
        ordinal += 1
    return tokens


def parse_compilation_unit(source: str, source_path: Path, scan_root: Path) -> JavaClassModel:
    tokens = tokenize_java(source)
    package_name = _package_name(tokens)
    imports = _source_imports(tokens, source_path, scan_root)
    class_name, class_open, class_close = _top_level_class(tokens)
    partial_parse_issue = _compilation_unit_parse_issue(tokens, class_open, class_close)
    return JavaClassModel(
        package_name=package_name,
        class_name=class_name,
        imports=imports,
        tokens=tokens,
        class_open=class_open,
        class_close=class_close,
        partial_parse_issue=partial_parse_issue,
    )


def find_service_methods(model: JavaClassModel, method_name: str) -> list[JavaMethodCandidate]:
    return _find_service_method_candidates(model, method_name).candidates


def _find_service_method_candidates(
    model: JavaClassModel, method_name: str
) -> JavaMethodSearchResult:
    if model.class_open is None or model.class_close is None:
        return JavaMethodSearchResult(candidates=[], parse_issues=[])
    depths = _brace_depths(model.tokens)
    candidates: list[JavaMethodCandidate] = []
    parse_issues: list[JavaParseIssue] = []
    index = model.class_open + 1
    while index < model.class_close:
        token = model.tokens[index]
        if (
            token.value == method_name
            and depths[index] == 1
            and _token_value(model.tokens, index - 1) != "."
            and _token_value(model.tokens, index + 1) == "("
        ):
            paren_end = _matching(model.tokens, index + 1, "(", ")")
            if paren_end is None:
                parse_issues.append(
                    JavaParseIssue(
                        token=token,
                        message=(
                            "Matching service method declaration has unbalanced parentheses."
                        ),
                    )
                )
                index += 1
                continue
            body_open = _method_body_open(model.tokens, paren_end + 1)
            if body_open is None:
                parse_issues.append(
                    JavaParseIssue(
                        token=token,
                        message="Matching service method declaration has no parseable body.",
                    )
                )
                index = paren_end + 1
                continue
            body_close = _matching(model.tokens, body_open, "{", "}")
            if body_close is None:
                parse_issues.append(
                    JavaParseIssue(
                        token=model.tokens[body_open],
                        message="Matching service method body has unbalanced braces.",
                    )
                )
                index = body_open + 1
                continue
            declaration_start = _declaration_start(model.tokens, index)
            declaration_tokens = model.tokens[declaration_start:index]
            parameters = _parameter_types(model.tokens[index + 2 : paren_end])
            static = any(token.value == "static" for token in declaration_tokens)
            return_type = _return_type(declaration_tokens)
            unsupported_reasons = _method_signature_unsupported_reasons(
                static, return_type, parameters
            )
            candidates.append(
                JavaMethodCandidate(
                    name=method_name,
                    tokens=model.tokens[declaration_start : body_close + 1],
                    declaration_tokens=declaration_tokens,
                    body_tokens=model.tokens[body_open + 1 : body_close],
                    body_open=model.tokens[body_open],
                    body_close=model.tokens[body_close],
                    static=static,
                    return_type=return_type,
                    parameter_types=parameters,
                    signature_supported=not unsupported_reasons,
                    unsupported_reasons=tuple(unsupported_reasons),
                )
            )
            index = body_close + 1
            continue
        index += 1
    return JavaMethodSearchResult(candidates=candidates, parse_issues=parse_issues)


def _select_method(candidates: list[JavaMethodCandidate]) -> JavaMethodCandidate | None:
    supported = [candidate for candidate in candidates if candidate.signature_supported]
    if not supported:
        return None
    if len(supported) == 1:
        return supported[0]
    return None


def _method_signature_unsupported_reasons(
    static: bool, return_type: str | None, parameter_types: list[str]
) -> list[str]:
    reasons: list[str] = []
    if not static:
        reasons.append("missing static modifier")
    if return_type != "void":
        reasons.append(f"return type is {return_type or 'unknown'}, not void")
    if len(parameter_types) != 1:
        reasons.append(f"parameter count is {len(parameter_types)}, not 1")
    elif parameter_types[0] not in {"IData", "com.wm.data.IData"}:
        reasons.append(f"parameter type is {parameter_types[0]}, not IData")
    return reasons


def _decode_java_fragment(path: Path) -> str:
    root = parse_xml_file(path)
    if root.tag != "Values":
        raise ValueError("java.frag root is not Values")
    body = None
    for child in root:
        if isinstance(child.tag, str) and child.tag == "value" and child.get("name") == "body":
            body = child.text or ""
            break
    if body is None:
        raise ValueError("java.frag is missing body")
    decoded = base64.b64decode("".join(body.split()), validate=True)
    return decoded.decode("utf-8")


def _fragment_kind(tokens: list[JavaToken]) -> JavaFragmentKind:
    values = {token.value for token in tokens}
    if "package" in values or "import" in values:
        return JavaFragmentKind.COMPLETE_COMPILATION_UNIT
    if "class" in values:
        return JavaFragmentKind.CLASS_FRAGMENT
    if any(token.value == "void" for token in tokens) and any(
        token.value == "(" for token in tokens
    ):
        return JavaFragmentKind.METHOD_FRAGMENT
    if tokens:
        return JavaFragmentKind.METHOD_BODY
    return JavaFragmentKind.UNKNOWN_FRAGMENT


def _find_source_candidate(
    direct_source: Path | None, source_root: Path, expected_package: str, expected_class: str
) -> Path | None:
    if direct_source is not None and direct_source.exists():
        return direct_source
    if not source_root.exists():
        return direct_source
    matches = sorted(source_root.rglob(f"{expected_class}.java"), key=lambda item: item.as_posix())
    for candidate in matches:
        model = parse_compilation_unit(_read_java_source(candidate), candidate, source_root.parent)
        if model.package_name == expected_package and model.class_name == expected_class:
            return candidate
    return direct_source


def _expected_source_identity(namespace: str) -> tuple[str, str]:
    if "." not in namespace:
        return "", namespace
    package, class_name = namespace.rsplit(".", 1)
    return package, class_name


def _read_java_source(path: Path) -> str:
    return path.read_text(encoding="latin-1")


def _helper_sources_for_service(
    source_root: Path, expected_package: str, expected_class: str
) -> list[Path]:
    del expected_class
    if not source_root.exists():
        return []
    expected_package_dir = source_root / Path(*expected_package.split("."))
    helpers = [
        path
        for path in sorted(source_root.rglob("*.java"), key=lambda item: item.as_posix())
        if expected_package_dir not in [path, *path.parents]
    ]
    return helpers


def _java_imports(
    source_model: JavaClassModel | None,
    source_path: Path | None,
    service_dir: Path,
    source_root: Path,
    scan_root: Path,
    service_name: str,
    id_factory: Any,
    findings: list[AnalysisFinding],
) -> list[JavaImport]:
    source_imports = source_model.imports if source_model is not None else []
    metadata_imports = _metadata_imports(service_dir, scan_root)
    source_by_decl = {item.declaration: item for item in source_imports}
    metadata_by_decl = {item.declaration: item for item in metadata_imports}
    if source_by_decl and metadata_by_decl and set(source_by_decl) != set(metadata_by_decl):
        findings.append(
            _finding(
                "JAVA_IMPORT_SOURCE_MISMATCH",
                "Complete-source imports and node.idf import metadata differ.",
                source_path or service_dir,
                scan_root,
                "java_import",
                FindingSeverity.INFO,
            )
        )

    records: list[JavaImport] = []
    seen: set[str] = set()
    order = 1
    for declaration in sorted(set(source_by_decl) | set(metadata_by_decl), key=str.casefold):
        source_decl = source_by_decl.get(declaration)
        metadata_decl = metadata_by_decl.get(declaration)
        provenance = (
            JavaImportProvenance.BOTH
            if source_decl is not None and metadata_decl is not None
            else JavaImportProvenance.COMPLETE_SOURCE
            if source_decl is not None
            else JavaImportProvenance.NODE_IDF
        )
        selected = source_decl or metadata_decl
        if selected is None or declaration in seen:
            continue
        seen.add(declaration)
        records.append(
            JavaImport(
                id=id_factory.make(
                    "javaimport", selected.source, service_name, "import", order, declaration
                ),
                service=service_name,
                declaration=declaration,
                is_static=selected.is_static,
                is_wildcard=selected.is_wildcard,
                imported_name=selected.imported_name,
                declaration_order=order,
                provenance=provenance,
                category=_type_category(selected.imported_name, source_root),
                source=selected.source,
            )
        )
        order += 1
    return sorted(records, key=lambda item: (item.declaration_order, item.declaration.casefold()))


def _metadata_imports(service_dir: Path, scan_root: Path) -> list[JavaImportDecl]:
    node_idf = service_dir.parent / "node.idf"
    if not node_idf.exists():
        return []
    try:
        values = parse_values_file(node_idf)
    except (XmlParseError, XmlSecurityError):
        return []
    raw = values.get("imports")
    imports = raw if isinstance(raw, list) else []
    source = SourceReference(
        path=stable_relative_path(node_idf, scan_root), artifact_type="java_import_metadata"
    )
    return [
        JavaImportDecl(
            declaration=str(value),
            imported_name=str(value),
            is_static=False,
            is_wildcard=str(value).endswith(".*"),
            order=index,
            source=source,
        )
        for index, value in enumerate(imports, start=1)
        if isinstance(value, str)
    ]


def _referenced_types(
    method_input: JavaMethodInput,
    imports: list[JavaImport],
    service_name: str,
    id_factory: Any,
    scan_root: Path,
    direct_token_indexes: set[int],
) -> list[JavaTypeReference]:
    explicit = {
        item.imported_name.rsplit(".", 1)[-1]: item
        for item in imports
        if not item.is_wildcard and "." in item.imported_name
    }
    references: list[JavaTypeReference] = []
    seen: set[str] = set()
    for index, token in enumerate(method_input.tokens, start=1):
        if index not in direct_token_indexes:
            continue
        imported = explicit.get(token.value)
        if imported is None or token.value in seen:
            continue
        seen.add(token.value)
        source = _java_source_reference(method_input, token, index, scan_root)
        references.append(
            JavaTypeReference(
                id=id_factory.make(
                    "javatype",
                    source.primary,
                    service_name,
                    "type",
                    imported.imported_name,
                    index,
                ),
                service=service_name,
                reference_kind=JavaReferenceKind.REFERENCED_TYPE,
                type_name=token.value,
                resolved_import=imported.imported_name,
                category=imported.category,
                token_ordinal=index,
                source=source,
            )
        )
    return sorted(references, key=lambda item: (item.type_name.casefold(), item.token_ordinal))


def _direct_token_indexes(
    tokens: list[JavaToken], nested_ranges: list[NestedExecutableRange]
) -> set[int]:
    skipped: set[int] = set()
    for nested_range in nested_ranges:
        skipped.update(range(nested_range.start + 1, nested_range.end + 2))
    return {index for index in range(1, len(tokens) + 1) if index not in skipped}


def _nested_executable_ranges(tokens: list[JavaToken]) -> list[NestedExecutableRange]:
    ranges: list[NestedExecutableRange] = []
    for index, token in enumerate(tokens):
        if token.value == "class":
            open_index = _local_class_open(tokens, index)
            if open_index is None:
                continue
            close_index = _matching(tokens, open_index, "{", "}")
            if close_index is not None:
                ranges.append(
                    _nested_range(tokens, "LOCAL_CLASS", open_index, close_index, token)
                )
            continue
        if token.value == "new":
            open_index = _anonymous_class_open(tokens, index)
            if open_index is None:
                continue
            close_index = _matching(tokens, open_index, "{", "}")
            if close_index is not None:
                ranges.append(
                    _nested_range(tokens, "ANONYMOUS_CLASS", open_index, close_index, token)
                )
            continue
        if token.value != "->":
            continue
        if _token_value(tokens, index + 1) == "{":
            close_index = _matching(tokens, index + 1, "{", "}")
            if close_index is not None:
                ranges.append(_nested_range(tokens, "LAMBDA", index + 1, close_index, token))
            continue
        end_index = _lambda_expression_end(tokens, index + 1)
        if end_index is not None and end_index >= index + 1:
            ranges.append(_nested_range(tokens, "LAMBDA", index + 1, end_index, token))
    return _dedupe_nested_ranges(ranges)


def _nested_range(
    tokens: list[JavaToken], kind: str, start: int, end: int, token: JavaToken
) -> NestedExecutableRange:
    return NestedExecutableRange(
        kind=kind,
        start=start,
        end=end,
        token=token,
        skipped_api_count=_supported_api_site_count(tokens, start, end),
    )


def _dedupe_nested_ranges(
    ranges: list[NestedExecutableRange],
) -> list[NestedExecutableRange]:
    unique: dict[tuple[str, int, int], NestedExecutableRange] = {}
    for nested_range in ranges:
        if nested_range.skipped_api_count == 0:
            continue
        unique[(nested_range.kind, nested_range.start, nested_range.end)] = nested_range
    return sorted(unique.values(), key=lambda item: (item.start, item.end, item.kind))


def _nested_executable_findings(
    method_input: JavaMethodInput,
    service_name: str,
    nested_ranges: list[NestedExecutableRange],
    scan_root: Path,
) -> list[AnalysisFinding]:
    findings: list[AnalysisFinding] = []
    for nested_range in nested_ranges:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="JAVA_NESTED_EXECUTABLE_BODY_SKIPPED",
                message=(
                    f"M4a does not promote {nested_range.kind} nested executable body "
                    f"API sites as direct Java Service evidence for {service_name}; "
                    f"skipped {nested_range.skipped_api_count} supported-looking site(s). "
                    "This does not imply the nested code never executes."
                ),
                source=_java_source_reference(
                    method_input,
                    nested_range.token,
                    nested_range.token.ordinal,
                    scan_root,
                ).primary,
                severity=FindingSeverity.INFO,
                confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
            )
        )
    return findings


def _local_class_open(tokens: list[JavaToken], class_index: int) -> int | None:
    if _token_value(tokens, class_index - 1) == ".":
        return None
    name = _token(tokens, class_index + 1)
    if name is None or name.kind != "id":
        return None
    index = class_index + 2
    while index < len(tokens):
        value = tokens[index].value
        if value == "{":
            return index
        if value == ";":
            return None
        index += 1
    return None


def _anonymous_class_open(tokens: list[JavaToken], new_index: int) -> int | None:
    index = new_index + 1
    while index < len(tokens):
        value = tokens[index].value
        if value in {";", ",", ")", "}", ":", "->", "="}:
            return None
        if value == "[":
            return None
        if value == "{":
            return None
        if value == "(":
            close_index = _matching(tokens, index, "(", ")")
            if close_index is None:
                return None
            next_index = close_index + 1
            return next_index if _token_value(tokens, next_index) == "{" else None
        index += 1
    return None


def _lambda_expression_end(tokens: list[JavaToken], start: int) -> int | None:
    parens = brackets = braces = 0
    index = start
    while index < len(tokens):
        value = tokens[index].value
        if value == "(":
            parens += 1
        elif value == ")":
            if parens == 0:
                return index - 1
            parens -= 1
        elif value == "[":
            brackets += 1
        elif value == "]":
            if brackets == 0:
                return index - 1
            brackets -= 1
        elif value == "{":
            braces += 1
        elif value == "}":
            if braces == 0:
                return index - 1
            braces -= 1
        elif value in {";", ","} and parens == brackets == braces == 0:
            return index - 1
        index += 1
    return len(tokens) - 1 if start < len(tokens) else None


def _supported_api_site_count(tokens: list[JavaToken], start: int, end: int) -> int:
    count = 0
    for index in range(start, end + 1):
        if (
            _pipeline_api_method_at(tokens, index) is not None
            or _java_invoke_method_at(tokens, index) is not None
        ):
            count += 1
    return count


def _pipeline_api_method_at(tokens: list[JavaToken], index: int) -> str | None:
    if tokens[index].value != "IDataUtil" or _token_value(tokens, index + 1) != ".":
        return None
    method_token = _token(tokens, index + 2)
    if method_token is None or _token_value(tokens, index + 3) != "(":
        return None
    method = method_token.value
    if method not in PIPELINE_READ_METHODS | PIPELINE_WRITE_METHODS | PIPELINE_REMOVE_METHODS:
        return None
    return method


def _java_invoke_method_at(tokens: list[JavaToken], index: int) -> str | None:
    if tokens[index].value != "Service" or _token_value(tokens, index + 1) != ".":
        return None
    method_token = _token(tokens, index + 2)
    if method_token is None or method_token.value not in JAVA_INVOKE_APIS:
        return None
    if _token_value(tokens, index + 3) != "(":
        return None
    return method_token.value


def _pipeline_accesses(
    method_input: JavaMethodInput,
    service_name: str,
    id_factory: Any,
    scan_root: Path,
    findings: list[AnalysisFinding],
    direct_token_indexes: set[int],
) -> list[JavaPipelineAccess]:
    cursor_scopes = _cursor_scopes(method_input.tokens)
    accesses: list[JavaPipelineAccess] = []
    for index, token in enumerate(method_input.tokens, start=1):
        if index not in direct_token_indexes:
            continue
        method = _pipeline_api_method_at(method_input.tokens, index - 1)
        if method is None:
            continue
        paren_end = _matching(method_input.tokens, index + 2, "(", ")")
        if paren_end is None:
            findings.append(
                _finding_from_token(
                    "JAVA_SOURCE_PARTIAL_PARSE",
                    "Java scanner could not safely determine IDataUtil call boundaries.",
                    method_input,
                    token,
                    scan_root,
                    FindingSeverity.WARNING,
                )
            )
            continue
        args = _split_arguments(method_input.tokens[index + 3 : paren_end])
        source = _java_source_reference(method_input, token, index, scan_root)
        cursor_name = args[0][0].value if args and len(args[0]) == 1 else None
        key = _literal_value(args[1]) if len(args) > 1 else None
        dynamic_key = len(args) <= 1 or key is None
        if dynamic_key:
            findings.append(
                _finding_from_token(
                    "DYNAMIC_PIPELINE_KEY",
                    "Pipeline access uses a non-literal key; expression text was not serialized.",
                    method_input,
                    token,
                    scan_root,
                    FindingSeverity.INFO,
                )
            )
        access_kind = _pipeline_access_kind(method)
        accesses.append(
            JavaPipelineAccess(
                id=id_factory.make(
                    "javapipe",
                    source.primary,
                    service_name,
                    access_kind.value,
                    f"IDataUtil.{method}",
                    index,
                ),
                service=service_name,
                access_kind=access_kind,
                api_form=f"IDataUtil.{method}",
                field_key=key,
                dynamic_key=dynamic_key,
                cursor_scope=cursor_scopes.get(cursor_name or "", JavaCursorScope.UNKNOWN_CURSOR),
                evidenced_java_type=_evidenced_type(method_input.tokens, index - 1, method),
                token_ordinal=index,
                source=source,
            )
        )
    return sorted(accesses, key=lambda item: item.token_ordinal)


def _cursor_scopes(tokens: list[JavaToken]) -> dict[str, JavaCursorScope]:
    scopes: dict[str, JavaCursorScope] = {}
    for index, token in enumerate(tokens):
        if token.value != "IDataCursor":
            continue
        name = _token(tokens, index + 1)
        if name is None or _token_value(tokens, index + 2) != "=":
            continue
        receiver = _cursor_receiver(tokens, index + 3)
        if receiver == "pipeline":
            scopes[name.value] = JavaCursorScope.ROOT_PIPELINE
        elif receiver is None:
            scopes[name.value] = JavaCursorScope.UNKNOWN_CURSOR
        else:
            scopes[name.value] = JavaCursorScope.NESTED_IDATA
    return scopes


def _cursor_receiver(tokens: list[JavaToken], start: int) -> str | None:
    for index in range(start, min(len(tokens), start + 8)):
        if (
            _token(tokens, index) is not None
            and _token_value(tokens, index + 1) == "."
            and _token_value(tokens, index + 2) == "getCursor"
        ):
            return tokens[index].value
    return None


def _java_invocations(
    method_input: JavaMethodInput,
    service_name: str,
    id_factory: Any,
    scan_root: Path,
    findings: list[AnalysisFinding],
    direct_token_indexes: set[int],
) -> tuple[list[JavaInvocationOccurrence], list[CallOccurrence]]:
    occurrences: list[JavaInvocationOccurrence] = []
    calls: list[CallOccurrence] = []
    for index, token in enumerate(method_input.tokens, start=1):
        if index not in direct_token_indexes:
            continue
        method = _java_invoke_method_at(method_input.tokens, index - 1)
        if method is None:
            continue
        paren_end = _matching(method_input.tokens, index + 2, "(", ")")
        if paren_end is None:
            continue
        args = _split_arguments(method_input.tokens[index + 3 : paren_end])
        source = _java_source_reference(method_input, token, index, scan_root)
        direct_prefix = [
            prefix_token
            for prefix_index, prefix_token in enumerate(method_input.tokens[: index - 1], start=1)
            if prefix_index in direct_token_indexes
        ]
        constants = _string_constants(direct_prefix)
        target, status = _java_target(args, constants)
        if status == JavaInvocationTargetStatus.DYNAMIC_TARGET:
            findings.append(
                _finding_from_token(
                    "DYNAMIC_SERVICE_TARGET",
                    "Java service invocation target is dynamic; expression text was not "
                    "serialized.",
                    method_input,
                    token,
                    scan_root,
                    FindingSeverity.WARNING,
                )
            )
        elif status == JavaInvocationTargetStatus.PARTIALLY_STATIC_TARGET:
            findings.append(
                _finding_from_token(
                    "PARTIALLY_STATIC_SERVICE_TARGET",
                    "Java service invocation target is only partially static.",
                    method_input,
                    token,
                    scan_root,
                    FindingSeverity.INFO,
                )
            )
        invocation = JavaInvocationOccurrence(
            id=id_factory.make(
                "javacall",
                source.primary,
                service_name,
                "Service.doInvoke",
                index,
            ),
            caller=service_name,
            api_form=f"Service.{method}",
            target_status=status,
            declared_target=target if status == JavaInvocationTargetStatus.STATIC_TARGET else None,
            canonical_target=target if status == JavaInvocationTargetStatus.STATIC_TARGET else None,
            synchronous=True,
            token_ordinal=index,
            source=source,
            confidence=(
                InterpretationConfidence.CONFIRMED
                if status == JavaInvocationTargetStatus.STATIC_TARGET
                else InterpretationConfidence.RAW_ONLY
            ),
        )
        occurrences.append(invocation)
        if status == JavaInvocationTargetStatus.STATIC_TARGET and target is not None:
            calls.append(
                CallOccurrence(
                    id=invocation.id.replace("javacall_", "call_java_", 1),
                    caller=service_name,
                    target=target,
                    call_type=CallType.JAVA_INVOKE,
                    dependency_kind=DependencyKind.INVOKES,
                    order=index,
                    structural_path=f"java:{index}",
                    resolved=False,
                    target_classification=_low_placeholder_classification(),
                    source=source.primary,
                )
            )
    return sorted(occurrences, key=lambda item: item.token_ordinal), calls


def _java_target(
    args: list[list[JavaToken]], constants: dict[str, str]
) -> tuple[str | None, JavaInvocationTargetStatus]:
    if not args:
        return None, JavaInvocationTargetStatus.MALFORMED_TARGET
    if len(args) >= 2:
        first = _argument_static_value(args[0], constants)
        second = _argument_static_value(args[1], constants)
        if first and ":" in first:
            return first, JavaInvocationTargetStatus.STATIC_TARGET
        if first and second:
            return f"{first}:{second}", JavaInvocationTargetStatus.STATIC_TARGET
        if first or second:
            return None, JavaInvocationTargetStatus.PARTIALLY_STATIC_TARGET
    single = _argument_static_value(args[0], constants)
    if single and ":" in single:
        return single, JavaInvocationTargetStatus.STATIC_TARGET
    if _is_literal_nsname(args[0]):
        values = [_literal_value([token]) for token in args[0] if token.kind == "literal"]
        literals = [value for value in values if value is not None]
        if len(literals) >= 2:
            return f"{literals[0]}:{literals[1]}", JavaInvocationTargetStatus.STATIC_TARGET
    return None, JavaInvocationTargetStatus.DYNAMIC_TARGET


def _argument_static_value(tokens: list[JavaToken], constants: dict[str, str]) -> str | None:
    literal = _literal_value(tokens)
    if literal is not None:
        return literal
    if len(tokens) == 1 and tokens[0].value in constants:
        return constants[tokens[0].value]
    return None


def _is_literal_nsname(tokens: list[JavaToken]) -> bool:
    values = [token.value for token in tokens]
    return ("NSName" in values and ("create" in values or "new" in values))


def _string_constants(tokens: list[JavaToken]) -> dict[str, str]:
    assignments: dict[str, list[str]] = {}
    for index, token in enumerate(tokens):
        if token.value not in {"String", "final"}:
            continue
        string_index = index if token.value == "String" else index + 1
        if _token_value(tokens, string_index) != "String":
            continue
        name = _token(tokens, string_index + 1)
        if name is None or _token_value(tokens, string_index + 2) != "=":
            continue
        value_token = _token(tokens, string_index + 3)
        if value_token is not None and value_token.kind == "literal":
            value = _literal_token_value(value_token)
            assignments.setdefault(name.value, []).append(value)
    return {
        name: values[0]
        for name, values in assignments.items()
        if len(values) == 1 and _assignment_count(tokens, name) == 1
    }


def _assignment_count(tokens: list[JavaToken], name: str) -> int:
    count = 0
    for index, token in enumerate(tokens):
        if token.value == name and _token_value(tokens, index + 1) == "=":
            count += 1
    return count


def _java_metrics(
    source_set: JavaSourceSet,
    pipeline_accesses: list[JavaPipelineAccess],
    invocations: list[JavaInvocationOccurrence],
    java_calls: list[CallOccurrence],
) -> Any:
    from wm_doc.ir import AnalysisMetrics

    status_counts = Counter({source_set.status.value: 1})
    access_counts = Counter(access.access_kind.value for access in pipeline_accesses)
    scope_counts = Counter(access.cursor_scope.value for access in pipeline_accesses)
    dynamic_invocations = sum(
        1
        for invocation in invocations
        if invocation.target_status != JavaInvocationTargetStatus.STATIC_TARGET
    )
    return AnalysisMetrics(
        java_service_analysis_count=1,
        java_source_match_count=status_counts[JavaSourceStatus.SOURCE_AND_FRAGMENT_MATCH.value],
        java_source_only_count=status_counts[JavaSourceStatus.SOURCE_ONLY.value],
        java_fragment_only_count=status_counts[JavaSourceStatus.FRAGMENT_ONLY.value],
        java_source_mismatch_count=status_counts[JavaSourceStatus.SOURCE_FRAGMENT_MISMATCH.value],
        java_source_method_not_found_count=status_counts[
            JavaSourceStatus.SOURCE_METHOD_NOT_FOUND.value
        ],
        java_source_method_ambiguous_count=status_counts[
            JavaSourceStatus.SOURCE_METHOD_AMBIGUOUS.value
        ],
        java_source_identity_mismatch_count=status_counts[
            JavaSourceStatus.SOURCE_IDENTITY_MISMATCH.value
        ],
        java_source_partial_parse_count=status_counts[JavaSourceStatus.SOURCE_PARTIAL_PARSE.value],
        java_pipeline_access_count=len(pipeline_accesses),
        java_pipeline_access_kind_counts=dict(sorted(access_counts.items())),
        java_pipeline_cursor_scope_counts=dict(sorted(scope_counts.items())),
        java_invocation_occurrence_count=len(invocations),
        java_static_call_occurrence_count=len(java_calls),
        java_dynamic_call_occurrence_count=dynamic_invocations,
    )


def _source_imports(
    tokens: list[JavaToken], source_path: Path, scan_root: Path
) -> list[JavaImportDecl]:
    imports: list[JavaImportDecl] = []
    index = 0
    order = 1
    while index < len(tokens):
        if tokens[index].value == "class":
            break
        if tokens[index].value != "import":
            index += 1
            continue
        import_token = tokens[index]
        index += 1
        is_static = False
        if _token_value(tokens, index) == "static":
            is_static = True
            index += 1
        parts: list[str] = []
        while index < len(tokens) and tokens[index].value != ";":
            parts.append(tokens[index].value)
            index += 1
        declaration = "".join(parts)
        imports.append(
            JavaImportDecl(
                declaration=declaration,
                imported_name=declaration.removesuffix(".*"),
                is_static=is_static,
                is_wildcard=declaration.endswith(".*"),
                order=order,
                source=SourceReference(
                    path=stable_relative_path(source_path, scan_root),
                    artifact_type="java_import",
                    line=import_token.line,
                    column=import_token.column,
                ),
            )
        )
        order += 1
        index += 1
    return imports


def _package_name(tokens: list[JavaToken]) -> str | None:
    for index, token in enumerate(tokens):
        if token.value != "package":
            continue
        parts: list[str] = []
        cursor = index + 1
        while cursor < len(tokens) and tokens[cursor].value != ";":
            parts.append(tokens[cursor].value)
            cursor += 1
        return "".join(parts)
    return None


def _top_level_class(tokens: list[JavaToken]) -> tuple[str | None, int | None, int | None]:
    depths = _brace_depths(tokens)
    for index, token in enumerate(tokens):
        if token.value == "class" and depths[index] == 0:
            name = _token(tokens, index + 1)
            open_index = _next_value(tokens, index + 2, "{")
            if name is None or open_index is None:
                return None, None, None
            close_index = _matching(tokens, open_index, "{", "}")
            return name.value, open_index, close_index
    return None, None, None


def _compilation_unit_parse_issue(
    tokens: list[JavaToken], class_open: int | None, class_close: int | None
) -> JavaParseIssue | None:
    brace_issue = _balanced_token_issue(tokens, "{", "}")
    if brace_issue is not None:
        return brace_issue
    paren_issue = _balanced_token_issue(tokens, "(", ")")
    if paren_issue is not None:
        return paren_issue
    if class_open is not None and class_close is None:
        return JavaParseIssue(
            token=tokens[class_open],
            message="Top-level generated service class has no matching closing brace.",
        )
    depths = _brace_depths(tokens)
    for index, token in enumerate(tokens):
        if token.value == "class" and depths[index] == 0 and class_open is None:
            return JavaParseIssue(
                token=token,
                message="Top-level generated service class declaration is incomplete.",
            )
    return None


def _balanced_token_issue(
    tokens: list[JavaToken], open_value: str, close_value: str
) -> JavaParseIssue | None:
    depth = 0
    last_open: JavaToken | None = None
    for token in tokens:
        if token.value == open_value:
            depth += 1
            last_open = token
        elif token.value == close_value:
            depth -= 1
            if depth < 0:
                return JavaParseIssue(
                    token=token,
                    message=f"Java source has an unmatched {close_value!r} token.",
                )
    if depth > 0:
        return JavaParseIssue(
            token=last_open,
            message=f"Java source has an unmatched {open_value!r} token.",
        )
    return None


def _brace_depths(tokens: list[JavaToken]) -> list[int]:
    depths: list[int] = []
    depth = 0
    for token in tokens:
        depths.append(depth)
        if token.value == "{":
            depth += 1
        elif token.value == "}":
            depth = max(depth - 1, 0)
    return depths


def _matching(tokens: list[JavaToken], start: int, open_value: str, close_value: str) -> int | None:
    depth = 0
    for index in range(start, len(tokens)):
        if tokens[index].value == open_value:
            depth += 1
        elif tokens[index].value == close_value:
            depth -= 1
            if depth == 0:
                return index
    return None


def _method_body_open(tokens: list[JavaToken], start: int) -> int | None:
    index = start
    while index < len(tokens):
        value = tokens[index].value
        if value == "{":
            return index
        if value == ";":
            return None
        index += 1
    return None


def _declaration_start(tokens: list[JavaToken], method_index: int) -> int:
    index = method_index - 1
    while index > 0 and tokens[index].value not in {";", "{", "}"}:
        index -= 1
    return index + 1


def _return_type(declaration_tokens: list[JavaToken]) -> str | None:
    values = [
        token.value
        for token in _without_annotations(declaration_tokens)
        if token.value not in JAVA_MODIFIERS
    ]
    if not values:
        return None
    return values[-1]


def _parameter_types(tokens: list[JavaToken]) -> list[str]:
    params = _split_arguments(tokens)
    types: list[str] = []
    for param in params:
        if len(param) < 2:
            continue
        without_annotations = _without_annotations(param)
        if len(without_annotations) < 2:
            continue
        type_tokens = [
            token.value
            for token in without_annotations[:-1]
            if token.value not in {"final"}
        ]
        types.append("".join(type_tokens).replace("...", "[]"))
    return types


def _without_annotations(tokens: list[JavaToken]) -> list[JavaToken]:
    cleaned: list[JavaToken] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.value != "@":
            cleaned.append(token)
            index += 1
            continue
        index += 1
        if index < len(tokens) and tokens[index].kind == "id":
            index += 1
            while (
                index + 1 < len(tokens)
                and tokens[index].value == "."
                and tokens[index + 1].kind == "id"
            ):
                index += 2
        if index < len(tokens) and tokens[index].value == "(":
            paren_end = _matching(tokens, index, "(", ")")
            if paren_end is None:
                break
            index = paren_end + 1
    return cleaned


def _split_arguments(tokens: list[JavaToken]) -> list[list[JavaToken]]:
    args: list[list[JavaToken]] = []
    current: list[JavaToken] = []
    parens = brackets = braces = angles = 0
    for token in tokens:
        value = token.value
        if value == "," and parens == brackets == braces == angles == 0:
            args.append(current)
            current = []
            continue
        current.append(token)
        if value == "(":
            parens += 1
        elif value == ")":
            parens = max(0, parens - 1)
        elif value == "[":
            brackets += 1
        elif value == "]":
            brackets = max(0, brackets - 1)
        elif value == "{":
            braces += 1
        elif value == "}":
            braces = max(0, braces - 1)
        elif value == "<":
            angles += 1
        elif value == ">":
            angles = max(0, angles - 1)
    if current:
        args.append(current)
    return args


def _pipeline_access_kind(method: str) -> JavaPipelineAccessKind:
    if method in PIPELINE_READ_METHODS:
        return JavaPipelineAccessKind.READ
    if method in PIPELINE_WRITE_METHODS:
        return JavaPipelineAccessKind.WRITE
    if method in PIPELINE_REMOVE_METHODS:
        return JavaPipelineAccessKind.REMOVE
    return JavaPipelineAccessKind.UNKNOWN_ACCESS


def _evidenced_type(tokens: list[JavaToken], call_index: int, method: str) -> str | None:
    if method == "getString":
        return "String"
    if method == "getIData":
        return "IData"
    if method == "getIDataArray":
        return "IData[]"
    if method != "get":
        return None
    if call_index <= 0 or _token_value(tokens, call_index - 1) != ")":
        return None
    open_index = _previous_matching_open(tokens, call_index - 1)
    if open_index is None:
        return None
    return "".join(token.value for token in tokens[open_index + 1 : call_index - 1]) or None


def _previous_matching_open(tokens: list[JavaToken], close_index: int) -> int | None:
    depth = 0
    for index in range(close_index, -1, -1):
        if tokens[index].value == ")":
            depth += 1
        elif tokens[index].value == "(":
            depth -= 1
            if depth == 0:
                return index
    return None


def _literal_value(tokens: list[JavaToken]) -> str | None:
    stripped = [token for token in tokens if token.value not in {"(", ")"}]
    if len(stripped) == 1 and stripped[0].kind == "literal":
        return _literal_token_value(stripped[0])
    return None


def _literal_token_value(token: JavaToken) -> str:
    value = token.value
    if value.startswith('"""') and value.endswith('"""'):
        return value[3:-3]
    if len(value) >= 2 and value[0] in {'"', "'"} and value[-1] == value[0]:
        return value[1:-1]
    return value


def _java_source_reference(
    method_input: JavaMethodInput, token: JavaToken, token_ordinal: int, scan_root: Path
) -> JavaSourceReference:
    primary = SourceReference(
        path=stable_relative_path(method_input.primary_path, scan_root),
        artifact_type=method_input.primary_artifact_type,
        source_node="body" if method_input.primary_artifact_type == "java_frag_body" else None,
        line=token.line,
        column=token.column,
        end_line=token.end_line,
        end_column=token.end_column,
        class_name=method_input.primary_class_name,
        method_name=method_input.primary_method_name,
    )
    corroborating = None
    if method_input.corroborating_path is not None and token_ordinal <= len(
        method_input.corroborating_tokens
    ):
        frag_token = method_input.corroborating_tokens[token_ordinal - 1]
        corroborating = SourceReference(
            path=stable_relative_path(method_input.corroborating_path, scan_root),
            artifact_type="java_frag_body",
            source_node="body",
            line=frag_token.line,
            column=frag_token.column,
            end_line=frag_token.end_line,
            end_column=frag_token.end_column,
        )
    return JavaSourceReference(
        primary=primary, corroborating=corroborating, token_ordinal=token_ordinal
    )


def _method_source(
    method: JavaMethodCandidate, source_path: Path | None, scan_root: Path, class_name: str
) -> SourceReference:
    return SourceReference(
        path=stable_relative_path(source_path, scan_root) if source_path else ".",
        artifact_type="java_source",
        line=method.body_open.line,
        column=method.body_open.column,
        end_line=method.body_close.end_line,
        end_column=method.body_close.end_column,
        class_name=class_name,
        method_name=method.name,
    )


def _fragment_source(
    fragment_path: Path, scan_root: Path, token: JavaToken | None
) -> SourceReference:
    return SourceReference(
        path=stable_relative_path(fragment_path, scan_root),
        artifact_type="java_frag_body",
        source_node="body",
        line=token.line if token else None,
        column=token.column if token else None,
        end_line=token.end_line if token else None,
        end_column=token.end_column if token else None,
    )


def _finding(
    code: str,
    message: str,
    path: Path,
    scan_root: Path,
    artifact_type: str,
    severity: FindingSeverity,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        code=code,
        message=message,
        source=SourceReference(
            path=stable_relative_path(path, scan_root), artifact_type=artifact_type
        ),
        severity=severity,
        confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
    )


def _partial_parse_finding(
    issue: JavaParseIssue,
    path: Path,
    scan_root: Path,
    message: str,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        code="JAVA_SOURCE_PARTIAL_PARSE",
        message=f"{message} Structural issue: {issue.message}",
        source=SourceReference(
            path=stable_relative_path(path, scan_root),
            artifact_type="java_source",
            line=issue.token.line if issue.token else None,
            column=issue.token.column if issue.token else None,
        ),
        severity=FindingSeverity.WARNING,
        confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
    )


def _unsupported_signature_finding(
    service_name: str,
    candidate: JavaMethodCandidate,
    path: Path,
    scan_root: Path,
) -> AnalysisFinding:
    reasons = "; ".join(candidate.unsupported_reasons) or "unsupported service signature"
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        code="JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED",
        message=(
            f"Java source contains same-name method for {service_name}, but the method "
            f"does not match the supported generated Java Service shape: {reasons}. "
            "java.frag fallback is used when available."
        ),
        source=SourceReference(
            path=stable_relative_path(path, scan_root),
            artifact_type="java_source",
            line=candidate.body_open.line,
            column=candidate.body_open.column,
            method_name=candidate.name,
        ),
        severity=FindingSeverity.WARNING,
        confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
    )


def _finding_from_token(
    code: str,
    message: str,
    method_input: JavaMethodInput,
    token: JavaToken,
    scan_root: Path,
    severity: FindingSeverity,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=FindingStatus.PARTIALLY_SUPPORTED,
        code=code,
        message=message,
        source=_java_source_reference(method_input, token, token.ordinal, scan_root).primary,
        severity=severity,
        confidence=InterpretationConfidence.PARTIALLY_INTERPRETED.value,
    )


def _type_category(imported_name: str, source_root: Path) -> JavaTypeCategory:
    if imported_name.startswith("com.wm."):
        return JavaTypeCategory.WEBMETHODS_API
    if imported_name.startswith("java.") or imported_name.startswith("javax."):
        return JavaTypeCategory.JAVA_STANDARD_LIBRARY
    candidate = source_root / Path(*imported_name.split(".")).with_suffix(".java")
    if candidate.exists():
        return JavaTypeCategory.PACKAGE_LOCAL_CLASS
    if imported_name.startswith("org."):
        return JavaTypeCategory.THIRD_PARTY_LIBRARY
    return JavaTypeCategory.UNKNOWN


def _token_values(tokens: list[JavaToken]) -> list[str]:
    return [token.value for token in tokens]


def _token(tokens: list[JavaToken], index: int) -> JavaToken | None:
    if 0 <= index < len(tokens):
        return tokens[index]
    return None


def _token_value(tokens: list[JavaToken], index: int) -> str | None:
    token = _token(tokens, index)
    return token.value if token else None


def _next_value(tokens: list[JavaToken], start: int, value: str) -> int | None:
    for index in range(start, len(tokens)):
        if tokens[index].value == value:
            return index
    return None


def _consume_quoted(source: str, start: int) -> tuple[str, int]:
    quote = source[start]
    index = start + 1
    escaped = False
    while index < len(source):
        char = source[index]
        index += 1
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            break
    return source[start:index], index


def _consume_text_block(source: str, start: int) -> tuple[str, int]:
    index = start + 3
    while index + 2 < len(source) and not source.startswith('"""', index):
        index += 1
    if index + 2 < len(source):
        index += 3
    return source[start:index], index


def _operator_at(source: str, index: int) -> str:
    for length in (4, 3, 2):
        value = source[index : index + length]
        if value in {
            ">>>=",
            ">>>",
            "<<=",
            ">>=",
            "==",
            "!=",
            "<=",
            ">=",
            "&&",
            "||",
            "++",
            "--",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "<<",
            ">>",
            "->",
            "::",
            "...",
        }:
            return value
    return source[index]


def _low_placeholder_classification() -> Any:
    from wm_doc.config import DEFAULT_CONFIG, classify_service

    return classify_service("", "", DEFAULT_CONFIG)
