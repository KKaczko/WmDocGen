from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis import analyze_path
from wm_doc.cli import app
from wm_doc.config import DEFAULT_CONFIG, classify_service
from wm_doc.ir import (
    AnalysisMetrics,
    ClassificationResult,
    FactBasis,
    FlowNode,
    FlowService,
    ServiceIdentity,
    ServiceSignature,
    SourceReference,
)
from wm_doc.render.analysis_json import render_analysis_json
from wm_doc.render.dot import render_dependency_dot
from wm_doc.render.service_markdown import render_service_markdown, write_service_markdown

OA_FULL_NAME = "oa.adapter.geographicAddressManagement:createGeographicAddressValidation"


def test_primary_oaadapter_identity_signature_and_call_model() -> None:
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
    assert input_field.source.line is not None

    assert len(service.signature.outputs) == 1
    output_field = service.signature.outputs[0]
    assert output_field.name == "output"
    assert output_field.data_type == "recref"
    assert output_field.document_reference == (
        "oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:"
        "docCreateGeographicAddressValidationOutput"
    )

    assert len(service.call_occurrences) == 43
    assert Counter(call.call_type.value for call in service.call_occurrences) == {
        "INVOKE": 13,
        "MAPINVOKE": 30,
    }
    first_call = service.call_occurrences[0]
    assert first_call.target == "pub.list:sizeOfList"
    assert first_call.call_type == "MAPINVOKE"
    assert first_call.dependency_kind == "USES_TRANSFORMER"
    assert first_call.parent_flow_path[:2] == ["fn0001", "fn0002"]
    assert first_call.source.line == 450

    assert len(service.unique_dependencies) == 25
    unique_kind_counts = Counter(
        dependency.dependency_kind.value for dependency in service.unique_dependencies
    )
    assert unique_kind_counts == {
        "INVOKES": 6,
        "USES_TRANSFORMER": 19,
    }
    assert service.metrics.call_occurrence_count == 43
    assert service.metrics.unique_dependency_count == 25


def test_oaadapter_flow_tree_counts_and_observed_attributes() -> None:
    service = _service(OA_FULL_NAME)
    assert service.flow_tree is not None

    assert service.metrics.flow_node_counts == {
        "BRANCH": 27,
        "BRANCH_CASE": 45,
        "EXIT": 9,
        "FLOW": 1,
        "INVOKE": 13,
        "LOOP": 2,
        "MAP": 135,
        "MAPINVOKE": 30,
        "SEQUENCE": 32,
    }

    sequences = _nodes(service.flow_tree, "SEQUENCE")
    branches = _nodes(service.flow_tree, "BRANCH")
    loops = _nodes(service.flow_tree, "LOOP")
    exits = _nodes(service.flow_tree, "EXIT")
    branch_cases = _nodes(service.flow_tree, "BRANCH_CASE")

    assert len(sequences) == 32
    assert any(sequence.exit_on == "FAILURE" for sequence in sequences)
    assert any(sequence.form == "TRY" for sequence in sequences)
    assert len(branches) == 27
    assert any(branch.switch for branch in branches)
    assert any(branch.evaluate_labels is True for branch in branches)
    assert any(case.is_default_case for case in branch_cases)
    assert len(loops) == 2
    assert any(loop.in_array == "/geographicAddresses" for loop in loops)
    assert len(exits) == 9
    assert all(exit_node.signal == "SUCCESS" for exit_node in exits)
    assert all(exit_node.exit_from for exit_node in exits)
    assert [exit_node.source.line for exit_node in exits] == [
        1400,
        2346,
        4926,
        7793,
        10280,
        11461,
        12467,
        13830,
        19833,
    ]


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


