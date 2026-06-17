from __future__ import annotations

import base64
from collections import Counter
from pathlib import Path

from wm_doc.analysis import analyze_path
from wm_doc.config import DEFAULT_CONFIG
from wm_doc.render.analysis_json import render_analysis_json

BASE_BODY = """
IDataCursor pc = pipeline.getCursor();
String input = IDataUtil.getString(pc, "input");
IDataUtil.put(pc, "output", input);
pc.destroy();
"""
VALID_SIGNATURE = "public static final void doIt (IData pipeline) throws ServiceException"


def test_java_source_statuses_and_fragment_fallbacks(tmp_path: Path) -> None:
    cases = [
        ("match", True, True, BASE_BODY, BASE_BODY, "SOURCE_AND_FRAGMENT_MATCH", "input"),
        ("source_only", True, False, BASE_BODY, None, "SOURCE_ONLY", "input"),
        ("fragment_only", False, True, None, BASE_BODY, "FRAGMENT_ONLY", "input"),
        (
            "mismatch",
            True,
            True,
            BASE_BODY.replace('"input"', '"sourceOnly"'),
            BASE_BODY.replace('"input"', '"fragmentOnly"'),
            "SOURCE_FRAGMENT_MISMATCH",
            "fragmentOnly",
        ),
        (
            "method_missing",
            True,
            True,
            _java_method("otherService", BASE_BODY),
            BASE_BODY,
            "SOURCE_METHOD_NOT_FOUND",
            "input",
        ),
        (
            "ambiguous",
            True,
            True,
            _java_method("doIt", BASE_BODY)
            + _java_method("doIt", BASE_BODY.replace('"input"', '"otherInput"')),
            BASE_BODY,
            "SOURCE_METHOD_AMBIGUOUS",
            "input",
        ),
        (
            "identity_mismatch",
            True,
            True,
            BASE_BODY,
            BASE_BODY,
            "SOURCE_IDENTITY_MISMATCH",
            "input",
        ),
    ]

    for name, write_source, write_frag, source_body, frag_body, status, expected_key in cases:
        root = tmp_path / name
        _write_java_metadata(root, "javaSvc", "doIt", frag_body, write_frag=write_frag)
        if write_source:
            if name == "identity_mismatch":
                _write_java_source(
                    root,
                    "javaSvc",
                    _java_method("doIt", source_body or BASE_BODY),
                    package_name="wrong.pkg",
                    class_name="WrongClass",
                )
            elif source_body and source_body.lstrip().startswith("public "):
                _write_java_source(root, "javaSvc", source_body)
            else:
                _write_java_source(root, "javaSvc", _java_method("doIt", source_body or BASE_BODY))

        record = _java_record(root, "pkg.services.javaSvc:doIt")

        assert record.source_set.status == status
        if status == "SOURCE_AND_FRAGMENT_MATCH":
            assert record.source_set.parser_mode == "COMPLETE_SOURCE"
            assert record.source_set.token_match is True
        elif status == "SOURCE_ONLY":
            assert record.source_set.parser_mode == "COMPLETE_SOURCE"
            assert record.source_set.fragment_path is None
        else:
            assert record.source_set.parser_mode == "FRAGMENT_FALLBACK"
        assert any(access.field_key == expected_key for access in record.pipeline_accesses)


