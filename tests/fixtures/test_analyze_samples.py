from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from lxml import etree
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
from wm_doc.render.document_markdown import render_document_markdown
from wm_doc.render.dot import render_dependency_dot, render_document_dot
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
    assert first_call.id.startswith("call_")
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
        if service.service_type == "FLOW"
    }

    assert "pgp.services.encrypt:encryptString" in full_names
    assert "pgp.services.decrypt:decryptString" in full_names
    assert len(full_names) == 24


def test_static_dependencies_are_split_into_occurrences_and_unique_dependencies() -> None:
    analysis = _analysis()

    assert analysis.schema_version == "analysis.v6"
    assert analysis.metrics.call_occurrence_count == 108
    assert analysis.metrics.flow_call_occurrence_count == 108
    assert analysis.metrics.java_static_call_occurrence_count == 0
    assert analysis.metrics.java_dynamic_call_occurrence_count == 0
    assert analysis.metrics.total_call_occurrence_count == 108
    assert analysis.metrics.call_type_counts == {"INVOKE": 68, "MAPINVOKE": 40}
    assert analysis.metrics.resolved_call_occurrence_count == 49
    assert analysis.metrics.unresolved_call_occurrence_count == 59
    assert analysis.metrics.unique_dependency_count == 86
    assert analysis.metrics.flow_unique_dependency_count == 86
    assert analysis.metrics.java_unique_dependency_count == 0
    assert analysis.metrics.total_unique_dependency_count == 86
    assert analysis.metrics.unique_dependency_kind_counts == {
        "INVOKES": 61,
        "USES_TRANSFORMER": 25,
    }
    assert analysis.metrics.resolved_unique_dependency_count == 45
    assert analysis.metrics.unresolved_unique_dependency_count == 41
    assert analysis.extraction_policy.literal_mode == "redact"
    assert analysis.extraction_policy.free_text_mode == "include"
    assert analysis.extraction_policy.secret_guard.enabled is True
    assert analysis.extraction_policy.secret_guard.strategy_version == "secret-guard.v1"
    assert len(analysis.call_occurrences) == 108
    assert len(analysis.unique_dependencies) == 86
    assert all(call.id.startswith("call_") for call in analysis.call_occurrences)
    assert any(
        call.target == "pgp.services.registry:getPubKey"
        for call in analysis.call_occurrences
    )
    assert any(call.target == "pub.list:sizeOfList" for call in analysis.call_occurrences)
    assert any(
        dependency.occurrence_count > 1 for dependency in analysis.unique_dependencies
    )


def test_java_services_are_analyzed_source_first() -> None:
    analysis = _analysis()
    java_services = [
        service
        for package in analysis.packages
        for service in package.services
        if service.service_type == "JAVA"
    ]

    assert _independent_java_service_artifact_count() == 11
    assert len(java_services) == 11
    assert len(analysis.java_service_analyses) == 11
    assert analysis.metrics.java_service_analysis_count == 11
    assert analysis.metrics.java_source_match_count == 11
    assert analysis.metrics.java_source_only_count == 0
    assert analysis.metrics.java_fragment_only_count == 0
    assert analysis.metrics.java_source_mismatch_count == 0
    assert analysis.metrics.java_source_method_not_found_count == 0
    assert analysis.metrics.java_source_method_ambiguous_count == 0
    assert analysis.metrics.java_source_identity_mismatch_count == 0
    assert analysis.metrics.java_source_partial_parse_count == 0
    assert analysis.metrics.java_invocation_occurrence_count == 0

    source_paths = {
        analysis_record.source_set.complete_source_path
        for analysis_record in analysis.java_service_analyses
    }
    assert source_paths == {
        "PGP/code/source/pgp/services/common.java",
        "PGP/code/source/pgp/services/decrypt.java",
        "PGP/code/source/pgp/services/encrypt.java",
        "PGP/code/source/pgp/services/keys.java",
    }

    for analysis_record in analysis.java_service_analyses:
        source_set = analysis_record.source_set
        assert source_set.status == "SOURCE_AND_FRAGMENT_MATCH"
        assert source_set.parser_mode == "COMPLETE_SOURCE"
        assert source_set.token_match is True
        assert source_set.complete_source_path is not None
        assert source_set.fragment_path is not None
        assert source_set.matched_method == analysis_record.identity.name
        assert source_set.matched_class == analysis_record.identity.namespace.rsplit(".", 1)[-1]
        assert source_set.method_range is not None
        assert source_set.method_range.start_line > 0
        assert source_set.primary_source is not None
        assert source_set.primary_source.path == source_set.complete_source_path
        assert source_set.primary_source.class_name == source_set.matched_class
        assert source_set.primary_source.method_name == analysis_record.identity.name
        assert source_set.corroborating_source is not None
        assert source_set.corroborating_source.path == source_set.fragment_path
        assert all(
            helper.startswith("PGP/code/source/com/softwareag/pgp/")
            for helper in source_set.related_helper_sources
        )

    assert not any(
        service.identity.namespace.startswith("com.softwareag")
        for package in analysis.packages
        for service in package.services
    )


