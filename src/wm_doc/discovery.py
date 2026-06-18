from __future__ import annotations

from collections import Counter
from pathlib import Path

from wm_doc import __version__
from wm_doc.ir import (
    AnalysisFinding,
    ArtifactCandidate,
    ArtifactFile,
    ArtifactIdentity,
    Confidence,
    FactBasis,
    FileSummary,
    FindingStatus,
    InventoryResult,
    PackageInventory,
    SourceReference,
    source_for,
    stable_relative_path,
)
from wm_doc.values import parse_values_file, record_value, scalar_value
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError

ACTIVE_ARTIFACT_FILES = ("node.ndf", "flow.xml", "java.frag")
FILE_ROLE_ORDER = {
    "node.ndf": 0,
    "flow.xml": 1,
    "java.frag": 2,
    "node.idf": 3,
    "manifest.v3": 4,
    "flow.xml.bak": 5,
}


def scan_path(path: Path) -> InventoryResult:
    scan_root = path.resolve()
    package_roots = _find_package_roots(scan_root)
    findings: list[AnalysisFinding] = []
    if not package_roots:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.UNRESOLVED,
                code="NO_PACKAGE_ROOT_FOUND",
                message="No webMethods package root was found under the scan path.",
                source=SourceReference(path="."),
            )
        )

    packages = [_scan_package(package_root, scan_root) for package_root in package_roots]
    file_summary = _file_summary(scan_root)
    return InventoryResult(
        tool_version=__version__,
        scan_root=".",
        packages=packages,
        file_summary=file_summary,
        findings=findings,
    )


def _find_package_roots(scan_root: Path) -> list[Path]:
    if _is_package_root(scan_root):
        return [scan_root]
    candidates = [
        candidate
        for candidate in scan_root.rglob("*")
        if candidate.is_dir() and _is_package_root(candidate)
    ]
    candidates.sort(key=lambda item: stable_relative_path(item, scan_root).lower())
    accepted: list[Path] = []
    for candidate in candidates:
        if not any(_is_relative_to(candidate, parent) for parent in accepted):
            accepted.append(candidate)
    return accepted


def _is_package_root(path: Path) -> bool:
    return (path / "ns").is_dir() or (path / "manifest.v3").is_file()


def _scan_package(package_root: Path, scan_root: Path) -> PackageInventory:
    artifacts: list[ArtifactCandidate] = []
    findings: list[AnalysisFinding] = []
    consumed: set[Path] = set()
    aliases: set[str] = set()
    package_name = package_root.name
    evidence = ["Directory is treated as package root because it contains ns/ or manifest.v3."]

    manifest_path = package_root / "manifest.v3"
    manifest: dict[str, str | list[str] | None] = {}
    if manifest_path.exists():
        consumed.add(manifest_path)
        artifact, manifest_data, manifest_findings = _manifest_artifact(
            manifest_path, package_root, scan_root
        )
        artifacts.append(artifact)
        manifest = manifest_data
        findings.extend(manifest_findings)

    project_path = package_root / ".project"
    if project_path.exists():
        project_name = _read_project_name(project_path)
        if project_name is not None:
            aliases.add(project_name)

    namespace_root = package_root / "ns"
    if namespace_root.exists():
        for node_idf in sorted(namespace_root.rglob("node.idf"), key=_stable_path_key):
            consumed.add(node_idf)
            artifact = _namespace_folder_artifact(node_idf, package_root, scan_root)
            artifacts.append(artifact)

        artifact_dirs = _find_namespace_artifact_dirs(namespace_root)
        for artifact_dir in artifact_dirs:
            artifact, artifact_findings, artifact_aliases, artifact_files = _namespace_artifact(
                artifact_dir, package_root, scan_root
            )
            artifacts.append(artifact)
            findings.extend(artifact_findings)
            aliases.update(artifact_aliases)
            consumed.update(artifact_files)

        for backup in sorted(namespace_root.rglob("flow.xml.bak"), key=_stable_path_key):
            consumed.add(backup)
            artifacts.append(_backup_artifact(backup, package_root, scan_root))

    for unsupported in sorted(
        [item for item in package_root.rglob("*") if item.is_file() and item not in consumed],
        key=_stable_path_key,
    ):
        artifacts.append(_unsupported_file_artifact(unsupported, package_root, scan_root))

    aliases.discard(package_name)
    if package_name == "PGP":
        findings.append(
            AnalysisFinding(
                status=FindingStatus.UNKNOWN,
                code="PGP_PROVENANCE_UNKNOWN",
                message=(
                    "The public PGP fixture is used as-is; upstream URL, exact commit SHA, "
                    "and documented webMethods version are not available in the repository."
                ),
                source=source_for(package_root, scan_root, "package"),
            )
        )

    if aliases:
        findings.append(
            AnalysisFinding(
                status=FindingStatus.PARTIALLY_SUPPORTED,
                code="PACKAGE_ALIAS_CONFLICT",
                message=(
                    "Package-related metadata contains names that differ from the directory "
                    f"name {package_name!r}: {', '.join(sorted(aliases))}."
                ),
                source=source_for(package_root, scan_root, "package"),
            )
        )

    artifacts.sort(key=lambda artifact: artifact.relative_path.lower())
    findings.sort(key=lambda finding: (finding.source.path.lower(), finding.code))
    return PackageInventory(
        name=package_name,
        root=stable_relative_path(package_root, scan_root),
        evidence=evidence,
        manifest=manifest,
        aliases=sorted(aliases),
        artifacts=artifacts,
        findings=findings,
    )