def test_java_service_method_authority_requires_supported_signature(tmp_path: Path) -> None:
    cases = [
        ("valid_short_idata", VALID_SIGNATURE, "SOURCE_AND_FRAGMENT_MATCH", False),
        (
            "valid_fq_idata",
            "public final static void doIt (com.wm.data.IData pipeline) throws ServiceException",
            "SOURCE_AND_FRAGMENT_MATCH",
            False,
        ),
        (
            "valid_annotated_idata",
            "public static final void doIt (@Nullable IData pipeline) throws ServiceException",
            "SOURCE_AND_FRAGMENT_MATCH",
            False,
        ),
        (
            "wrong_object",
            "public static final void doIt (Object pipeline) throws ServiceException",
            "SOURCE_METHOD_NOT_FOUND",
            True,
        ),
        (
            "wrong_parameter_count",
            "public static final void doIt (IData pipeline, IData second) "
            "throws ServiceException",
            "SOURCE_METHOD_NOT_FOUND",
            True,
        ),
        (
            "wrong_return",
            "public static final String doIt (IData pipeline) throws ServiceException",
            "SOURCE_METHOD_NOT_FOUND",
            True,
        ),
        (
            "non_static",
            "public final void doIt (IData pipeline) throws ServiceException",
            "SOURCE_METHOD_NOT_FOUND",
            True,
        ),
        (
            "idata_array",
            "public static final void doIt (IData[] pipeline) throws ServiceException",
            "SOURCE_METHOD_NOT_FOUND",
            True,
        ),
        (
            "idata_varargs",
            "public static final void doIt (IData... pipeline) throws ServiceException",
            "SOURCE_METHOD_NOT_FOUND",
            True,
        ),
    ]
    for name, signature, status, unsupported in cases:
        root = tmp_path / name
        _write_java_metadata(root, "javaSvc", "doIt", BASE_BODY)
        _write_java_source(root, "javaSvc", _java_method("doIt", BASE_BODY, signature=signature))

        record = _java_record(root, "pkg.services.javaSvc:doIt")

        assert record.source_set.status == status
        assert [access.field_key for access in record.pipeline_accesses] == ["input", "output"]
        codes = {finding.code for finding in record.findings}
        if unsupported:
            assert record.source_set.parser_mode == "FRAGMENT_FALLBACK"
            assert "JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED" in codes
            assert record.source_set.status != "SOURCE_AND_FRAGMENT_MATCH"
        else:
            assert record.source_set.parser_mode == "COMPLETE_SOURCE"
            assert "JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED" not in codes


def test_java_service_method_authority_handles_wrong_nested_and_ambiguous_methods(
    tmp_path: Path,
) -> None:
    one_valid_root = tmp_path / "wrong_plus_valid"
    _write_java_metadata(one_valid_root, "javaSvc", "doIt", BASE_BODY)
    _write_java_source(
        one_valid_root,
        "javaSvc",
        _java_method(
            "doIt",
            BASE_BODY.replace('"input"', '"wrongObject"'),
            signature="public static final void doIt (Object pipeline) throws ServiceException",
        )
        + _java_method("doIt", BASE_BODY),
    )
    one_valid = _java_record(one_valid_root, "pkg.services.javaSvc:doIt")
    assert one_valid.source_set.status == "SOURCE_AND_FRAGMENT_MATCH"
    assert [access.field_key for access in one_valid.pipeline_accesses] == ["input", "output"]

    ambiguous_root = tmp_path / "ambiguous_compatible"
    _write_java_metadata(ambiguous_root, "javaSvc", "doIt", BASE_BODY)
    _write_java_source(
        ambiguous_root,
        "javaSvc",
        _java_method("doIt", BASE_BODY)
        + _java_method(
            "doIt",
            BASE_BODY.replace('"input"', '"otherInput"'),
            signature=(
                "public static final void doIt (com.wm.data.IData pipeline) "
                "throws ServiceException"
            ),
        ),
    )
    ambiguous = _java_record(ambiguous_root, "pkg.services.javaSvc:doIt")
    assert ambiguous.source_set.status == "SOURCE_METHOD_AMBIGUOUS"
    assert "JAVA_SOURCE_METHOD_AMBIGUOUS" in {finding.code for finding in ambiguous.findings}
    assert any(access.field_key == "input" for access in ambiguous.pipeline_accesses)

    nested_root = tmp_path / "nested_same_name"
    _write_java_metadata(nested_root, "javaSvc", "doIt", BASE_BODY)
    _write_java_source(
        nested_root,
        "javaSvc",
        """
public static class Inner {
  public static final void doIt (IData pipeline) throws ServiceException
  {
    IDataCursor pc = pipeline.getCursor();
    IDataUtil.put(pc, "nestedOnly", "x");
  }
}
""",
    )
    nested = _java_record(nested_root, "pkg.services.javaSvc:doIt")
    assert nested.source_set.status == "SOURCE_METHOD_NOT_FOUND"
    assert [access.field_key for access in nested.pipeline_accesses] == ["input", "output"]

    anonymous_root = tmp_path / "anonymous_same_name"
    _write_java_metadata(anonymous_root, "javaSvc", "doIt", BASE_BODY)
    _write_java_source(
        anonymous_root,
        "javaSvc",
        """
Object holder = new Object() {
  public static final void doIt (IData pipeline) throws ServiceException
  {
    IDataCursor pc = pipeline.getCursor();
    IDataUtil.put(pc, "anonymousOnly", "x");
  }
};
""",
    )
    anonymous = _java_record(anonymous_root, "pkg.services.javaSvc:doIt")
    assert anonymous.source_set.status == "SOURCE_METHOD_NOT_FOUND"
    assert [access.field_key for access in anonymous.pipeline_accesses] == ["input", "output"]