def test_java_pipeline_access_counts_and_scopes() -> None:
    analysis = _analysis()
    access_counts = Counter(access.access_kind.value for access in analysis.java_pipeline_accesses)
    scope_counts = Counter(
        (access.access_kind.value, access.cursor_scope.value)
        for access in analysis.java_pipeline_accesses
    )

    assert analysis.metrics.java_pipeline_access_count == 73
    assert analysis.metrics.java_pipeline_access_kind_counts == {
        "READ": 37,
        "WRITE": 36,
    }
    assert access_counts == {"READ": 37, "WRITE": 36}
    assert scope_counts == {
        ("READ", "ROOT_PIPELINE"): 34,
        ("READ", "NESTED_IDATA"): 3,
        ("WRITE", "ROOT_PIPELINE"): 21,
        ("WRITE", "NESTED_IDATA"): 15,
    }
    assert {
        access.field_key
        for access in analysis.java_pipeline_accesses
        if access.service == "pgp.services.decrypt:decryptAndVerify"
        and access.access_kind == "READ"
    } >= {"publicKeyRingCollection", "privateKeyRingCollection"}
    assert not any(access.access_kind == "REMOVE" for access in analysis.java_pipeline_accesses)
    assert all(
        access.source.primary.path.startswith("PGP/code/source/")
        for access in analysis.java_pipeline_accesses
    )
    assert all(
        access.source.primary.line is not None for access in analysis.java_pipeline_accesses
    )
    per_service = {
        record.identity.full_name: Counter(
            access.access_kind.value for access in record.pipeline_accesses
        )
        for record in analysis.java_service_analyses
    }
    assert per_service == {
        "pgp.services.common:getFileContent": {"READ": 2, "WRITE": 1},
        "pgp.services.common:getPackagePath": {"READ": 3, "WRITE": 1},
        "pgp.services.common:getSupportedEncodings": {"READ": 1, "WRITE": 3},
        "pgp.services.common:selectFromConfig": {"READ": 5, "WRITE": 1},
        "pgp.services.decrypt:decryptAndVerify": {"READ": 10, "WRITE": 5},
        "pgp.services.encrypt:encryptAndSign": {"READ": 12, "WRITE": 5},
        "pgp.services.keys:listEncryptionAlgorithms": {"WRITE": 1},
        "pgp.services.keys:listKeyExchangeAlgorithms": {"WRITE": 1},
        "pgp.services.keys:listSignatureAlgorithms": {"WRITE": 1},
        "pgp.services.keys:readPrivateKeys": {"READ": 2, "WRITE": 8},
        "pgp.services.keys:readPublicKeys": {"READ": 2, "WRITE": 9},
    }


