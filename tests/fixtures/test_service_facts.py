"""M12 phase 1: the facts on service pages, summaries and pseudo-code are correct."""

from __future__ import annotations

from pathlib import Path

import pytest

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.ir import AnalysisResult, FlowNode, FlowNodeType, FlowService, SignatureOrigin
from wm_doc.pseudocode import render_pseudocode
from wm_doc.render.service_markdown import render_service_markdown
from wm_doc.render.service_summary import error_handling_mechanisms, render_service_summary

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
ORDER_BATCH = "sample.orders.intake:validateOrderBatch"


@pytest.fixture(scope="module")
def samples() -> dict[str, FlowService]:
    analysis = analyze_path(SAMPLES, load_config(None), None, processes_file_explicit=False)
    return {s.identity.full_name: s for p in analysis.packages for s in p.services}


def _analyze(root: Path) -> AnalysisResult:
    return analyze_path(root, load_config(None), None, processes_file_explicit=False)


def _service(analysis: AnalysisResult, full_name: str) -> FlowService:
    return next(
        s for p in analysis.packages for s in p.services if s.identity.full_name == full_name
    )


def _write_flow_service(root: Path, namespace: str, name: str, flow_body: str, **node) -> None:
    service_dir = root / "Pkg" / "ns" / Path(*namespace.split(".")) / name
    service_dir.mkdir(parents=True)
    spec = node.get("spec")
    spec_line = f'  <value name="svc_spec">{spec}</value>\n' if spec else ""
    (service_dir / "node.ndf").write_text(
        f"""<Values version="2.0">
  <value name="svc_type">flow</value>
{spec_line}  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )
    (service_dir / "flow.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<FLOW VERSION="3.0" CLEANUP="true">\n'
        f"{flow_body}\n</FLOW>",
        encoding="utf-8",
    )


def _invoke(target: str) -> str:
    return (
        f'<INVOKE TIMEOUT="" SERVICE="{target}" VALIDATE-IN="$none" VALIDATE-OUT="$none">'
        "</INVOKE>"
    )


def _find(node: FlowNode | None, node_type: FlowNodeType) -> FlowNode | None:
    if node is None:
        return None
    if node.type is node_type:
        return node
    for child in node.children:
        found = _find(child, node_type)
        if found is not None:
            return found
    return None


def test_default_page_lists_transformer_calls(samples: dict[str, FlowService]) -> None:
    page = render_service_markdown(samples[ORDER_BATCH])

    assert "## Calls" in page
    assert "## Normal Service Dependencies" not in page
    assert "| `sample.orders.services.common:saveEvent` | transformer | `EXTERNAL` |" in page
    assert "| `pub.publish:publish` | step | `PLATFORM` | publishes a message |" in page
    for heading in ("## Input Signature", "## Called By", "## Processes"):
        assert heading in page


def test_summary_ranks_effects_and_counts_external_calls(
    samples: dict[str, FlowService],
) -> None:
    summary = render_service_summary(samples[ORDER_BATCH])

    first_sentence = summary.split(". ", 1)[0]
    assert first_sentence.startswith("Starts a transaction, commits a transaction")
    # Before ranking, list/string helpers crowded the publish out of the first four labels.
    assert "publishes a message" in first_sentence
    assert "measures a list" not in first_sentence
    assert "Calls 9 services outside the analysed packages and 10 platform services." in summary
    assert "local service" not in summary


def test_summary_recognises_flow_error_handling(samples: dict[str, FlowService]) -> None:
    assert error_handling_mechanisms(samples[ORDER_BATCH]) == [
        "TRY/CATCH blocks",
        "a try/catch sequence (exit on first success)",
        "`pub.flow:getLastError`",
    ]
    assert render_service_summary(samples["pgp.services.common:readConfig"]).endswith(
        "No error-handling steps found."
    )


def test_java_summary_does_not_claim_missing_error_handling(
    samples: dict[str, FlowService],
) -> None:
    summary = render_service_summary(samples["pgp.services.decrypt:decryptAndVerify"])

    assert summary.endswith("Error handling is not analysed for Java services.")
    assert "No statically confirmed service calls." in summary
    assert "No explicit error handling" not in summary


def test_logging_is_not_error_handling(tmp_path: Path) -> None:
    _write_flow_service(tmp_path, "acme.log", "onlyLogs", _invoke("pub.flow:debugLog"))

    service = _service(_analyze(tmp_path), "acme.log:onlyLogs")

    assert error_handling_mechanisms(service) == []
    assert render_service_summary(service).endswith("No error-handling steps found.")


def test_specification_signature_is_used_when_service_declares_none(
    samples: dict[str, FlowService],
) -> None:
    service = samples["pgp.services.decrypt:decryptAndVerify"]
    page = render_service_markdown(service)

    assert service.specification == "pgp.specifications:decryptAndVerifySpec"
    assert service.signature_origin is SignatureOrigin.SPECIFICATION
    assert [field.name for field in service.signature.inputs][:2] == [
        "cipherTextBytes",
        "cipherTextPath",
    ]
    assert "| Specification | `pgp.specifications:decryptAndVerifySpec` |" in page
    assert "Signature from specification `pgp.specifications:decryptAndVerifySpec`." in page
    assert "signature: from specification pgp.specifications:decryptAndVerifySpec" in (
        render_pseudocode(service, lambda _: None)
    )


def test_unknown_specification_keeps_service_signature(tmp_path: Path) -> None:
    _write_flow_service(
        tmp_path, "acme.spec", "usesMissingSpec", _invoke("pub.flow:debugLog"),
        spec="acme.specs:doesNotExist",
    )

    service = _service(_analyze(tmp_path), "acme.spec:usesMissingSpec")

    assert service.specification == "acme.specs:doesNotExist"
    assert service.signature_origin is SignatureOrigin.SERVICE
    assert service.signature.inputs == []


def test_repeat_step_is_modelled(tmp_path: Path) -> None:
    body = (
        '<RETRY TIMEOUT="" COUNT="3" BACK-OFF="10" LOOP-ON="FAILURE">'
        f"{_invoke('acme.remote:send')}</RETRY>"
    )
    _write_flow_service(tmp_path, "acme.retry", "sendWithRetry", body)

    service = _service(_analyze(tmp_path), "acme.retry:sendWithRetry")
    repeat = _find(service.flow_tree, FlowNodeType.REPEAT)

    assert repeat is not None
    assert repeat.attributes["COUNT"] == "3"
    assert repeat.attributes["LOOP-ON"] == "FAILURE"
    assert not any(f.code == "UNSUPPORTED_FLOW_ELEMENT" for f in service.findings)
    assert error_handling_mechanisms(service) == ["REPEAT on failure"]
    assert "REPEAT up to 3 more time(s) on failure, waiting 10s between attempts:" in (
        render_pseudocode(service, lambda _: None)
    )
    assert service.call_occurrences[0].target == "acme.remote:send"


def test_signature_table_has_no_empty_code_spans(samples: dict[str, FlowService]) -> None:
    page = render_service_markdown(samples["pgp.services.decrypt:decryptAndVerify"])

    assert "``" not in page