def test_java_method_scope_ignores_siblings_comments_strings_and_helpers(tmp_path: Path) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
// IDataUtil.getString(pc, "commentOnly");
String fake = "IDataUtil.getString(pc, \\"stringOnly\\");"
        + " Service.doInvoke(\\"pkg:svc\\", pipeline)";
String input = IDataUtil.getString(pc, "input");
IDataUtil.put(pc, "output", input);
pc.destroy();
"""
    sibling_body = """
IDataCursor pc = pipeline.getCursor();
IDataUtil.put(pc, "siblingOnly", "x");
Service.doInvoke("pkg.services.flow:targetFlow", pipeline);
pc.destroy();
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_source(
        tmp_path,
        "javaSvc",
        _java_method("doIt", body) + _java_method("sibling", sibling_body),
    )
    helper = tmp_path / "Pkg" / "code" / "source" / "com" / "example" / "Helper.java"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("package com.example; public class Helper {}\n", encoding="utf-8")

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    record = _java_record(tmp_path, "pkg.services.javaSvc:doIt")

    assert [access.field_key for access in record.pipeline_accesses] == ["input", "output"]
    assert record.invocation_occurrences == []
    assert not any(
        service.identity.namespace.startswith("com.example")
        for package in analysis.packages
        for service in package.services
    )
    assert "Pkg/code/source/com/example/Helper.java" in record.source_set.related_helper_sources


def test_java_nested_executable_bodies_are_not_promoted(tmp_path: Path) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
String real = IDataUtil.getString(pc, "real");
Runnable blockLambda = () -> {
    IDataUtil.getString(pc, "lambdaRead");
    IDataUtil.put(pc, "lambdaWrite", real);
    Service.doInvoke("pkg.services.flow:nestedTarget", pipeline);
};
Supplier<String> expressionLambda = () -> IDataUtil.getString(pc, "exprLambda");
Runnable anonymous = new Runnable() {
    public void run() {
        IDataUtil.put(pc, "anonymousWrite", real);
        Service.doInvoke("pkg.services.flow:anonymousTarget", pipeline);
    }
};
Object callback = new SomeType("callbackLiteral") {
    void callback() {
        Service.doInvoke("pkg.services.flow:callbackTarget", pipeline);
    }
};
Object plain = new SomeType();
{
    IDataUtil.put(pc, "unrelatedBlockWrite", real);
}
class LocalWorker {
    void run() {
        IDataUtil.put(pc, "localClassWrite", real);
        Service.doInvoke("pkg.services.flow:localTarget", pipeline);
    }
}
IDataUtil.put(pc, "directWrite", real);
Service.doInvoke("pkg.services.flow:targetFlow", pipeline);
pc.destroy();
"""
    imports = """