def test_java_markdown_sections_are_rendered_without_source_bodies() -> None:
    service = _service("pgp.services.encrypt:encryptAndSign")
    markdown = render_service_markdown(service)

    assert "## Java Analysis" in markdown
    assert "### Source Consistency" in markdown
    assert "SOURCE_AND_FRAGMENT_MATCH" in markdown
    assert "### Observed Pipeline Reads" in markdown
    assert "### Observed Pipeline Writes" in markdown
    assert "### Static Integration Server Calls" in markdown
    assert "No Java Integration Server invocation sites were extracted" in markdown
    assert "### Declared Imports" in markdown
    assert "### Referenced Java Types" in markdown
    assert "public static final void" not in markdown
    assert "--- <<IS-START" not in markdown


def test_document_types_are_extracted_with_ordered_fields() -> None:
    analysis = _analysis()
    documents = {document.identity.full_name: document for document in analysis.document_types}

    assert analysis.metrics.document_type_count == 7
    assert analysis.metrics.document_field_count == 33
    assert set(documents) == {
        "pgp.documents.config:KeyConfig",
        "pgp.documents.config:PGPconfig",
        "pgp.documents:KeyRegData",
        "pgp.documents:PrivateKeyData",
        "pgp.documents:PubKeyRegEntry",
        "pgp.documents:PublicKeyData",
        "pgp.documents:SecKeyRegEntry",
    }

    top_counts = {
        name: len(document.fields) for name, document in sorted(documents.items())
    }
    assert top_counts == {
        "pgp.documents.config:KeyConfig": 3,
        "pgp.documents.config:PGPconfig": 2,
        "pgp.documents:KeyRegData": 4,
        "pgp.documents:PrivateKeyData": 7,
        "pgp.documents:PubKeyRegEntry": 2,
        "pgp.documents:PublicKeyData": 8,
        "pgp.documents:SecKeyRegEntry": 2,
    }

    key_config = documents["pgp.documents.config:KeyConfig"]
    assert [field.name for field in key_config.fields] == ["@userId", "pub", "sec"]
    assert [field.name for field in key_config.fields[1].children] == [
        "filename",
        "exchangeAlgorithm",
    ]
    assert key_config.fields[1].field_type == "RECORD"
    assert key_config.fields[1].dimension == "SCALAR"
    assert key_config.fields[1].technical_metadata["rec_closed"] == "true"

    pgp_config = documents["pgp.documents.config:PGPconfig"]
    nested_reference = pgp_config.fields[1].children[0]
    assert nested_reference.name == "keys"
    assert nested_reference.field_path == "keys/keys"
    assert nested_reference.raw_field_type == "recref"
    assert nested_reference.field_type == "DOCUMENT_REFERENCE"
    assert nested_reference.raw_dimension == "1"
    assert nested_reference.dimension == "LIST"
    assert nested_reference.document_reference == "pgp.documents.config:KeyConfig"