def _manifest_artifact(
    manifest_path: Path, package_root: Path, scan_root: Path
) -> tuple[ArtifactCandidate, dict[str, str | list[str] | None], list[AnalysisFinding]]:
    findings: list[AnalysisFinding] = []
    manifest_data: dict[str, str | list[str] | None] = {}
    evidence = ["manifest.v3 file is present."]
    status = FindingStatus.SUPPORTED
    confidence = Confidence.HIGH
    try:
        values = parse_values_file(manifest_path)
        manifest_data["enabled"] = scalar_value(values, "enabled")
        manifest_data["system_package"] = scalar_value(values, "system_package")
        manifest_data["version"] = scalar_value(values, "version")
        requires = record_value(values, "requires")
        manifest_data["requires"] = sorted(requires.keys()) if requires else []
        evidence.append("Parsed Values XML metadata from manifest.v3.")
    except (XmlParseError, XmlSecurityError) as exc:
        status = FindingStatus.MALFORMED
        confidence = Confidence.LOW
        findings.append(_xml_finding(exc, manifest_path, scan_root, "manifest"))

    return (
        ArtifactCandidate(
            relative_path=stable_relative_path(manifest_path, scan_root),
            probable_type="package_manifest",
            files=[_artifact_file(manifest_path, scan_root, active=True)],
            evidence=evidence,
            confidence=confidence,
            parser_responsibility="ManifestParser",
            status=status,
            source=source_for(manifest_path, scan_root, "manifest"),
        ),
        manifest_data,
        findings,
    )


def _namespace_folder_artifact(
    node_idf: Path, package_root: Path, scan_root: Path
) -> ArtifactCandidate:
    evidence = ["node.idf file is present."]
    status = FindingStatus.SUPPORTED
    confidence = Confidence.HIGH
    try:
        values = parse_values_file(node_idf)
        node_type = scalar_value(values, "node_type")
        node_ns_name = scalar_value(values, "node_nsName")
        if node_type is not None:
            evidence.append(f"node_type={node_type}.")
        if node_ns_name is not None:
            evidence.append(f"node_nsName={node_ns_name}.")
    except (XmlParseError, XmlSecurityError) as exc:
        status = FindingStatus.MALFORMED
        confidence = Confidence.LOW
        evidence.append(str(exc))

    identity = _identity_from_namespace_path(
        node_idf.parent, package_root, basis=FactBasis.CONFIRMED
    )
    return ArtifactCandidate(
        relative_path=stable_relative_path(node_idf.parent, scan_root),
        probable_type="namespace_folder",
        files=[_artifact_file(node_idf, scan_root, active=True)],
        evidence=evidence,
        confidence=confidence,
        parser_responsibility="NamespaceFolderParser",
        status=status,
        identity=identity,
        source=source_for(node_idf, scan_root, "namespace_folder"),
    )


