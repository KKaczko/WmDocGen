"""Build FLOW services for tests in the shapes Designer writes (test-only, never shipped).

Steps are XML strings composed with small functions, so a test reads like the FLOW it builds:

    pkg = FlowPackage(tmp_path, "Orders")
    pkg.service(
        "orders.api:processOrder",
        branch(
            case("ACTIVE", invoke("systemA:validateOrder",
                                  outputs=[copy("/result/status", "/validationStatus")])),
            case("FINALIZED", invoke("systemB:finalizeOrder")),
            switch="/request/status",
        ),
        inputs=[record("request", [string("status")])],
    )
    analysis = pkg.analyze()

Mapping paths are written plainly (`/request/status`) and get Designer's type suffixes
(`/request;2;0/status;1;0`, the leaf typed as a string); write the suffixes yourself for other
types (`/conn;2;0`). A path that already has suffixes is kept as it is. BRANCH switches and LOOP
arrays stay plain unless `typed_switch=True`, as in the PGP sample. A case is either wrapped
in a SEQUENCE named after the label (`case(label, *steps)`) or is the step itself carrying the
label as its NAME (`case(label, step, wrap=False)`), as Designer allows both. Label expressions
are passed through unchanged. Every name used by tests is invented.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from wm_doc.analysis import analyze_path
from wm_doc.config import AppConfig, ExtractionMode, load_config
from wm_doc.ir import AnalysisResult


def typed(path: str, *, leaf: str = "1;0") -> str:
    """`/a/b` -> `/a;2;0/b;1;0`; paths that already carry suffixes are returned unchanged."""
    if ";" in path or not path.startswith("/"):
        return path
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return path
    parts = [f"{segment};2;0" for segment in segments[:-1]] + [f"{segments[-1]};{leaf}"]
    return "/" + "/".join(parts)


def _attrs(pairs: dict[str, str | None]) -> str:
    return "".join(
        f" {name}={quoteattr(value)}" for name, value in pairs.items() if value is not None
    )


def _disabled(disabled: bool) -> str | None:
    return "true" if disabled else None


def _block(tag: str, attrs: dict[str, str | None], body: list[str], comment: str | None) -> str:
    lines = [f"<{tag}{_attrs(attrs)}>"]
    if comment is not None:
        lines.append(f"<COMMENT>{escape(comment)}</COMMENT>")
    lines.extend(body)
    lines.append(f"</{tag}>")
    return "\n".join(lines)


# --- mapping operations --------------------------------------------------------------------


def copy(source: str, target: str, **extra: str) -> str:
    attrs: dict[str, str | None] = {"FROM": typed(source), "TO": typed(target), **extra}
    return f"<MAPCOPY{_attrs(attrs)}>\n</MAPCOPY>"


def drop(path: str) -> str:
    return f"<MAPDELETE{_attrs({'FIELD': typed(path)})}>\n</MAPDELETE>"


def set_(path: str, value: str, *, overwrite: bool = True, variables: bool = False) -> str:
    target = typed(path)
    name = target.rstrip("/").rsplit("/", 1)[-1].split(";", 1)[0]
    attrs: dict[str, str | None] = {
        "NAME": "Setter",
        "OVERWRITE": "true" if overwrite else "false",
        "VARIABLES": "true" if variables else "false",
        "GLOBALVARIABLES": "false",
        "FIELD": target,
    }
    return (
        f"<MAPSET{_attrs(attrs)}>\n"
        '<DATA ENCODING="XMLValues" I18N="true">\n'
        '<Values version="2.0">\n'
        f'  <value name="xml">{escape(value)}</value>\n'
        '  <record name="type" javaclass="com.wm.util.Values">\n'
        '    <value name="node_type">unknown</value>\n'
        f'    <value name="field_name">{escape(name)}</value>\n'
        '    <value name="field_type">string</value>\n'
        '    <value name="field_dim">0</value>\n'
        "  </record>\n"
        "</Values>\n"
        "</DATA>\n"
        "</MAPSET>"
    )


# --- steps ---------------------------------------------------------------------------------


def map_(
    *operations: str,
    mode: str = "STANDALONE",
    name: str | None = None,
    comment: str | None = None,
    disabled: bool = False,
) -> str:
    attrs: dict[str, str | None] = {
        "NAME": name,
        "TIMEOUT": "" if mode == "STANDALONE" else None,
        "MODE": mode,
        "DISABLED": _disabled(disabled),
    }
    return _block("MAP", attrs, list(operations), comment)


def transform(
    service: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    order: int = 0,
) -> str:
    """A transformer (MAPINVOKE); place it inside `map_()`."""
    attrs: dict[str, str | None] = {
        "SERVICE": service,
        "VALIDATE-IN": "$none",
        "VALIDATE-OUT": "$none",
        "INVOKE-ORDER": str(order),
    }
    body = [map_(*(inputs or []), mode="INVOKEINPUT"), map_(*(outputs or []), mode="INVOKEOUTPUT")]
    return _block("MAPINVOKE", attrs, body, None)


def invoke(
    service: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
    *,
    name: str | None = None,
    comment: str | None = "",
    disabled: bool = False,
) -> str:
    attrs: dict[str, str | None] = {
        "NAME": name,
        "TIMEOUT": "",
        "SERVICE": service,
        "VALIDATE-IN": "$none",
        "VALIDATE-OUT": "$none",
        "DISABLED": _disabled(disabled),
    }
    body: list[str] = []
    if inputs is not None:
        body.append(map_(*inputs, mode="INPUT"))
    if outputs is not None:
        body.append(map_(*outputs, mode="OUTPUT"))
    return _block("INVOKE", attrs, body, comment)


def seq(
    *steps: str,
    name: str | None = None,
    exit_on: str = "FAILURE",
    form: str | None = None,
    comment: str | None = None,
    disabled: bool = False,
) -> str:
    attrs: dict[str, str | None] = {
        "NAME": name,
        "TIMEOUT": "",
        "EXIT-ON": exit_on,
        "FORM": form,
        "DISABLED": _disabled(disabled),
    }
    return _block("SEQUENCE", attrs, list(steps), comment)


def case(label: str, *steps: str, disabled: bool = False, wrap: bool = True) -> str:
    """A BRANCH child labelled `label` (`$default`, `$null`, a value or an expression).

    By default the steps are wrapped in a SEQUENCE carrying the label. With `wrap=False` the
    single step is the child and carries the label as its NAME, as in the PGP sample.
    """
    if wrap:
        return seq(*steps, name=label, disabled=disabled)
    if len(steps) != 1 or disabled:
        raise ValueError("an unwrapped case is exactly one step (disable the step itself)")
    step = steps[0]
    tag_end = step.index(" ") if " " in step.split(">", 1)[0] else step.index(">")
    if " NAME=" in step.split(">", 1)[0]:
        raise ValueError("the step already has a NAME")
    return step[:tag_end] + f" NAME={quoteattr(label)}" + step[tag_end:]


def branch(
    *children: str,
    switch: str | None = None,
    expressions: bool = False,
    typed_switch: bool = False,
    comment: str | None = "",
    disabled: bool = False,
) -> str:
    attrs: dict[str, str | None] = {
        "TIMEOUT": "",
        "SWITCH": (typed(switch) if typed_switch else switch) if switch else None,
        "LABELEXPRESSIONS": "true" if expressions else None,
        "DISABLED": _disabled(disabled),
    }
    return _block("BRANCH", attrs, list(children), comment)


def loop(
    *steps: str,
    in_array: str,
    out_array: str | None = None,
    name: str | None = None,
    comment: str | None = "",
) -> str:
    attrs: dict[str, str | None] = {
        "NAME": name,
        "TIMEOUT": "",
        "IN-ARRAY": in_array,
        "OUT-ARRAY": out_array,
    }
    return _block("LOOP", attrs, list(steps), comment)


def repeat(*steps: str, count: str = "1", loop_on: str = "FAILURE", back_off: str = "0") -> str:
    attrs: dict[str, str | None] = {
        "TIMEOUT": "",
        "COUNT": count,
        "BACK-OFF": back_off,
        "LOOP-ON": loop_on,
    }
    return _block("RETRY", attrs, list(steps), None)


def exit_(from_: str = "$parent", signal: str = "SUCCESS", message: str = "") -> str:
    attrs: dict[str, str | None] = {"FROM": from_, "SIGNAL": signal, "FAILURE-MESSAGE": message}
    return f"<EXIT{_attrs(attrs)}>\n</EXIT>"


def try_catch(
    try_steps: list[str], catch_steps: list[str], finally_steps: list[str] | None = None
) -> str:
    """TRY/CATCH(/FINALLY) as sibling FORM sequences inside an EXIT-ON SUCCESS sequence.

    This is the shape of the Synthetic sample; how IS 10.15 really writes FINALLY is still to be
    checked (V13, rule S14), so FINALLY fixtures are provisional.
    """
    blocks = [
        seq(*try_steps, name="Try", form="TRY"),
        seq(*catch_steps, name="Catch", form="CATCH"),
    ]
    if finally_steps is not None:
        blocks.append(seq(*finally_steps, name="Finally", form="FINALLY"))
    return seq(*blocks, exit_on="SUCCESS")


# --- signatures ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Field:
    name: str
    kind: str = "string"  # string | record | recref
    dim: int = 0
    children: tuple[Field, ...] = ()
    ref: str | None = None


def string(name: str, dim: int = 0) -> Field:
    return Field(name, "string", dim)


def record(name: str, children: list[Field] | None = None, dim: int = 0) -> Field:
    return Field(name, "record", dim, tuple(children or ()))


def recref(name: str, ref: str, dim: int = 0) -> Field:
    return Field(name, "recref", dim, (), ref)


def _field_xml(item: Field, indent: str) -> str:
    node_type = "record" if item.kind in ("record", "recref") else "unknown"
    lines = [
        f'{indent}<record javaclass="com.wm.util.Values">',
        f'{indent}  <value name="node_type">{node_type}</value>',
        f'{indent}  <value name="node_subtype">unknown</value>',
        f'{indent}  <value name="is_public">false</value>',
        f'{indent}  <value name="field_name">{escape(item.name)}</value>',
        f'{indent}  <value name="field_type">{item.kind}</value>',
        f'{indent}  <value name="field_dim">{item.dim}</value>',
        f'{indent}  <value name="nillable">true</value>',
    ]
    if item.kind == "record":
        lines.append(f'{indent}  <array name="rec_fields" type="record" depth="1">')
        lines.extend(_field_xml(child, indent + "    ") for child in item.children)
        lines.append(f"{indent}  </array>")
    if item.ref is not None:
        lines.append(f'{indent}  <value name="rec_ref">{escape(item.ref)}</value>')
    lines.append(f"{indent}</record>")
    return "\n".join(lines)


def _signature_xml(name: str, fields: list[Field]) -> str:
    body = "\n".join(_field_xml(item, "        ") for item in fields)
    return (
        f'    <record name="{name}" javaclass="com.wm.util.Values">\n'
        '      <value name="node_type">record</value>\n'
        '      <value name="field_type">record</value>\n'
        '      <value name="field_dim">0</value>\n'
        '      <array name="rec_fields" type="record" depth="1">\n'
        + (body + "\n" if body else "")
        + "      </array>\n"
        "    </record>\n"
    )


# --- packages ------------------------------------------------------------------------------


@dataclass
class FlowPackage:
    """A packages directory with one package; services are written as they are added."""

    root: Path
    name: str = "Pkg"

    def __post_init__(self) -> None:
        # wm-doc skips Wm* and Default packages by default; a fixture there would vanish.
        if self.name.startswith("Wm") or self.name == "Default":
            raise ValueError(f"package name {self.name!r} is skipped by default")

    def service(
        self,
        full_name: str,
        *steps: str,
        inputs: list[Field] | None = None,
        outputs: list[Field] | None = None,
    ) -> Path:
        namespace, colon, service_name = full_name.partition(":")
        if not colon or not namespace or not service_name:
            raise ValueError(f"not a service name: {full_name!r}")
        folder = self.root / self.name / "ns" / Path(*namespace.split(".")) / service_name
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "node.ndf").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n\n'
            '<Values version="2.0">\n'
            '  <value name="svc_type">flow</value>\n'
            '  <value name="svc_subtype">default</value>\n'
            '  <value name="svc_sigtype">java 3.5</value>\n'
            '  <record name="svc_sig" javaclass="com.wm.util.Values">\n'
            + _signature_xml("sig_in", inputs or [])
            + _signature_xml("sig_out", outputs or [])
            + "  </record>\n"
            '  <value name="node_comment"></value>\n'
            "</Values>\n",
            encoding="utf-8",
            newline="\n",
        )
        body = "\n".join(steps)
        (folder / "flow.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n\n'
            f'<FLOW VERSION="3.0" CLEANUP="true">\n{body}\n</FLOW>\n',
            encoding="utf-8",
            newline="\n",
        )
        return folder

    def analyze(
        self,
        *,
        free_text: ExtractionMode | None = None,
        literals: ExtractionMode | None = None,
    ) -> AnalysisResult:
        return analyze_path(self.root, extraction_config(free_text=free_text, literals=literals))


def extraction_config(
    *, free_text: ExtractionMode | None = None, literals: ExtractionMode | None = None
) -> AppConfig:
    config = load_config(None)
    extraction = config.extraction
    if free_text is not None:
        extraction = extraction.model_copy(
            update={"freeText": extraction.freeText.model_copy(update={"mode": free_text})}
        )
    if literals is not None:
        extraction = extraction.model_copy(
            update={"literals": extraction.literals.model_copy(update={"mode": literals})}
        )
    return config.model_copy(update={"extraction": extraction})