def test_document_reference_dependencies_are_resolved_exactly() -> None:
    analysis = _analysis()

    assert analysis.metrics.document_reference_occurrence_count == 12
    assert analysis.metrics.resolved_document_reference_count == 10
    assert analysis.metrics.unresolved_document_reference_count == 2
    assert analysis.metrics.unique_document_dependency_count == 5
    assert analysis.metrics.service_document_dependency_count == 7

    document_edges = {
        (dependency.source_document, dependency.target_document, dependency.resolved)
        for dependency in analysis.document_dependencies
    }
    assert document_edges == {
        ("pgp.documents.config:PGPconfig", "pgp.documents.config:KeyConfig", True),
        ("pgp.documents:PubKeyRegEntry", "pgp.documents:KeyRegData", True),
        ("pgp.documents:PubKeyRegEntry", "pgp.documents:PublicKeyData", True),
        ("pgp.documents:SecKeyRegEntry", "pgp.documents:KeyRegData", True),
        ("pgp.documents:SecKeyRegEntry", "pgp.documents:PrivateKeyData", True),
    }

    service_dependencies = {
        (
            dependency.service,
            dependency.target_document,
            dependency.usage_role.value,
            dependency.resolved,
        )
        for dependency in analysis.service_document_dependencies
    }
    assert (
        "oa.adapter.geographicAddressManagement:createGeographicAddressValidation",
        "oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:"
        "docCreateGeographicAddressValidationInput",
        "INPUT",
        False,
    ) in service_dependencies
    assert (
        "oa.adapter.geographicAddressManagement:createGeographicAddressValidation",
        "oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:"
        "docCreateGeographicAddressValidationOutput",
        "OUTPUT",
        False,
    ) in service_dependencies
    assert (
        "pgp.services.common:selectFromConfig",
        "pgp.documents.config:PGPconfig",
        "INPUT",
        True,
    ) in service_dependencies
    assert (
        "pgp.services.common:selectFromConfig",
        "pgp.documents.config:KeyConfig",
        "OUTPUT",
        True,
    ) in service_dependencies

    document_finding_codes = {
        finding.code
        for document in analysis.document_types
        for finding in document.findings
    }
    assert "MALFORMED_NESTED_RECORD" not in document_finding_codes
    assert "UNSUPPORTED_DOCUMENT_METADATA" not in document_finding_codes


def test_raw_document_and_spec_counts_are_independently_verified() -> None:
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    document_count = 0
    spec_count = 0
    for node_path in sorted(_samples().rglob("node.ndf")):
        root = etree.parse(str(node_path), parser).getroot()
        if _value_child(root, "svc_type") == "spec":
            spec_count += 1
        record = _record_child(root, "record")
        if record is not None and _value_child(record, "node_type") == "record":
            document_count += 1

    assert document_count == 7
    assert spec_count == 8


def test_mapping_operations_and_transformer_bindings_are_extracted() -> None:
    analysis = _analysis()
    service = _service(OA_FULL_NAME)

    assert analysis.metrics.flow_map_count == 265
    assert analysis.metrics.mapping_operation_count == 568
    assert analysis.metrics.mapping_operation_type_counts == {
        "COPY": 297,
        "DELETE": 178,
        "SET": 93,
    }
    assert analysis.metrics.transformer_binding_count == 198
    assert analysis.metrics.transformer_binding_direction_counts == {
        "FROM_TRANSFORMER": 66,
        "INTO_TRANSFORMER": 132,
    }

    assert service.metrics.flow_map_count == 135
    assert service.metrics.mapping_operation_count == 219
    assert service.metrics.mapping_operation_type_counts == {
        "COPY": 190,
        "DELETE": 8,
        "SET": 21,
    }
    assert service.metrics.transformer_binding_count == 168
    assert service.metrics.transformer_binding_direction_counts == {
        "FROM_TRANSFORMER": 56,
        "INTO_TRANSFORMER": 112,
    }

    assert sum(1 for flow_map in service.flow_maps if flow_map.source_schema) == 60
    assert sum(1 for flow_map in service.flow_maps if flow_map.target_schema) == 60
    assert all(operation.id.startswith("mapop_") for operation in service.mapping_operations)
    assert all(flow_map.id.startswith("map_") for flow_map in service.flow_maps)
    assert all(binding.id.startswith("bind_") for binding in service.transformer_bindings)

    set_operation = next(
        operation for operation in service.mapping_operations if operation.source.line == 118
    )
    assert set_operation.operation_type == "SET"
    assert set_operation.target_endpoint is not None
    assert set_operation.literal is not None
    assert set_operation.literal.declared_type == "string"
    assert set_operation.literal.length == 1
    assert set_operation.literal.disclosure == "REDACTED"
    assert set_operation.literal.value is None

    indexed_copy = next(
        operation
        for operation in service.mapping_operations
        if operation.source_endpoint and operation.source_endpoint.path.contains_index
    )
    assert indexed_copy.source.line == 3752
    assert indexed_copy.source_endpoint is not None
    assert indexed_copy.source_endpoint.raw_path.startswith("/geographicAddresses[0]")

    assert any(operation.operation_type == "DELETE" for operation in service.mapping_operations)

    first_binding = service.transformer_bindings[0]
    assert first_binding.direction == "INTO_TRANSFORMER"
    assert first_binding.call_occurrence_id.startswith("call_")
    assert first_binding.pipeline_endpoint is not None
    assert first_binding.transformer_endpoint is not None


