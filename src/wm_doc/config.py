from __future__ import annotations

from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from wm_doc.ir import ClassificationMatch, ClassificationResult, Importance, Layer


class ImportanceRuleSet(BaseModel):
    fullName: list[str] = Field(default_factory=list)
    serviceName: list[str] = Field(default_factory=list)


class ImportanceRules(BaseModel):
    important: ImportanceRuleSet = Field(default_factory=ImportanceRuleSet)
    neverImportant: ImportanceRuleSet = Field(default_factory=ImportanceRuleSet)


class ClassificationConfig(BaseModel):
    importance: ImportanceRules = Field(default_factory=ImportanceRules)
    layers: dict[str, list[str]] = Field(default_factory=dict)


class ExtractionMode(StrEnum):
    REDACT = "redact"
    INCLUDE = "include"
    OMIT = "omit"


class LiteralExtractionConfig(BaseModel):
    # Literal values are the filenames, keys and flags a reader needs to understand a
    # service. The secret guard runs before this mode is consulted, so secret-like
    # literals stay redacted regardless of the setting.
    mode: ExtractionMode = ExtractionMode.INCLUDE


class FreeTextExtractionConfig(BaseModel):
    mode: ExtractionMode = ExtractionMode.INCLUDE


class ExtractionConfig(BaseModel):
    literals: LiteralExtractionConfig = Field(default_factory=LiteralExtractionConfig)
    freeText: FreeTextExtractionConfig = Field(default_factory=FreeTextExtractionConfig)


DEFAULT_PACKAGE_EXCLUDES = ("Wm*", "Default")


class PackageSelectionConfig(BaseModel):
    """Which package roots are analysed. Globs match the package directory name."""

    # When non-empty, only packages matching one of these globs are analysed.
    include: list[str] = Field(default_factory=list)
    # Software AG / IBM product packages and the Default package are skipped by default.
    exclude: list[str] = Field(default_factory=lambda: list(DEFAULT_PACKAGE_EXCLUDES))
    # Skip packages whose manifest.v3 declares system_package=yes.
    skipSystemPackages: bool = True

    def exclusion_reason(self, name: str, system_package: bool) -> str | None:
        """Return why a package is excluded, or None when it is analysed."""
        if self.include and not any(_glob_match(pattern, name) for pattern in self.include):
            return "not matched by the include patterns"
        for pattern in self.exclude:
            if _glob_match(pattern, name):
                return f"matches exclude pattern `{pattern}`"
        if self.skipSystemPackages and system_package:
            return "system package (manifest.v3 system_package=yes)"
        return None


ANALYZE_ALL_PACKAGES = PackageSelectionConfig(exclude=[], skipSystemPackages=False)


class AppConfig(BaseModel):
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    packages: PackageSelectionConfig = Field(default_factory=PackageSelectionConfig)


# Generic defaults only. Project-specific namespace rules belong in a config file
# (see examples/wm-doc.yml) passed with --config.
DEFAULT_CONFIG = AppConfig(
    classification=ClassificationConfig(
        importance=ImportanceRules(
            important=ImportanceRuleSet(
                serviceName=["*Service", "process*"],
            ),
            neverImportant=ImportanceRuleSet(
                fullName=["*utils*", "*common.helpers*", "pub.*", "wm.*"],
                serviceName=["convert*", "format*", "log*"],
            ),
        ),
        layers={
            "CHANNEL": ["*.channel:*"],
            "CORE": ["*.core:*"],
            "ADAPTER": ["*.adapter:*"],
            "UTILITY": ["*.utils:*", "*.util:*"],
        },
    )
)


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return DEFAULT_CONFIG
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError("Configuration root must be a mapping.")
    return AppConfig.model_validate(data)


def classify_service(full_name: str, service_name: str, config: AppConfig) -> ClassificationResult:
    never_match = _match_rule_set(
        "neverImportant", full_name, service_name, config.classification.importance.neverImportant
    )
    important_match = _match_rule_set(
        "important", full_name, service_name, config.classification.importance.important
    )

    if never_match is not None:
        importance = Importance.LOW
        importance_match = never_match
    elif important_match is not None:
        importance = Importance.IMPORTANT
        importance_match = important_match
    else:
        importance = Importance.NORMAL
        importance_match = None

    layer = Layer.UNKNOWN.value
    layer_match: ClassificationMatch | None = None
    for layer_name, patterns in config.classification.layers.items():
        for pattern in patterns:
            if _glob_match(pattern, full_name):
                layer = layer_name
                layer_match = ClassificationMatch(
                    category="layer",
                    field="fullName",
                    pattern=pattern,
                    value=full_name,
                    explanation=f"Service full name matched layer rule {layer_name}:{pattern}.",
                )
                break
        if layer_match is not None:
            break

    return ClassificationResult(
        importance=importance,
        layer=layer,
        importance_match=importance_match,
        layer_match=layer_match,
    )


def _match_rule_set(
    category: str, full_name: str, service_name: str, rules: ImportanceRuleSet
) -> ClassificationMatch | None:
    for field_name, value, patterns in (
        ("fullName", full_name, rules.fullName),
        ("serviceName", service_name, rules.serviceName),
    ):
        for pattern in patterns:
            if _glob_match(pattern, value):
                return ClassificationMatch(
                    category=category,
                    field=field_name,
                    pattern=pattern,
                    value=value,
                    explanation=f"{field_name} matched {category} glob {pattern}.",
                )
    return None


def _glob_match(pattern: str, value: str) -> bool:
    return fnmatchcase(value.casefold(), pattern.casefold())