import com.wm.app.b2b.server.Service;
import com.wm.data.IData;
import com.wm.data.IDataCursor;
import com.wm.data.IDataUtil;
import java.util.function.Supplier;
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_source(tmp_path, "javaSvc", _java_method("doIt", body), imports=imports)
    _write_flow_service(tmp_path, "pkg", "services", "flow", service_name="targetFlow")

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    service = _service(analysis, "pkg.services.javaSvc:doIt")
    record = service.java_analysis
    assert record is not None

    assert [access.field_key for access in record.pipeline_accesses] == [
        "real",
        "unrelatedBlockWrite",
        "directWrite",
    ]
    assert [invocation.canonical_target for invocation in record.invocation_occurrences] == [
        "pkg.services.flow:targetFlow"
    ]
    assert [call.target for call in service.call_occurrences] == [
        "pkg.services.flow:targetFlow"
    ]
    assert [dependency.target_service for dependency in service.unique_dependencies] == [
        "pkg.services.flow:targetFlow"
    ]
    dot = _dependency_dot_edges(analysis)
    assert dot.count(" -> ") == 1
    assert "pkg.services.flow:nestedTarget" not in dot
    assert "pkg.services.flow:anonymousTarget" not in dot
    assert "pkg.services.flow:callbackTarget" not in dot
    assert "pkg.services.flow:localTarget" not in dot

    findings = [
        finding
        for finding in record.findings
        if finding.code == "JAVA_NESTED_EXECUTABLE_BODY_SKIPPED"
    ]
    assert {finding.severity for finding in findings} == {"INFO"}
    assert any("LAMBDA" in finding.message for finding in findings)
    assert any("ANONYMOUS_CLASS" in finding.message for finding in findings)
    assert any("LOCAL_CLASS" in finding.message for finding in findings)
    messages = " ".join(finding.message for finding in findings)
    assert "lambdaRead" not in messages
    assert "anonymousWrite" not in messages
    assert "callbackLiteral" not in messages
    assert "localClassWrite" not in messages


def test_java_array_creation_and_enhanced_for_are_normal_service_flow(
    tmp_path: Path,
) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
for (String item : new String[] {"arrayLiteralSecret"}) {
    IDataUtil.put(pc, "enhancedForWrite", item);
}
for (int item : new int[] {1, 2}) {
    IDataUtil.put(pc, "primitiveArrayWrite", item);
}
Object[] values = new Object[] {new Object()};
for (Object value : values) {
    IDataUtil.put(pc, "variableArrayWrite", value);
}
for (String item : java.util.List.of("collectionLiteralSecret")) {
    IDataUtil.put(pc, "expressionWrite", item);
}
Object[] sized = new Object[10];
IDataUtil.put(pc, "sizedArrayWrite", sized);
Object[][] matrix = new Object[2][3];
IDataUtil.put(pc, "matrixArrayWrite", matrix);
Object[] empty = new Object[] {};
IDataUtil.put(pc, "emptyArrayWrite", empty);
Object[][] nestedEmpty = new Object[][] {{}};
IDataUtil.put(pc, "nestedArrayWrite", nestedEmpty);
Object[] constructed = new Object[] {new Object()};
IDataUtil.put(pc, "constructedArrayWrite", constructed);
pc.destroy();
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_source(tmp_path, "javaSvc", _java_method("doIt", body))

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    record = _java_record(tmp_path, "pkg.services.javaSvc:doIt")
    accesses = [
        (access.access_kind.value, access.field_key, access.cursor_scope.value)
        for access in record.pipeline_accesses
    ]

    assert accesses == [
        ("WRITE", "enhancedForWrite", "ROOT_PIPELINE"),
        ("WRITE", "primitiveArrayWrite", "ROOT_PIPELINE"),
        ("WRITE", "variableArrayWrite", "ROOT_PIPELINE"),
        ("WRITE", "expressionWrite", "ROOT_PIPELINE"),
        ("WRITE", "sizedArrayWrite", "ROOT_PIPELINE"),
        ("WRITE", "matrixArrayWrite", "ROOT_PIPELINE"),
        ("WRITE", "emptyArrayWrite", "ROOT_PIPELINE"),
        ("WRITE", "nestedArrayWrite", "ROOT_PIPELINE"),
        ("WRITE", "constructedArrayWrite", "ROOT_PIPELINE"),
    ]
    assert Counter(access.field_key for access in record.pipeline_accesses) == {
        "enhancedForWrite": 1,
        "primitiveArrayWrite": 1,
        "variableArrayWrite": 1,
        "expressionWrite": 1,
        "sizedArrayWrite": 1,
        "matrixArrayWrite": 1,
        "emptyArrayWrite": 1,
        "nestedArrayWrite": 1,
        "constructedArrayWrite": 1,
    }
    nested_findings = [
        finding
        for finding in record.findings
        if finding.code == "JAVA_NESTED_EXECUTABLE_BODY_SKIPPED"
    ]
    assert nested_findings == []
    payload = render_analysis_json(analysis)
    assert "arrayLiteralSecret" not in payload
    assert "collectionLiteralSecret" not in payload