def test_static_dependencies_are_split_into_occurrences_and_unique_dependencies() -> None:
    analysis = _analysis()

    assert analysis.schema_version == "analysis.v2"
    assert analysis.metrics.call_occurrence_count == 108
    assert analysis.metrics.call_type_counts == {"INVOKE": 68, "MAPINVOKE": 40}
    assert analysis.metrics.resolved_call_occurrence_count == 49
    assert analysis.metrics.unresolved_call_occurrence_count == 59
    assert analysis.metrics.unique_dependency_count == 86
    assert analysis.metrics.unique_dependency_kind_counts == {
        "INVOKES": 61,
        "USES_TRANSFORMER": 25,
    }
    assert analysis.metrics.resolved_unique_dependency_count == 45
    assert analysis.metrics.unresolved_unique_dependency_count == 41
    assert len(analysis.call_occurrences) == 108
    assert len(analysis.unique_dependencies) == 86
    assert any(
        call.target == "pgp.services.registry:getPubKey"
        for call in analysis.call_occurrences
    )
    assert any(call.target == "pub.list:sizeOfList" for call in analysis.call_occurrences)
    assert any(
        dependency.occurrence_count > 1 for dependency in analysis.unique_dependencies
    )


def test_low_dependency_target_is_retained_in_graph() -> None:
    analysis = _analysis()
    dependency = next(
        dependency
        for dependency in analysis.unique_dependencies
        if dependency.target_service == "pub.list:sizeOfList"
    )
    dot = render_dependency_dot(analysis)

    assert dependency.target_classification.importance == "LOW"
    assert "pub.list:sizeOfList" in dot
    assert "USES_TRANSFORMER" in dot
    assert 'occurrences="' in dot


def test_deferred_map_findings_are_explicit_without_generic_map_or_exit_findings() -> None:
    service = _service(OA_FULL_NAME)
    messages = {finding.message for finding in service.findings}

    assert {finding.code for finding in service.findings} == {"MAP_OPERATION_DEFERRED"}
    assert any("MAPCOPY" in message for message in messages)
    assert not any("FLOW element MAP is observed" in message for message in messages)
    assert not any("FLOW element EXIT is observed" in message for message in messages)


def test_markdown_separates_service_and_transformer_calls() -> None:
    markdown = render_service_markdown(_service(OA_FULL_NAME))

    assert "## FLOW Overview" in markdown
    assert "## Normal Service Dependencies" in markdown
    assert "## Transformer Dependencies" in markdown
    assert "## Call Occurrences" in markdown
    assert "## Transformer Call Occurrences" in markdown
    assert "MAP data-flow semantics" in markdown


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

    assert oa.metrics.flow_node_counts["LOOP"] == 2
    assert pgp.metrics.flow_node_counts.get("LOOP", 0) == 0
    assert len(oa.call_occurrences) > len(pgp.call_occurrences)


def test_service_markdown_filename_collisions_are_disambiguated(tmp_path) -> None:
    services = [
        _minimal_service("pkg.alpha:beta"),
        _minimal_service("pkg.alpha_beta"),
    ]

    paths = write_service_markdown(tmp_path, services)

    assert len(paths) == 2
    assert len({path.name for path in paths}) == 2
    assert all(path.exists() for path in paths)


def _analysis():
    return analyze_path(_samples(), DEFAULT_CONFIG)


def _service(full_name: str):
    for package in _analysis().packages:
        for service in package.services:
            if service.identity.full_name == full_name:
                return service
    raise AssertionError(f"Service not found: {full_name}")


def _nodes(root: FlowNode, node_type: str) -> list[FlowNode]:
    nodes = [root] if root.type.value == node_type else []
    for child in root.children:
        nodes.extend(_nodes(child, node_type))
    return nodes


def _minimal_service(full_name: str) -> FlowService:
    name = full_name.rsplit(":", 1)[-1]
    classification: ClassificationResult = classify_service(full_name, name, DEFAULT_CONFIG)
    source = SourceReference(path="samples/Pkg/ns/pkg/service/node.ndf")
    return FlowService(
        identity=ServiceIdentity(
            package="Pkg",
            namespace="pkg",
            name=name,
            full_name=full_name,
            basis=FactBasis.RECONSTRUCTED,
            source=source,
        ),
        signature=ServiceSignature(source=source),
        classification=classification,
        metrics=AnalysisMetrics(),
        source=source,
    )


def _samples() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"