def test_raw_xml_mapping_counts_are_independently_verified() -> None:
    tags = {
        "MAP",
        "MAPCOPY",
        "MAPSET",
        "MAPDELETE",
        "MAPSOURCE",
        "MAPTARGET",
        "DATA",
        "MAPINVOKE",
    }
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    counts: Counter[str] = Counter()
    for flow_path in sorted(_samples().rglob("flow.xml")):
        root = etree.parse(str(flow_path), parser).getroot()
        for element in root.iter():
            if isinstance(element.tag, str) and element.tag in tags:
                counts[element.tag] += 1

    assert counts == {
        "DATA": 93,
        "MAP": 265,
        "MAPCOPY": 297,
        "MAPDELETE": 178,
        "MAPINVOKE": 40,
        "MAPSET": 93,
        "MAPSOURCE": 150,
        "MAPTARGET": 150,
    }


def test_mapping_operation_ordering_fields_are_unambiguous() -> None:
    service = _service(OA_FULL_NAME)
    operations_by_id = {operation.id: operation for operation in service.mapping_operations}
    traversal_orders = [
        operation.document_traversal_order for operation in service.mapping_operations
    ]

    assert all(order is not None for order in traversal_orders)
    assert len(set(traversal_orders)) == len(traversal_orders)
    for flow_map in service.flow_maps:
        direct_orders = [
            operations_by_id[operation_id].map_operation_order
            for operation_id in flow_map.operation_ids
        ]
        assert direct_orders == list(range(1, len(direct_orders) + 1))

    earlier_nested = next(
        operation for operation in service.mapping_operations if operation.source.line == 5343
    )
    later_parent_direct = next(
        operation for operation in service.mapping_operations if operation.source.line == 5356
    )
    assert earlier_nested.order > later_parent_direct.order
    assert earlier_nested.document_traversal_order < later_parent_direct.document_traversal_order


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


def test_parsed_map_and_exit_constructs_do_not_emit_deferred_findings() -> None:
    service = _service(OA_FULL_NAME)
    finding_codes = {finding.code for finding in service.findings}
    messages = {finding.message for finding in service.findings}

    assert "MAP_OPERATION_DEFERRED" not in finding_codes
    assert "UNSUPPORTED_FLOW_ELEMENT" not in finding_codes
    assert not any("FLOW element MAP is observed" in message for message in messages)
    assert not any("FLOW element EXIT is observed" in message for message in messages)


def test_markdown_separates_calls_and_summarizes_mappings() -> None:
    markdown = render_service_markdown(_service(OA_FULL_NAME))

    assert "## Document Type Usage" in markdown
    assert "## FLOW Overview" in markdown
    assert "docCreateGeographicAddressValidationInput" in markdown
    assert "docCreateGeographicAddressValidationOutput" in markdown
    assert "## FLOW Overview" in markdown
    assert "## Mapping Overview" in markdown
    assert "## Mapping Copies" in markdown
    assert "## Mapping Sets" in markdown
    assert "## Transformer Bindings" in markdown
    assert "Transformer input bindings | 112" in markdown
    assert "Transformer output bindings | 56" in markdown
    assert "## Normal Service Dependencies" in markdown
    assert "## Transformer Dependencies" in markdown
    assert "## Call Occurrences" in markdown
    assert "## Transformer Call Occurrences" in markdown
    assert "<redacted:literal>" in markdown
    assert "`OK`" not in markdown
    assert "M4a extracts observed FLOW, mapping, document-reference, and Java Service" in markdown


