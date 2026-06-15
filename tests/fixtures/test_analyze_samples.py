from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import DEFAULT_CONFIG
from wm_doc.render.analysis_json import render_analysis_json
from wm_doc.render.dot import render_dependency_dot
from wm_doc.render.service_markdown import render_service_markdown

OA_FULL_NAME = "oa.adapter.geographicAddressManagement:createGeographicAddressValidation"


def test_primary_oaadapter_identity_signature_and_invokes() -> None:
    service = _service(OA_FULL_NAME)

    assert service.identity.package == "OAAdapter"
    assert service.identity.namespace == "oa.adapter.geographicAddressManagement"
    assert service.identity.name == "createGeographicAddressValidation"
    assert service.identity.basis == "RECONSTRUCTED"
    assert service.service_type == "FLOW"

    assert len(service.signature.inputs) == 1
    input_field = service.signature.inputs[0]
    assert input_field.name == "input"
    assert input_field.data_type == "recref"
    assert input_field.dimensions == 0
    assert input_field.document_reference == (
        "oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:"
        "docCreateGeographicAddressValidationInput"
    )

    assert len(service.signature.outputs) == 1
    output_field = service.signature.outputs[0]
    assert output_field.name == "output"
    assert output_field.data_type == "recref"
    assert output_field.document_reference == (
        "oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:"
        "docCreateGeographicAddressValidationOutput"
    )

    assert len(service.invokes) == 43
    assert service.invokes[0].target == "pub.list:sizeOfList"
    assert service.invokes[0].parent_containers[:2] == ["c0001", "c0002"]
    assert service.invokes[0].source.line == 450
    assert len(service.dependencies) == 43
    assert len(service.unresolved_dependencies) == 43


def test_pgp_flow_services_are_processed_by_same_parser() -> None:
    analysis = _analysis()
    full_names = {
        service.identity.full_name
        for package in analysis.packages
        for service in package.services
    }

    assert "pgp.services.encrypt:encryptString" in full_names
    assert "pgp.services.decrypt:decryptString" in full_names
    assert len(full_names) == 24


def test_static_dependencies_are_resolved_and_unresolved() -> None:
    analysis = _analysis()

    assert len(analysis.edges) == 108
    assert sum(1 for edge in analysis.edges if edge.resolved) == 49
    assert len(analysis.unresolved_dependencies) == 59
    assert any(edge.target_service == "pgp.services.registry:getPubKey" for edge in analysis.edges)
    assert any(edge.target_service == "pub.list:sizeOfList" for edge in analysis.edges)


def test_low_dependency_target_is_retained_in_graph() -> None:
    analysis = _analysis()
    edge = next(edge for edge in analysis.edges if edge.target_service == "pub.list:sizeOfList")
    dot = render_dependency_dot(analysis)

    assert edge.target_classification.importance == "LOW"
    assert "pub.list:sizeOfList" in dot


def test_unknown_flow_elements_create_findings() -> None:
    service = _service(OA_FULL_NAME)
    codes = {finding.code for finding in service.findings}
    messages = {finding.message for finding in service.findings}

    assert "UNSUPPORTED_FLOW_ELEMENT" in codes
    assert any("MAP" in message for message in messages)


def test_deterministic_analysis_json_markdown_and_dot() -> None:
    analysis = _analysis()
    service = _service(OA_FULL_NAME)

    assert render_analysis_json(analysis) == render_analysis_json(_analysis())
    assert render_service_markdown(service) == render_service_markdown(_service(OA_FULL_NAME))
    assert render_dependency_dot(analysis) == render_dependency_dot(_analysis())


def test_canonical_outputs_have_relative_paths_and_no_source_xml() -> None:
    analysis = _analysis()
    payload = render_analysis_json(analysis)
    markdown = render_service_markdown(_service(OA_FULL_NAME))
    dot = render_dependency_dot(analysis)
    combined = payload + markdown + dot

    assert "D:/Dev" not in combined
    assert "D:\\Dev" not in combined
    assert "<FLOW" not in combined
    assert "<Values" not in combined

    data = json.loads(payload)
    source_paths = []
    for package in data["packages"]:
        for service in package["services"]:
            source_paths.append(service["source"]["path"])
            source_paths.extend(field["source"]["path"] for field in service["signature"]["inputs"])
            source_paths.extend(
                field["source"]["path"] for field in service["signature"]["outputs"]
            )
    assert source_paths
    assert all("\\" not in path for path in source_paths)
    assert all(":" not in path for path in source_paths)


def test_analyze_cli_writes_expected_outputs(tmp_path) -> None:
    output = tmp_path / "analysis"
    result = CliRunner().invoke(app, ["analyze", str(_samples()), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert (output / "analysis.json").exists()
    assert (output / "graphs" / "dependencies.dot").exists()
    assert len(list((output / "services").glob("*.md"))) == 24


def test_pgp_and_oaadapter_fixture_formats_differ() -> None:
    oa = _service(OA_FULL_NAME)
    pgp = _service("pgp.services.encrypt:encryptString")

    assert any(container.type == "LOOP" for container in oa.containers)
    assert not any(container.type == "LOOP" for container in pgp.containers)
    assert len(oa.invokes) > len(pgp.invokes)


def _analysis():
    return analyze_path(_samples(), DEFAULT_CONFIG)


def _service(full_name: str):
    for package in _analysis().packages:
        for service in package.services:
            if service.identity.full_name == full_name:
                return service
    raise AssertionError(f"Service not found: {full_name}")


def _samples() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"
