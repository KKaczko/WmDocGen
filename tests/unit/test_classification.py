from __future__ import annotations

from wm_doc.config import DEFAULT_CONFIG, classify_service
from wm_doc.ir import Importance


def test_classification_important_full_name_match() -> None:
    result = classify_service("di.sales.adapter:createOrder", "createOrder", DEFAULT_CONFIG)

    assert result.importance == Importance.IMPORTANT
    assert result.importance_match is not None
    assert result.importance_match.field == "fullName"


def test_classification_important_service_name_match() -> None:
    result = classify_service("acme.foo:processOrder", "processOrder", DEFAULT_CONFIG)

    assert result.importance == Importance.IMPORTANT
    assert result.importance_match is not None
    assert result.importance_match.field == "serviceName"


def test_classification_never_important_precedence() -> None:
    result = classify_service("pub.foo:processService", "processService", DEFAULT_CONFIG)

    assert result.importance == Importance.LOW
    assert result.importance_match is not None
    assert result.importance_match.category == "neverImportant"


def test_classification_case_insensitive_matching() -> None:
    result = classify_service("DI.SALES.ADAPTER:createOrder", "createOrder", DEFAULT_CONFIG)

    assert result.importance == Importance.IMPORTANT


def test_classification_unmatched_normal_and_unknown_layer() -> None:
    result = classify_service("acme.orders:create", "create", DEFAULT_CONFIG)

    assert result.importance == Importance.NORMAL
    assert result.layer == "UNKNOWN"


def test_classification_layer_match() -> None:
    result = classify_service("acme.sales.channel:createOrder", "createOrder", DEFAULT_CONFIG)

    assert result.layer == "CHANNEL"
    assert result.layer_match is not None
    assert result.layer_match.pattern == "*.channel:*"