def test_java_anonymous_class_inside_array_initializer_skips_only_inner_body(
    tmp_path: Path,
) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
Runnable[] runnables = new Runnable[] {
    new Runnable() {
        public void run() {
            IDataUtil.put(pc, "innerAnonymousWrite", "value");
        }
    }
};
IDataUtil.put(pc, "afterAnonymousArray", "value");
pc.destroy();
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_source(tmp_path, "javaSvc", _java_method("doIt", body))

    record = _java_record(tmp_path, "pkg.services.javaSvc:doIt")

    assert [access.field_key for access in record.pipeline_accesses] == [
        "afterAnonymousArray"
    ]
    nested_findings = [
        finding
        for finding in record.findings
        if finding.code == "JAVA_NESTED_EXECUTABLE_BODY_SKIPPED"
    ]
    assert len(nested_findings) == 1
    assert "ANONYMOUS_CLASS" in nested_findings[0].message
    assert "innerAnonymousWrite" not in nested_findings[0].message


def test_java_normal_control_blocks_remain_analyzed(tmp_path: Path) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
String[] values = new String[] {"normalControlLiteral"};
if (true) { IDataUtil.getString(pc, "ifRead"); }
else { IDataUtil.put(pc, "elseWrite", "x"); }
for (int i = 0; i < 1; i++) { IDataUtil.put(pc, "forWrite", "x"); }
for (String value : values) { IDataUtil.put(pc, "enhancedVariableWrite", value); }
for (String value : new String[] {"inlineNormalLiteral"}) {
    IDataUtil.put(pc, "enhancedInlineWrite", value);
}
for (String value : java.util.List.of("expressionNormalLiteral")) {
    IDataUtil.put(pc, "enhancedExpressionWrite", value);
}
while (IDataUtil.get(pc, "whileRead") == null) {
    IDataUtil.put(pc, "whileWrite", "x");
    break;
}
do { IDataUtil.put(pc, "doWhileWrite", "x"); }
while (IDataUtil.get(pc, "doWhileRead") == null);
try { IDataUtil.getString(pc, "tryRead"); }
catch (Exception ex) { IDataUtil.put(pc, "catchWrite", "x"); }
finally { IDataUtil.put(pc, "finallyWrite", "x"); }
switch ("x") {
case "x":
    IDataUtil.getString(pc, "switchRead");
    break;
default:
    IDataUtil.put(pc, "defaultWrite", "x");
}
synchronized (pipeline) { IDataUtil.put(pc, "syncWrite", "x"); }
{ IDataUtil.put(pc, "plainBlockWrite", "x"); }
pc.destroy();
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_source(tmp_path, "javaSvc", _java_method("doIt", body))

    record = _java_record(tmp_path, "pkg.services.javaSvc:doIt")

    assert [access.field_key for access in record.pipeline_accesses] == [
        "ifRead",
        "elseWrite",
        "forWrite",
        "enhancedVariableWrite",
        "enhancedInlineWrite",
        "enhancedExpressionWrite",
        "whileRead",
        "whileWrite",
        "doWhileWrite",
        "doWhileRead",
        "tryRead",
        "catchWrite",
        "finallyWrite",
        "switchRead",
        "defaultWrite",
        "syncWrite",
        "plainBlockWrite",
    ]
    assert "JAVA_NESTED_EXECUTABLE_BODY_SKIPPED" not in {
        finding.code for finding in record.findings
    }