def test_deterministic_analysis_json_markdown_and_dot() -> None:
    analysis = _analysis()
    service = _service(OA_FULL_NAME)
    document = analysis.document_types[0]

    assert render_analysis_json(analysis) == render_analysis_json(_analysis())
    assert render_service_markdown(service) == render_service_markdown(_service(OA_FULL_NAME))
    assert render_dependency_dot(analysis) == render_dependency_dot(_analysis())
    assert render_document_dot(analysis) == render_document_dot(_analysis())
    assert render_document_markdown(
        document,
        analysis.document_reference_occurrences,
        analysis.document_dependencies,
        analysis.service_document_dependencies,
        analysis.extraction_policy,
    ) == render_document_markdown(
        _analysis().document_types[0],
        _analysis().document_reference_occurrences,
        _analysis().document_dependencies,
        _analysis().service_document_dependencies,
        _analysis().extraction_policy,
    )


def test_canonical_outputs_have_relative_paths_and_no_source_xml() -> None:
    analysis = _analysis()
    payload = render_analysis_json(analysis)
    markdown = render_service_markdown(_service(OA_FULL_NAME))
    dot = render_dependency_dot(analysis)
    document_dot = render_document_dot(analysis)
    document_markdown = render_document_markdown(
        analysis.document_types[0],
        analysis.document_reference_occurrences,
        analysis.document_dependencies,
        analysis.service_document_dependencies,
        analysis.extraction_policy,
    )
    combined = payload + markdown + dot + document_dot + document_markdown

    assert "D:/Dev" not in combined
    assert "D:\\Dev" not in combined
    assert "<FLOW" not in combined
    assert "<Values" not in combined
    assert "analysis.v6" in payload
    assert "## Disclosure Policies" in document_markdown
    assert "- Free text mode: include" in document_markdown
    assert "- Literal mode: redact" in document_markdown
    assert "- Secret guard: enabled" in document_markdown
    assert "- Secret guard strategy: secret-guard.v1" in document_markdown

    data = json.loads(payload)
    source_paths = []
    for package in data["packages"]:
        for document in package["document_types"]:
            source_paths.append(document["source"]["path"])
            source_paths.extend(field["source"]["path"] for field in document["fields"])
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
    assert "Analyzed services:" in result.output
    assert "- FLOW: 24" in result.output
    assert "- Java: 11" in result.output
    assert "- total: 35" in result.output
    assert "Service call occurrences:" in result.output
    assert "- FLOW: 108" in result.output
    assert "- Java static: 0" in result.output
    assert "- Java dynamic/partial: 0" in result.output
    assert "- total promoted calls: 108" in result.output
    assert "Unique service dependencies:" in result.output
    assert "- FLOW-derived: 86" in result.output
    assert "- Java-derived: 0" in result.output
    assert "- total: 86" in result.output
    assert (output / "analysis.json").exists()
    assert (output / "graphs" / "dependencies.dot").exists()
    assert (output / "graphs" / "documents.dot").exists()
    assert len(list((output / "services").glob("*.md"))) == 35
    assert len(list((output / "documents").glob("*.md"))) == 7


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


def _value_child(element: etree._Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = _direct_named_child(element, "value", name)
    if child is None:
        return None
    return child.text


def _record_child(element: etree._Element | None, name: str) -> etree._Element | None:
    return _direct_named_child(element, "record", name)


def _direct_named_child(
    element: etree._Element | None, tag: str, name: str
) -> etree._Element | None:
    if element is None:
        return None
    for child in element:
        if isinstance(child.tag, str) and child.tag == tag and child.get("name") == name:
            return child
    return None


def _independent_java_service_artifact_count() -> int:
    parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
    count = 0
    for node_path in sorted(_samples().rglob("node.ndf")):
        root = etree.parse(str(node_path), parser).getroot()
        if _value_child(root, "svc_type") == "java" and (node_path.parent / "java.frag").exists():
            count += 1
    return count


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
