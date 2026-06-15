from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

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


class AppConfig(BaseModel):
    classification: ClassificationConfig = Field(default_factory=ClassificationConfig)


DEFAULT_CONFIG = AppConfig(
    classification=ClassificationConfig(
        importance=ImportanceRules(
            important=ImportanceRuleSet(
                fullName=["oa.*.channel:*", "di.*.adapter:*"],
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


def config_to_dict(config: AppConfig) -> dict[str, Any]:
    return config.model_dump(mode="json", exclude_none=True)