def test_java_pipeline_imports_types_invocations_and_dependency_resolution(
    tmp_path: Path,
) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
File file = null;
Helper helper = null;
IData nested = IDataUtil.getIData(pc, "doc");
IDataCursor nestedCursor = nested.getCursor();
String dynamicKey = "doc";
String read = IDataUtil.getString(pc, dynamicKey);
IDataUtil.remove(nestedCursor, "removed");
IDataCursor unknownCursor = getCursorSomehow();
IDataUtil.put(unknownCursor, "unknownWrite", read);
String dynamicService = read;
String targetName = dynamicService;
Service.doInvoke("pkg.services.flow:targetFlow", pipeline);
Service.doInvoke("pkg.services.javaSvc:targetJava", pipeline);
Service.doInvoke("pkg.services.flow", dynamicService, pipeline);
String ns = "pkg.services.flow";
String svc = "targetFlow";
Service.doInvoke(ns, svc, pipeline);
svc = dynamicService;
Service.doInvoke(ns, svc, pipeline);
Service.doInvoke(NSName.create("pkg.services.flow", "targetFlow"), pipeline);
Service.doInvoke(targetName, pipeline);
pc.destroy();
"""
    imports = """
import com.example.Helper;
import com.wm.app.b2b.server.Service;
import com.wm.data.IData;
import com.wm.data.IDataCursor;
import com.wm.data.IDataUtil;
import com.wm.lang.ns.NSName;
import java.io.File;
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_metadata(tmp_path, "javaSvc", "targetJava", "")
    _write_java_source(
        tmp_path,
        "javaSvc",
        _java_method("doIt", body) + _java_method("targetJava", ""),
        imports=imports,
    )
    _write_node_idf_imports(
        tmp_path,
        "javaSvc",
        ["java.io.File", "java.util.List", "com.example.Helper"],
    )
    helper = tmp_path / "Pkg" / "code" / "source" / "com" / "example" / "Helper.java"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("package com.example; public class Helper {}\n", encoding="utf-8")
    _write_flow_service(tmp_path, "pkg", "services", "flow", service_name="targetFlow")

    analysis = analyze_path(tmp_path, DEFAULT_CONFIG)
    service = _service(analysis, "pkg.services.javaSvc:doIt")
    record = service.java_analysis
    assert record is not None

    accesses = {
        (item.access_kind.value, item.field_key, item.cursor_scope.value)
        for item in record.pipeline_accesses
    }
    assert ("READ", "doc", "ROOT_PIPELINE") in accesses
    assert ("READ", None, "ROOT_PIPELINE") in accesses
    assert ("REMOVE", "removed", "NESTED_IDATA") in accesses
    assert ("WRITE", "unknownWrite", "UNKNOWN_CURSOR") in accesses
    assert any(finding.code == "DYNAMIC_PIPELINE_KEY" for finding in record.findings)

    imports_by_name = {item.imported_name: item for item in record.imports}
    assert imports_by_name["java.io.File"].provenance == "BOTH"
    assert imports_by_name["java.util.List"].provenance == "NODE_IDF"
    assert imports_by_name["com.example.Helper"].category == "PACKAGE_LOCAL_CLASS"
    assert any(finding.code == "JAVA_IMPORT_SOURCE_MISMATCH" for finding in record.findings)

    types = {item.type_name: item for item in record.referenced_types}
    assert types["File"].category == "JAVA_STANDARD_LIBRARY"
    assert types["Helper"].category == "PACKAGE_LOCAL_CLASS"
    assert types["Service"].category == "WEBMETHODS_API"

    invocation_statuses = Counter(
        item.target_status.value for item in record.invocation_occurrences
    )
    assert invocation_statuses == {
        "STATIC_TARGET": 4,
        "PARTIALLY_STATIC_TARGET": 2,
        "DYNAMIC_TARGET": 1,
    }
    assert any(finding.code == "DYNAMIC_SERVICE_TARGET" for finding in record.findings)
    assert any(finding.code == "PARTIALLY_STATIC_SERVICE_TARGET" for finding in record.findings)

    call_targets = Counter(call.target for call in service.call_occurrences)
    assert call_targets == {
        "pkg.services.flow:targetFlow": 3,
        "pkg.services.javaSvc:targetJava": 1,
    }
    assert all(call.resolved for call in service.call_occurrences)
    dependency_counts = {
        dependency.target_service: dependency.occurrence_count
        for dependency in service.unique_dependencies
    }
    assert dependency_counts == {
        "pkg.services.flow:targetFlow": 3,
        "pkg.services.javaSvc:targetJava": 1,
    }


