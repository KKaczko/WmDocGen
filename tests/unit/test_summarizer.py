"""Shared prompt helpers: call-graph order, pseudo-code view, context fitting, grounding."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from wm_doc.analysis import analyze_path
from wm_doc.callgraph import summary_order
from wm_doc.config import load_config
from wm_doc.ir import AnalysisResult, FlowService
from wm_doc.pseudocode import load_flow_comments, render_pseudocode
from wm_doc.summarizer import DEFAULT_NUM_PREDICT, fit_facts, unknown_names

SAMPLES = Path("samples")
READ_CONFIG = "pgp.services.common:readConfig"
SELECT_FROM_CONFIG = "pgp.services.common:selectFromConfig"
OA_SERVICE = "oa.adapter.geographicAddressManagement:createGeographicAddressValidation"


@pytest.fixture(scope="module")
def analysis() -> AnalysisResult:
    return analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)


@pytest.fixture(scope="module")
def services(analysis: AnalysisResult) -> dict[str, FlowService]:
    return {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }


def test_summary_order_puts_callees_before_callers(services: dict[str, FlowService]) -> None:
    order = summary_order(services.values())

    assert sorted(order) == sorted(services)
    position = {name: index for index, name in enumerate(order)}
    for service in services.values():
        for dependency in service.unique_dependencies:
            if dependency.resolved and dependency.target_service in services:
                assert position[dependency.target_service] < position[service.identity.full_name]


def _fake_service(name: str, *targets: str) -> Any:
    dependencies = [SimpleNamespace(target_service=target, resolved=True) for target in targets]
    return SimpleNamespace(
        identity=SimpleNamespace(full_name=name), unique_dependencies=dependencies
    )


def test_summary_order_handles_cycles_deterministically() -> None:
    graph = [
        _fake_service("a:entry", "b:loopOne"),
        _fake_service("b:loopOne", "c:loopTwo"),
        _fake_service("c:loopTwo", "b:loopOne", "d:leaf"),
        _fake_service("d:leaf"),
    ]

    order = summary_order(graph)

    assert order == ["d:leaf", "b:loopOne", "c:loopTwo", "a:entry"]
    assert summary_order(list(reversed(graph))) == order


def test_pseudocode_shows_calls_literals_and_callee_notes(
    services: dict[str, FlowService],
) -> None:
    notes = {SELECT_FROM_CONFIG: "Selects the key entry for a user."}

    text = render_pseudocode(services[READ_CONFIG], notes.get)

    assert text.startswith(f"service {READ_CONFIG}  [FLOW]")
    assert "  userId: string" in text
    assert "CALL pub.file:getFile  # platform: reads a file" in text
    assert 'in: set /filename = "./packages/PGP/config/config.xml"' in text
    assert f"CALL {SELECT_FROM_CONFIG}  # Selects the key entry for a user." in text


def test_pseudocode_shows_try_catch_conditions_and_comments(
    services: dict[str, FlowService],
) -> None:
    config = load_config(None)
    oa = services[OA_SERVICE]
    oa_comments = load_flow_comments(SAMPLES, oa, config)
    oa_text = render_pseudocode(oa, lambda _: None, comments=oa_comments)
    test_service = services["pgp.test.encrypt:testEncryptAndSignString"]
    test_text = render_pseudocode(
        test_service,
        lambda _: None,
        comments=load_flow_comments(SAMPLES, test_service, config),
    )

    assert "TRY:" in oa_text and "CATCH:" in oa_text
    assert "when %input/geographicAddressValidation/status% == $null:" in oa_text
    assert "# outside the analysed packages" in oa_text
    assert "(stops at the first child that succeeds)  // Try / Catch" in test_text
    assert "// Sending a message from Alice to Bob" in test_text


def test_pseudocode_names_declared_external_systems(services: dict[str, FlowService]) -> None:
    def external(target: str) -> str | None:
        return "OA core" if target.startswith("oa.adapter.services.") else None

    text = render_pseudocode(services[OA_SERVICE], lambda _: None, external_note=external)

    assert "declared external system OA core" in text


def test_pseudocode_for_java_service_states_what_is_not_analysed(
    services: dict[str, FlowService],
) -> None:
    text = render_pseudocode(services["pgp.services.decrypt:decryptAndVerify"], lambda _: None)

    assert "implementation: Java" in text
    assert "reads pipeline fields: cipherTextPath" in text
    assert "(Java control flow and error handling are not analysed)" in text


def test_fit_facts_shrinks_large_services_to_the_window(
    services: dict[str, FlowService],
) -> None:
    oa = services[OA_SERVICE]

    roomy, roomy_shortened = fit_facts(oa, lambda _: None, {}, 32768)
    tight, tight_shortened = fit_facts(oa, lambda _: None, {}, 4096)

    assert not roomy_shortened
    assert tight_shortened
    assert len(tight) < len(roomy)
    assert len(tight) <= (4096 - DEFAULT_NUM_PREDICT) * 3
    assert tight.endswith("to fit the model's context window)")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Reads the config with `pgp.services.common:readConfig`.", []),
        ("It returns the KeyConfig document for a userId, e.g. via XML.", []),
        ("It copies /body/string into /xmldata.", []),
        ("It looks up user IDs and URLs, then handles I/O errors.", []),
        ("It reads config.xml for public/private key encryption/decryption.", []),
        ("It reads secret.xml.", ["secret.xml"]),
        ("It writes to backup/Archive.", ["backup/Archive"]),
        ("It then calls pgp.services.common:deleteConfig.", ["pgp.services.common:deleteConfig"]),
        ("It stores the result in customerAccount.", ["customerAccount"]),
    ],
)
def test_unknown_names_flags_only_names_missing_from_facts(
    services: dict[str, FlowService], text: str, expected: list[str]
) -> None:
    facts = render_pseudocode(services[READ_CONFIG], lambda _: None)

    assert unknown_names(text, facts) == expected
