"""The SQL template reader: statement, tables, binds, substitutions, Oracle shapes, limits."""

from __future__ import annotations

from wm_doc.ir import SqlAnalysis
from wm_doc.sql_analysis import analyze_sql, tokenize


def _tables(analysis: SqlAnalysis) -> list[tuple[str | None, str, str]]:
    return [(item.schema_name, item.name, item.access) for item in analysis.objects]


def _binds(analysis: SqlAnalysis) -> list[tuple[str | None, str | None, str]]:
    return [(item.column, item.operator, item.role) for item in analysis.binds]


def test_dynamic_sql_keeps_substitutions_apart_from_bind_parameters() -> None:
    analysis = analyze_sql(
        "Select * from TEST t Where t.id IN (${IN_ARRAY}) AND t.name = ? AND t.quantity = ? "
    )
    assert analysis.status == "analysed"
    assert analysis.statement == "SELECT"
    assert _tables(analysis) == [(None, "TEST", "read")]
    assert _binds(analysis) == [("t.name", "=", "value"), ("t.quantity", "=", "value")]
    [placeholder] = analysis.placeholders
    assert (placeholder.name, placeholder.contexts, placeholder.column) == (
        "IN_ARRAY",
        ["value list"],
        "t.id",
    )
    assert analysis.where and analysis.order_by is None and analysis.pagination == []


def test_question_marks_and_names_inside_literals_and_comments_are_not_sql() -> None:
    analysis = analyze_sql(
        "SELECT a FROM t -- FROM hidden WHERE x = ?\n"
        "WHERE note = 'what? FROM other' /* ? FROM c */ AND b = ? AND q = q'[it's ?]'"
    )
    assert _tables(analysis) == [(None, "t", "read")]
    assert _binds(analysis) == [("b", "=", "value")]


def test_literal_values_never_leave_the_reader() -> None:
    sql = "SELECT * FROM t WHERE code = 'S3CRET-42' AND n = 4711"
    tokens, _ = tokenize(sql)
    assert all("S3CRET" not in token.text and "4711" not in token.text for token in tokens)
    dumped = analyze_sql(sql).model_dump_json()
    assert "S3CRET" not in dumped and "4711" not in dumped


def test_oracle_pagination_cte_join_and_function_from() -> None:
    analysis = analyze_sql(
        "WITH recent AS (SELECT id FROM sales.orders o WHERE o.status = 'OPEN') "
        "SELECT EXTRACT(YEAR FROM r.created) y, c.name FROM recent r "
        "JOIN crm.customers c ON c.id = r.id, dual "
        "WHERE c.name LIKE ? ORDER BY c.name OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    )
    assert analysis.status == "analysed"
    assert analysis.ctes == ["recent"]
    assert _tables(analysis) == [("sales", "orders", "read"), ("crm", "customers", "read")]
    assert analysis.joins == 1 and analysis.subqueries == 1
    assert analysis.order_by == "top level"
    assert analysis.pagination == ["OFFSET ... ROWS", "FETCH NEXT ... ROWS"]
    assert _binds(analysis) == [
        ("c.name", "LIKE", "value"),
        (None, None, "row offset"),
        (None, None, "row limit"),
    ]
    assert any("pseudo-table" in note for note in analysis.notes)


def test_rownum_pagination_over_an_ordered_subquery() -> None:
    analysis = analyze_sql("select * from (select * from x order by a) where rownum <= ?")
    assert analysis.pagination == ["ROWNUM"]
    assert analysis.order_by == "subquery only"
    assert _binds(analysis) == [("rownum", "<=", "row limit")]


def test_write_statements_name_their_targets() -> None:
    insert = analyze_sql("INSERT INTO app.audit (id, who) VALUES (?, ?)")
    assert _tables(insert) == [("app", "audit", "write")]
    assert _binds(insert) == [("id", "value of", "value"), ("who", "value of", "value")]

    copy = analyze_sql("INSERT INTO hist SELECT * FROM live WHERE day < ?")
    assert _tables(copy) == [(None, "hist", "write"), (None, "live", "read")]

    update = analyze_sql("UPDATE t SET a = ?, b = ? WHERE id = ?")
    assert _tables(update) == [(None, "t", "write")]
    assert _binds(update) == [("a", "set", "value"), ("b", "set", "value"), ("id", "=", "value")]

    delete = analyze_sql("DELETE FROM t WHERE x BETWEEN ? AND ?")
    assert _tables(delete) == [(None, "t", "write")]
    assert _binds(delete) == [("x", "BETWEEN", "value"), ("x", "BETWEEN", "value")]

    merge = analyze_sql(
        "MERGE INTO t USING (SELECT * FROM u) s ON (t.id = s.id) "
        "WHEN MATCHED THEN UPDATE SET t.a = s.a"
    )
    assert _tables(merge) == [(None, "t", "write"), (None, "u", "read")]


def test_procedure_calls() -> None:
    escape = analyze_sql("{call pkg.proc(?, ?)}")
    assert (escape.statement, escape.procedure, len(escape.binds)) == ("CALL", "pkg.proc", 2)
    plain = analyze_sql("CALL refresh_stats()")
    assert (plain.statement, plain.procedure) == ("CALL", "refresh_stats")


def test_a_table_named_by_a_substitution_is_partial() -> None:
    analysis = analyze_sql("select * from ${TAB} where a = ?")
    assert analysis.status == "partial"
    assert analysis.objects == []
    assert analysis.placeholders[0].contexts == ["object name"]


def test_unclear_templates_are_partial_or_not_analysed() -> None:
    assert analyze_sql("").status == "not_analysed"
    assert analyze_sql("SELECT * FROM t WHERE a = 'open").status == "partial"
    assert analyze_sql("SELECT (a FROM t").status == "partial"
    assert analyze_sql("SELECT 1 FROM t; DELETE FROM t").status == "partial"
    assert analyze_sql("GRANT SELECT ON t TO u").statement == "OTHER"


def test_quoted_identifiers_keep_their_case() -> None:
    analysis = analyze_sql('SELECT * FROM "MySchema"."Order Lines" ol, Plain p')
    assert _tables(analysis) == [("MySchema", "Order Lines", "read"), (None, "Plain", "read")]


def test_the_same_table_read_and_written_is_one_object() -> None:
    analysis = analyze_sql(
        "UPDATE stock SET qty = (SELECT qty FROM stock WHERE id = ?) WHERE id = ?"
    )
    assert _tables(analysis) == [(None, "stock", "read-write")]