def test_java_malformed_source_uses_partial_parse_finding_and_fragment_fallback(
    tmp_path: Path,
) -> None:
    cases = {
        "unclosed_service_method": (
            "package pkg.services; import com.wm.data.*; public final class javaSvc { "
            "public static final void doIt (IData pipeline) { "
            "IDataUtil.put(pipeline, \"unsafeSourceOnly\", \"x\"); "
        ),
        "unclosed_class": (
            "package pkg.services; import com.wm.data.*; public final class javaSvc { "
            "public static final void other (IData pipeline) {} "
        ),
        "unclosed_anonymous": (
            "package pkg.services; import com.wm.data.*; public final class javaSvc { "
            "public static final void doIt (IData pipeline) { Runnable r = new Runnable() { "
            "public void run() { IDataUtil.put(pipeline, \"unsafeSourceOnly\", \"x\"); } }; "
            "IDataUtil.put(pipeline, \"afterBroken\", \"x\"); }"
        ),
        "broken_lambda": (
            "package pkg.services; import com.wm.data.*; public final class javaSvc { "
            "public static final void doIt (IData pipeline) { Runnable r = () -> { "
            "IDataUtil.put(pipeline, \"unsafeSourceOnly\", \"x\"); ; }"
        ),
        "malformed_method_declaration": (
            "package pkg.services; import com.wm.data.*; public final class javaSvc { "
            "public static final void doIt (IData pipeline { "
            "IDataUtil.put(pipeline, \"unsafeSourceOnly\", \"x\"); } }"
        ),
    }
    for name, source in cases.items():
        root = tmp_path / name
        _write_java_metadata(root, "javaSvc", "doIt", BASE_BODY)
        source_path = (
            root / "Pkg" / "code" / "source" / "pkg" / "services" / "javaSvc.java"
        )
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(source, encoding="utf-8")

        record = _java_record(root, "pkg.services.javaSvc:doIt")

        assert record.source_set.status == "SOURCE_PARTIAL_PARSE"
        assert record.source_set.parser_mode == "FRAGMENT_FALLBACK"
        assert "JAVA_SOURCE_PARTIAL_PARSE" in {finding.code for finding in record.findings}
        assert "JAVA_SOURCE_METHOD_NOT_FOUND" not in {
            finding.code for finding in record.findings
        }
        assert [access.field_key for access in record.pipeline_accesses] == ["input", "output"]


