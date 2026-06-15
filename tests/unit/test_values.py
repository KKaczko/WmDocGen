from __future__ import annotations

from wm_doc.values import parse_values_file, record_value, scalar_value


def test_parse_values_file_reads_nested_records(tmp_path) -> None:
    values_file = tmp_path / "node.ndf"
    values_file.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in">
      <value name="field_type">record</value>
    </record>
  </record>
</Values>
""",
        encoding="utf-8",
    )

    parsed = parse_values_file(values_file)

    assert scalar_value(parsed, "svc_type") == "flow"
    svc_sig = record_value(parsed, "svc_sig")
    assert svc_sig is not None
    sig_in = record_value(svc_sig, "sig_in")
    assert sig_in is not None
    assert scalar_value(sig_in, "field_type") == "record"