def _namespace_artifact(
    artifact_dir: Path, package_root: Path, scan_root: Path
) -> tuple[ArtifactCandidate, list[AnalysisFinding], set[str], set[Path]]:
    findings: list[AnalysisFinding] = []
    aliases: set[str] = set()
    files = [
        artifact_dir / file_name
        for file_name in ACTIVE_ARTIFACT_FILES
        if (artifact_dir / file_name).exists()
    ]
    evidence = [f"{file.name} present." for file in files]
    consumed = set(files)
    status = FindingStatus.SUPPORTED
    confidence = Confidence.MEDIUM
    probable_type = "unknown_namespace_artifact"
    parser_responsibility = "UnknownArtifactReporter"

    node_path = artifact_dir / "node.ndf"
    flow_path = artifact_dir / "flow.xml"
    java_path = artifact_dir / "java.frag"
    values: dict[str, object] = {}

    if node_path.exists():
        try:
            values = parse_values_file(node_path)
            svc_type = _normalized_svc_type(values)
            if svc_type is not None:
                evidence.append(f"node.ndf svc_type={svc_type}.")
            node_pkg = _find_node_package(values)
            if node_pkg is not None:
                aliases.add(node_pkg)
            probable_type, parser_responsibility, confidence = _classify_from_values(
                values, flow_path.exists(), java_path.exists()
            )
        except (XmlParseError, XmlSecurityError) as exc:
            status = FindingStatus.MALFORMED
            confidence = Confidence.LOW
            findings.append(_xml_finding(exc, node_path, scan_root, "node_ndf"))
    else:
        status = FindingStatus.PARTIALLY_SUPPORTED
        evidence.append("node.ndf is missing.")
        findings.append(
            AnalysisFinding(
                status=FindingStatus.UNRESOLVED,
                code="NODE_NDF_MISSING",
                message="A namespace artifact file exists without node.ndf metadata.",
                source=source_for(artifact_dir, scan_root, "namespace_artifact"),
            )
        )
        if flow_path.exists():
            probable_type = "flow_xml_without_node"
            parser_responsibility = "FlowMetadataReporter"
        elif java_path.exists():
            probable_type = "java_frag_without_node"
            parser_responsibility = "JavaMetadataReporter"

    svc_type = _normalized_svc_type(values) if values else None
    if svc_type == "flow" and not flow_path.exists():
        status = FindingStatus.PARTIALLY_SUPPORTED
        probable_type = "flow_service_metadata_without_flow"
        findings.append(
            AnalysisFinding(
                status=FindingStatus.UNRESOLVED,
                code="FLOW_XML_MISSING",
                message="node.ndf declares a FLOW service but flow.xml is missing.",
                source=source_for(node_path, scan_root, "flow_service"),
            )
        )
    if svc_type == "java" and not java_path.exists():
        status = FindingStatus.PARTIALLY_SUPPORTED
        findings.append(
            AnalysisFinding(
                status=FindingStatus.UNRESOLVED,
                code="JAVA_FRAG_MISSING",
                message="node.ndf declares a Java service but java.frag is missing.",
                source=source_for(node_path, scan_root, "java_service"),
            )
        )

    identity = _identity_from_namespace_path(
        artifact_dir, package_root, basis=FactBasis.RECONSTRUCTED
    )
    return (
        ArtifactCandidate(
            relative_path=stable_relative_path(artifact_dir, scan_root),
            probable_type=probable_type,
            source_service_type=svc_type,
            files=sorted(
                [_artifact_file(file, scan_root, active=True) for file in files],
                key=lambda item: (FILE_ROLE_ORDER.get(Path(item.path).name, 99), item.path),
            ),
            evidence=evidence,
            confidence=confidence,
            parser_responsibility=parser_responsibility,
            status=status,
            identity=identity,
            source=source_for(
                node_path if node_path.exists() else artifact_dir, scan_root, probable_type
            ),
        ),
        findings,
        aliases,
        consumed,
    )


def _classify_from_values(
    values: dict[str, object], has_flow: bool, has_java: bool
) -> tuple[str, str, Confidence]:
    svc_type = _normalized_svc_type(values)
    if svc_type == "flow":
        return (
            "flow_service",
            "FlowServiceMetadataParser",
            Confidence.HIGH if has_flow else Confidence.MEDIUM,
        )
    if svc_type == "java":
        return (
            "java_service",
            "JavaServiceMetadataParser",
            Confidence.HIGH if has_java else Confidence.MEDIUM,
        )
    if svc_type == "spec":
        return ("specification", "SpecificationMetadataParser", Confidence.HIGH)
    if svc_type:
        return ("opaque_service", "OpaqueServiceMetadataParser", Confidence.MEDIUM)
    record = record_value(values, "record")
    if record is not None and scalar_value(record, "node_type") == "record":
        return ("document_type", "DocumentTypeMetadataParser", Confidence.MEDIUM)
    return ("unknown_namespace_artifact", "UnknownArtifactReporter", Confidence.LOW)