def test_fully_qualified_type_references_without_imports_are_m4a_deferred(
    tmp_path: Path,
) -> None:
    body = """
IDataCursor pc = pipeline.getCursor();
java.nio.file.Path path = null;
com.example.Helper helper = null;
String input = IDataUtil.getString(pc, "input");
pc.destroy();
"""
    _write_java_metadata(tmp_path, "javaSvc", "doIt", body)
    _write_java_source(tmp_path, "javaSvc", _java_method("doIt", body))

    record = _java_record(tmp_path, "pkg.services.javaSvc:doIt")

    assert {reference.resolved_import for reference in record.referenced_types} == set()


def _java_record(root: Path, full_name: str):
    analysis = analyze_path(root, DEFAULT_CONFIG)
    for record in analysis.java_service_analyses:
        if record.identity.full_name == full_name:
            return record
    raise AssertionError(f"Java analysis not found: {full_name}")


def _service(analysis, full_name: str):
    for package in analysis.packages:
        for service in package.services:
            if service.identity.full_name == full_name:
                return service
    raise AssertionError(f"Service not found: {full_name}")


def _write_java_metadata(
    root: Path,
    class_name: str,
    service_name: str,
    body: str | None,
    *,
    write_frag: bool = True,
) -> None:
    service_dir = _java_service_dir(root, class_name, service_name)
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "node.ndf").write_text(
        """<Values version="2.0">
  <value name="svc_type">java</value>
  <value name="svc_sigtype">java 3.5</value>
</Values>""",
        encoding="utf-8",
    )
    if write_frag:
        encoded = base64.b64encode((body or "").encode("utf-8")).decode("ascii")
        (service_dir / "java.frag").write_text(
            f"""<Values version="2.0">
  <value name="name">{service_name}</value>
  <value name="body">{encoded}</value>
</Values>""",
            encoding="utf-8",
        )


def _write_java_source(
    root: Path,
    expected_class_name: str,
    methods: str,
    *,
    imports: str = "",
    package_name: str = "pkg.services",
    class_name: str | None = None,
) -> None:
    source_path = (
        root
        / "Pkg"
        / "code"
        / "source"
        / "pkg"
        / "services"
        / f"{expected_class_name}.java"
    )
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text(
        f"""package {package_name};
{imports}
public final class {class_name or expected_class_name} {{
{methods}
}}
""",
        encoding="utf-8",
    )


def _java_method(name: str, body: str, *, signature: str | None = None) -> str:
    method_signature = signature or (
        f"public static final void {name} (IData pipeline) throws ServiceException"
    )
    return f"""
{method_signature}
{{
{body}
}}
"""


def _dependency_dot_edges(analysis) -> str:
    from wm_doc.render.dot import render_dependency_dot

    return "\n".join(
        line for line in render_dependency_dot(analysis).splitlines() if " -> " in line
    )


def _write_node_idf_imports(root: Path, class_name: str, imports: list[str]) -> None:
    node_idf = root / "Pkg" / "ns" / "pkg" / "services" / class_name / "node.idf"
    node_idf.parent.mkdir(parents=True, exist_ok=True)
    values = "\n".join(f"    <value>{item}</value>" for item in imports)
    node_idf.write_text(
        f"""<Values version="2.0">
  <value name="node_type">interface</value>
  <array name="imports" type="value" depth="1">
{values}
  </array>
</Values>""",
        encoding="utf-8",
    )


def _write_flow_service(
    root: Path, *namespace_parts: str, service_name: str
) -> None:
    service_dir = root / "Pkg" / "ns" / Path(*namespace_parts) / service_name
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "node.ndf").write_text(
        """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )
    (service_dir / "flow.xml").write_text(
        """<FLOW VERSION="3.0" CLEANUP="true"></FLOW>""",
        encoding="utf-8",
    )


def _java_service_dir(root: Path, class_name: str, service_name: str) -> Path:
    return root / "Pkg" / "ns" / "pkg" / "services" / class_name / service_name