def _normalized_svc_type(values: dict[str, object]) -> str | None:
    svc_type = scalar_value(values, "svc_type")
    if svc_type is None:
        return None
    normalized = svc_type.strip()
    return normalized or None


def _backup_artifact(backup: Path, package_root: Path, scan_root: Path) -> ArtifactCandidate:
    identity = _identity_from_namespace_path(
        backup.parent, package_root, basis=FactBasis.RECONSTRUCTED
    )
    return ArtifactCandidate(
        relative_path=stable_relative_path(backup, scan_root),
        probable_type="helper_backup_file",
        files=[_artifact_file(backup, scan_root, active=False)],
        evidence=["flow.xml.bak is a backup file and is not analyzed by default."],
        confidence=Confidence.HIGH,
        parser_responsibility="BackupFileReporter",
        status=FindingStatus.PARTIALLY_SUPPORTED,
        identity=identity,
        source=source_for(backup, scan_root, "helper_backup_file"),
    )


def _unsupported_file_artifact(
    file_path: Path, package_root: Path, scan_root: Path
) -> ArtifactCandidate:
    relative_to_package = stable_relative_path(file_path, package_root)
    return ArtifactCandidate(
        relative_path=stable_relative_path(file_path, scan_root),
        probable_type="unsupported_file",
        files=[_artifact_file(file_path, scan_root, active=False)],
        evidence=[
            "File is outside the M0 active artifact set and its contents were not inspected.",
            f"Package-relative path: {relative_to_package}.",
        ],
        confidence=Confidence.HIGH,
        parser_responsibility="UnsupportedFileReporter",
        status=FindingStatus.UNKNOWN,
        source=source_for(file_path, scan_root, "unsupported_file"),
    )


def _find_namespace_artifact_dirs(namespace_root: Path) -> list[Path]:
    artifact_dirs = {
        file.parent
        for file in namespace_root.rglob("*")
        if file.is_file() and file.name in ACTIVE_ARTIFACT_FILES
    }
    return sorted(artifact_dirs, key=_stable_path_key)


def _identity_from_namespace_path(
    artifact_path: Path, package_root: Path, basis: FactBasis
) -> ArtifactIdentity | None:
    namespace_root = package_root / "ns"
    try:
        relative = artifact_path.relative_to(namespace_root)
    except ValueError:
        return None
    parts = relative.parts
    if not parts:
        return ArtifactIdentity(basis=FactBasis.UNRESOLVED)
    if artifact_path.name == "node.idf":
        parts = artifact_path.parent.relative_to(namespace_root).parts
    if len(parts) == 1:
        namespace = parts[0]
        return ArtifactIdentity(
            namespace=namespace, name=parts[0], full_name=namespace, basis=basis
        )
    name = parts[-1]
    namespace = ".".join(parts[:-1])
    return ArtifactIdentity(
        namespace=namespace, name=name, full_name=f"{namespace}:{name}", basis=basis
    )


def _artifact_file(path: Path, scan_root: Path, active: bool) -> ArtifactFile:
    return ArtifactFile(
        path=stable_relative_path(path, scan_root),
        role=path.name,
        active=active,
        size_bytes=path.stat().st_size,
    )


def _xml_finding(
    exc: Exception, path: Path, scan_root: Path, artifact_type: str
) -> AnalysisFinding:
    status = FindingStatus.MALFORMED
    code = "XML_MALFORMED"
    if isinstance(exc, XmlSecurityError):
        code = "XML_UNSAFE"
    return AnalysisFinding(
        status=status,
        code=code,
        message=str(exc),
        source=source_for(path, scan_root, artifact_type),
    )


def _find_node_package(values: dict[str, object]) -> str | None:
    direct = scalar_value(values, "node_pkg")
    if direct is not None:
        return direct
    record = record_value(values, "record")
    if record is not None:
        return scalar_value(record, "node_pkg")
    return None


def _read_project_name(project_path: Path) -> str | None:
    try:
        text = project_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    start = text.find("<name>")
    end = text.find("</name>")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start + len("<name>") : end].strip() or None


def _file_summary(scan_root: Path) -> list[FileSummary]:
    counts = Counter(path.suffix or "[none]" for path in scan_root.rglob("*") if path.is_file())
    return [
        FileSummary(extension=extension, count=count)
        for extension, count in sorted(counts.items())
    ]


def _is_relative_to(path: Path, possible_parent: Path) -> bool:
    try:
        path.relative_to(possible_parent)
        return path != possible_parent
    except ValueError:
        return False


def _stable_path_key(path: Path) -> str:
    return path.as_posix().lower()
