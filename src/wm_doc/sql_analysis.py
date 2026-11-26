"""Deterministic reading of a JDBC adapter's SQL template (never executed, no database).

The SQL is tokenized first: string literals, quoted identifiers, comments, `?` bind
parameters and DynamicSQL `${name}` substitutions are tokens of their own, so nothing inside
a literal or a comment is mistaken for SQL, and a substitution is never replaced by guessed
text. The tokens are then read for:

- the statement type (after any `WITH` list) and a called procedure;
- the tables and views named after FROM, JOIN, INTO, UPDATE, DELETE, MERGE INTO and USING,
  with read or write access; a FROM inside a function call (`EXTRACT(YEAR FROM d)`) is not
  a table, and CTE names and Oracle's `DUAL` are not listed;
- clauses that matter for behaviour: WHERE, GROUP BY, ORDER BY, pagination (`OFFSET ...
  ROWS`, `FETCH FIRST|NEXT ... ROWS`, `ROWNUM`, `LIMIT`, `TOP`), set operations, FOR UPDATE;
- each bind parameter in order, with the column it is compared with or assigned to when the
  SQL shows it directly, and each substitution with where it stands.

Only identifiers and structure leave this module; literal values never do. Anything not
understood becomes a note, and a note that may hide part of the statement makes the status
`partial`. The original SQL text is kept by the caller exactly as configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from wm_doc.ir import SqlAnalysis, SqlBind, SqlObject, SqlPlaceholder

MAX_SQL_CHARS = 200_000

WORD = "word"
QUOTED = "quoted"
STRING = "string"
NUMBER = "number"
BIND = "bind"
NAMED_BIND = "named_bind"
PLACEHOLDER = "placeholder"
OP = "op"
PUNCT = "punct"

_COMPARISONS = {"=", "<>", "!=", "^=", "<", ">", "<=", ">="}
_MIRRORED = {"<": ">", ">": "<", "<=": ">=", ">=": "<="}
_STATEMENTS = {"SELECT", "INSERT", "UPDATE", "DELETE", "MERGE"}
_CALLS = {"CALL", "EXEC", "EXECUTE"}
_SET_OPERATIONS = {"UNION", "INTERSECT", "MINUS", "EXCEPT"}
# Words that never start a table name after FROM, JOIN, INTO, ...
_NOT_TABLES = {
    "SELECT",
    "WHERE",
    "SET",
    "VALUES",
    "ON",
    "USING",
    "WITH",
    "LATERAL",
    "ONLY",
    "TABLE",
    "JOIN",
    "INNER",
    "LEFT",
    "RIGHT",
    "FULL",
    "CROSS",
    "OUTER",
    "NATURAL",
    "GROUP",
    "ORDER",
    "HAVING",
    "UNION",
    "MINUS",
    "INTERSECT",
    "EXCEPT",
    "FETCH",
    "OFFSET",
    "FOR",
    "CONNECT",
    "START",
    "WINDOW",
    "LIMIT",
    "RETURNING",
    "WHEN",
    "THEN",
    "AS",
}
# Words that end an identifier chain read backwards from a comparison.
_KEYWORD_ENDS = {
    "WHERE",
    "AND",
    "OR",
    "NOT",
    "ON",
    "SET",
    "SELECT",
    "BY",
    "HAVING",
    "WHEN",
    "THEN",
    "ELSE",
    "CASE",
    "IN",
    "BETWEEN",
    "LIKE",
    "IS",
    "NULL",
    "ROWS",
    "ROW",
    "FIRST",
    "NEXT",
}
_PSEUDO_TABLES = {"DUAL"}
_CLOSERS = {"[": "]", "{": "}", "(": ")", "<": ">"}
_PARTIAL = True
_INFO = False


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    text: str  # as written; quoted identifiers without quotes; "" for string literals

    @property
    def upper(self) -> str:
        return self.text.upper() if self.kind == WORD else ""


def tokenize(sql: str) -> tuple[list[Token], list[str]]:
    """The tokens of `sql` without comments and blanks, and notes on what is not closed."""
    tokens: list[Token] = []
    notes: list[str] = []
    index = 0
    length = len(sql)
    while index < length:
        char = sql[index]
        if char.isspace():
            index += 1
        elif sql.startswith("--", index):
            end = sql.find("\n", index)
            index = length if end < 0 else end + 1
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end < 0:
                notes.append("a comment is not closed")
                index = length
            else:
                index = end + 2
        elif char == "'" or (char in "nNqQ" and _quote_prefix(sql, index) is not None):
            index = _string(sql, index, tokens, notes)
        elif char == '"':
            end = sql.find('"', index + 1)
            if end < 0:
                notes.append("a quoted identifier is not closed")
                index = length
            else:
                tokens.append(Token(QUOTED, sql[index + 1 : end]))
                index = end + 1
        elif sql.startswith("${", index):
            end = sql.find("}", index + 2)
            name = sql[index + 2 : end].strip() if end > 0 else ""
            if not name or "\n" in name:
                tokens.append(Token(OP, "$"))
                index += 1
            else:
                tokens.append(Token(PLACEHOLDER, name))
                index = end + 1
        elif char == "?":
            tokens.append(Token(BIND, "?"))
            index += 1
        elif char == ":" and index + 1 < length and sql[index + 1].isalpha():
            end = _word_end(sql, index + 1)
            tokens.append(Token(NAMED_BIND, sql[index + 1 : end]))
            index = end
        elif char.isalpha() or char == "_":
            end = _word_end(sql, index)
            tokens.append(Token(WORD, sql[index:end]))
            index = end
        elif char.isdigit() or (char == "." and index + 1 < length and sql[index + 1].isdigit()):
            end = index + 1
            while end < length and (sql[end].isalnum() or sql[end] == "."):
                end += 1
            tokens.append(Token(NUMBER, ""))  # the value is never kept
            index = end
        elif char in "(),;.{}[]":
            tokens.append(Token(PUNCT, char))
            index += 1
        else:
            two = sql[index : index + 2]
            if two in {"<=", ">=", "<>", "!=", "^=", "||", "=>", ":="}:
                tokens.append(Token(OP, two))
                index += 2
            else:
                tokens.append(Token(OP, char))
                index += 1
    return tokens, notes


def _word_end(sql: str, index: int) -> int:
    end = index + 1
    while end < len(sql) and (sql[end].isalnum() or sql[end] in "_$#"):
        end += 1
    return end


def _quote_prefix(sql: str, index: int) -> tuple[int, bool] | None:
    """(characters before the quote, Oracle q-quoting) for `N'`, `Q'x`, `NQ'x`; else None."""
    upper = sql[index : index + 3].upper()
    if upper.startswith("NQ'"):
        return 2, True
    if upper.startswith("Q'"):
        return 1, True
    if upper.startswith("N'"):
        return 1, False
    return None


def _string(sql: str, index: int, tokens: list[Token], notes: list[str]) -> int:
    if sql[index] == "'":
        quote, alternative = index, False
    else:
        prefix = _quote_prefix(sql, index)
        assert prefix is not None
        quote, alternative = index + prefix[0], prefix[1]
    if alternative:  # q'[...]' with any delimiter
        delimiter_at = quote + 1
        if delimiter_at >= len(sql):
            notes.append("a string literal is not closed")
            return len(sql)
        closer = _CLOSERS.get(sql[delimiter_at], sql[delimiter_at])
        end = sql.find(closer + "'", delimiter_at + 1)
        if end < 0:
            notes.append("a string literal is not closed")
            return len(sql)
        tokens.append(Token(STRING, ""))
        return end + 2
    position = quote + 1
    while True:
        end = sql.find("'", position)
        if end < 0:
            notes.append("a string literal is not closed")
            return len(sql)
        if sql.startswith("''", end):
            position = end + 2
            continue
        tokens.append(Token(STRING, ""))  # the value is never kept
        return end + 1


@dataclass
class _Level:
    clause: str = ""  # the last clause keyword at this nesting level
    query: bool = True  # a statement or subquery level (False: an expression in parentheses)


@dataclass
class _Object:
    name: str
    schema: str | None
    read: bool = False
    write: bool = False
    clauses: list[str] = field(default_factory=list)


@dataclass
class _Substitution:
    count: int = 0
    contexts: list[str] = field(default_factory=list)
    column: str | None = None


@dataclass
class _State:
    tokens: list[Token]
    statement: str | None = None
    start: int = 0
    notes: list[tuple[str, bool]] = field(default_factory=list)
    objects: dict[tuple[str, str], _Object] = field(default_factory=dict)
    binds: list[SqlBind] = field(default_factory=list)
    placeholders: dict[str, _Substitution] = field(default_factory=dict)
    ctes: list[str] = field(default_factory=list)
    joins: int = 0
    subqueries: int = 0
    where: bool = False
    group_by: bool = False
    order_by: str | None = None
    pagination: list[str] = field(default_factory=list)
    set_operations: list[str] = field(default_factory=list)
    for_update: bool = False
    insert_columns: list[str] = field(default_factory=list)

    def note(self, text: str, partial: bool = _PARTIAL) -> None:
        if (text, partial) not in self.notes:
            self.notes.append((text, partial))


def analyze_sql(sql: str) -> SqlAnalysis:
    """The structure of one SQL template; `not_analysed` when it is empty or too long."""
    if not sql.strip():
        return SqlAnalysis(status="not_analysed", notes=["the SQL template is empty"])
    if len(sql) > MAX_SQL_CHARS:
        return SqlAnalysis(status="not_analysed", notes=["the SQL template is too long"])
    tokens, lexer_notes = tokenize(sql)
    state = _State(tokens)
    for text in lexer_notes:
        state.note(text)
    procedure = _statement(state)
    if state.statement is None:
        state.note("the statement type is not recognised")
    _scan(state)
    return SqlAnalysis(
        status="partial" if any(partial for _, partial in state.notes) else "analysed",
        statement=state.statement or "OTHER",
        objects=[
            SqlObject(
                name=item.name,
                schema_name=item.schema,
                access="read-write"
                if item.read and item.write
                else ("write" if item.write else "read"),
                clauses=item.clauses,
            )
            for item in state.objects.values()
        ],
        procedure=procedure,
        ctes=state.ctes,
        joins=state.joins,
        subqueries=state.subqueries,
        where=state.where,
        group_by=state.group_by,
        order_by=state.order_by,
        pagination=state.pagination,
        set_operations=state.set_operations,
        for_update=state.for_update,
        binds=state.binds,
        placeholders=[
            SqlPlaceholder(
                name=name, occurrences=item.count, contexts=item.contexts, column=item.column
            )
            for name, item in state.placeholders.items()
        ],
        notes=[text for text, _ in state.notes],
    )


def _statement(state: _State) -> str | None:
    """Set the statement type and keyword index; return a called procedure's name."""
    tokens = state.tokens
    index = 0
    while index < len(tokens) and tokens[index].text in {"(", "{"}:
        index += 1
    if index >= len(tokens):
        return None
    first = tokens[index].upper
    if first == "WITH":
        index = _cte_names(state, index + 1)
        first = tokens[index].upper if index < len(tokens) else ""
    state.start = index
    if first in _STATEMENTS:
        state.statement = first
        return None
    if first in _CALLS:
        state.statement = "CALL"
        return _name_at(tokens, index + 1)
    if first in {"BEGIN", "DECLARE"}:
        state.statement = "CALL"
        state.note("a PL/SQL block is read only for the procedure it calls first")
        return _name_at(tokens, index + 1) if first == "BEGIN" else None
    return None


def _cte_names(state: _State, index: int) -> int:
    tokens = state.tokens
    if index < len(tokens) and tokens[index].upper == "RECURSIVE":
        index += 1
    while index < len(tokens) and tokens[index].kind in {WORD, QUOTED}:
        state.ctes.append(tokens[index].text)
        index += 1
        if index < len(tokens) and tokens[index].text == "(":
            index = _after_parentheses(tokens, index)
        if index < len(tokens) and tokens[index].upper == "AS":
            index += 1
        while index < len(tokens) and tokens[index].upper in {"NOT", "MATERIALIZED"}:
            index += 1
        if index < len(tokens) and tokens[index].text == "(":
            index = _after_parentheses(tokens, index)
        if index < len(tokens) and tokens[index].text == ",":
            index += 1
            continue
        break
    return index


def _after_parentheses(tokens: list[Token], index: int) -> int:
    depth = 0
    while index < len(tokens):
        if tokens[index].kind == PUNCT and tokens[index].text == "(":
            depth += 1
        elif tokens[index].kind == PUNCT and tokens[index].text == ")":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return index


def _name_at(tokens: list[Token], index: int) -> str | None:
    parts, _ = _chain(tokens, index)
    return ".".join(parts) if parts else None


def _chain(tokens: list[Token], index: int) -> tuple[list[str], int]:
    """An identifier chain `a.b.c` starting at `index`: (parts, index after it)."""
    parts: list[str] = []
    while index < len(tokens) and tokens[index].kind in {WORD, QUOTED}:
        parts.append(tokens[index].text)
        index += 1
        if (
            index + 1 < len(tokens)
            and tokens[index].kind == PUNCT
            and tokens[index].text == "."
            and tokens[index + 1].kind in {WORD, QUOTED}
        ):
            index += 1
            continue
        break
    return parts, index


def _chain_before(tokens: list[Token], index: int) -> str | None:
    """The identifier chain that ends at `index` (inclusive), read backwards."""
    parts: list[str] = []
    while index >= 0 and tokens[index].kind in {WORD, QUOTED}:
        if tokens[index].upper in _KEYWORD_ENDS:
            break
        parts.append(tokens[index].text)
        if index >= 2 and tokens[index - 1].kind == PUNCT and tokens[index - 1].text == ".":
            index -= 2
            continue
        break
    return ".".join(reversed(parts)) if parts else None


def _scan(state: _State) -> None:
    tokens = state.tokens
    levels = [_Level(clause=state.statement or "")]
    more_statements = False
    for index, token in enumerate(tokens):
        level = levels[-1]
        if token.kind == PUNCT and token.text == "(":
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            query = following is not None and following.upper in {"SELECT", "WITH"}
            if query:
                state.subqueries += 1
            levels.append(_Level(clause="SELECT" if query else "", query=query))
        elif token.kind == PUNCT and token.text == ")":
            if len(levels) > 1:
                levels.pop()
            else:
                state.note("the parentheses are not balanced")
        elif token.kind == PUNCT and token.text == ";":
            if not more_statements and any(t.kind != PUNCT for t in tokens[index + 1 :]):
                state.note("the template holds more than one statement")
                more_statements = True
        elif token.kind == PUNCT and token.text == ",":
            if level.query and level.clause == "FROM":
                _table(state, index + 1, "FROM", read=True)
        elif token.kind == BIND:
            state.binds.append(_bind(state, index, len(state.binds) + 1, level.clause))
        elif token.kind == NAMED_BIND:
            state.note("named bind variables (`:name`) are not JDBC parameters", _INFO)
        elif token.kind == PLACEHOLDER:
            _placeholder(state, index, level.clause)
        elif token.kind == WORD and token.upper == "ROWNUM":
            _paginate(state, "ROWNUM")
        elif token.kind == WORD and level.query:
            _word(state, index, level, top=len(levels) == 1)
    if len(levels) > 1:
        state.note("the parentheses are not balanced")


def _word(state: _State, index: int, level: _Level, *, top: bool) -> None:
    tokens = state.tokens
    word = tokens[index].upper
    previous = tokens[index - 1].upper if index > 0 else ""
    following = tokens[index + 1].upper if index + 1 < len(tokens) else ""
    statement = state.statement
    first = top and index == state.start
    if word == "SELECT":
        level.clause = "SELECT"
        if following == "TOP" and top:
            _paginate(state, "TOP")
    elif word == "FROM":
        if previous == "DELETE":
            _table(state, index + 1, "DELETE", read=False)
        else:
            _table(state, index + 1, "FROM", read=True)
        level.clause = "FROM"
    elif word == "JOIN":
        state.joins += 1
        _table(state, index + 1, "JOIN", read=True)
        level.clause = "FROM"
    elif word == "INTO":
        if statement == "INSERT" and top and level.clause in {"INSERT", "INTO", "VALUES"}:
            if previous in {"ALL", "FIRST"} or level.clause in {"INTO", "VALUES"}:
                state.note("a multi-table INSERT is read for its target tables only", _INFO)
            _insert_target(state, index + 1)
            level.clause = "INTO"
        elif statement == "MERGE" and top and previous == "MERGE":
            _table(state, index + 1, "MERGE INTO", read=False)
            level.clause = "INTO"
    elif word == "VALUES":
        level.clause = "VALUES"
    elif word == "UPDATE":
        if previous == "FOR":
            state.for_update = True
        elif statement == "UPDATE" and first:
            _table(state, index + 1, "UPDATE", read=False)
            level.clause = "UPDATE"
    elif word == "SET":
        level.clause = "SET"
    elif word == "DELETE":
        if statement == "DELETE" and first and following != "FROM":
            _table(state, index + 1, "DELETE", read=False)
    elif word == "USING":
        if statement == "MERGE" and top:
            _table(state, index + 1, "USING", read=True)
        level.clause = "USING"
    elif word == "WHERE":
        level.clause = "WHERE"
        state.where = state.where or top
    elif word == "BY" and previous == "GROUP":
        level.clause = "GROUP BY"
        state.group_by = state.group_by or top
    elif word == "BY" and previous == "ORDER":
        level.clause = "ORDER BY"
        if top:
            state.order_by = "top level"
        elif state.order_by is None:
            state.order_by = "subquery only"
    elif word in {"HAVING", "CONNECT", "START", "WINDOW", "RETURNING"}:
        level.clause = word
    elif word in _SET_OPERATIONS:
        if word not in state.set_operations:
            state.set_operations.append(word)
        level.clause = word
    elif word == "OFFSET" and top:
        _paginate(state, "OFFSET ... ROWS")
        level.clause = "OFFSET"
    elif word == "FETCH" and top and following in {"FIRST", "NEXT"}:
        _paginate(state, f"FETCH {following} ... ROWS")
        level.clause = "FETCH"
    elif word == "LIMIT" and top:
        _paginate(state, "LIMIT")
        level.clause = "LIMIT"
    elif word == "TABLE" and index + 1 < len(tokens) and tokens[index + 1].text == "(":
        if level.clause == "FROM":
            state.note("a TABLE(...) collection expression is not read as a table")


def _paginate(state: _State, kind: str) -> None:
    if kind not in state.pagination:
        state.pagination.append(kind)


def _insert_target(state: _State, index: int) -> None:
    after = _table(state, index, "INSERT INTO", read=False)
    tokens = state.tokens
    if after is None or after >= len(tokens) or tokens[after].text != "(":
        return
    following = tokens[after + 1] if after + 1 < len(tokens) else None
    if following is None or following.upper in {"SELECT", "WITH"}:
        return
    columns: list[str] = []
    position = after + 1
    while position < len(tokens) and tokens[position].text != ")":
        if tokens[position].kind in {WORD, QUOTED}:
            columns.append(tokens[position].text)
        position += 1
    state.insert_columns = columns


def _table(state: _State, index: int, clause: str, *, read: bool) -> int | None:
    """Record the table named at `index`; the index after its name, or None."""
    tokens = state.tokens
    while index < len(tokens) and tokens[index].upper in {"ONLY", "LATERAL"}:
        index += 1
    if index >= len(tokens):
        return None
    token = tokens[index]
    if token.kind == PLACEHOLDER:
        state.note(
            f"a table name comes from the substitution `${{{token.text}}}`: "
            "the table is known only at run time"
        )
        _substitution(state, token.text, "object name", None)
        return index + 1
    if token.kind not in {WORD, QUOTED} or token.upper in _NOT_TABLES:
        return None  # a subquery or an expression, read as it comes
    parts, after = _chain(tokens, index)
    quoted = tokens[after - 1].kind == QUOTED
    if after < len(tokens) and tokens[after].text == "@":
        state.note("a table is reached through a database link", _INFO)
        after += 1
        if after < len(tokens) and tokens[after].kind in {WORD, QUOTED}:
            after += 1
    if after < len(tokens) and tokens[after].text == "(" and clause in {"FROM", "JOIN"}:
        state.note(f"`{'.'.join(parts)}(...)` is a table function, not read as a table", _INFO)
        return None
    name = parts[-1]
    schema = ".".join(parts[:-1]) or None
    if schema is None and not quoted and name.upper() in _PSEUDO_TABLES:
        state.note(f"`{name}` (a one-row pseudo-table) is not listed as a table", _INFO)
        return after
    if schema is None and any(name.casefold() == cte.casefold() for cte in state.ctes):
        return after
    key = ((schema or "").upper(), name if quoted else name.upper())
    item = state.objects.setdefault(key, _Object(name, schema))
    if read:
        item.read = True
    else:
        item.write = True
    if clause not in item.clauses:
        item.clauses.append(clause)
    return after


def _comparison_before(tokens: list[Token], index: int) -> tuple[str | None, str | None]:
    """(column, operator) for `column op <index>`; (None, None) when the SQL does not show it."""
    if index < 2:
        return None, None
    before = tokens[index - 1]
    if before.kind == OP and before.text in _COMPARISONS:
        return _chain_before(tokens, index - 2), before.text
    if before.upper == "LIKE":
        negated = index >= 3 and tokens[index - 2].upper == "NOT"
        return _chain_before(tokens, index - (3 if negated else 2)), (
            "NOT LIKE" if negated else "LIKE"
        )
    if before.upper == "BETWEEN":
        return _chain_before(tokens, index - 2), "BETWEEN"
    if before.upper == "AND" and index >= 4 and tokens[index - 3].upper == "BETWEEN":
        return _chain_before(tokens, index - 4), "BETWEEN"  # the upper bound
    return None, None


def _comparison_after(tokens: list[Token], index: int) -> tuple[str | None, str | None]:
    if index + 2 >= len(tokens):
        return None, None
    after = tokens[index + 1]
    if after.kind != OP or after.text not in _COMPARISONS:
        return None, None
    if tokens[index + 2].upper in {"SELECT", "NULL"}:
        return None, None
    parts, _ = _chain(tokens, index + 2)
    return (".".join(parts), _MIRRORED.get(after.text, after.text)) if parts else (None, None)


def _in_list(tokens: list[Token], index: int) -> tuple[str | None, int | None]:
    """(column, None) for an item of `column IN (...)`; (None, item) for `VALUES (...)`."""
    depth = 0
    position = 0
    cursor = index - 1
    while cursor >= 0:
        token = tokens[cursor]
        if token.kind == PUNCT and token.text == ")":
            depth += 1
        elif token.kind == PUNCT and token.text == "(":
            if depth > 0:
                depth -= 1
            else:
                before = tokens[cursor - 1] if cursor > 0 else None
                if before is not None and before.upper == "IN":
                    negated = cursor >= 3 and tokens[cursor - 2].upper == "NOT"
                    return _chain_before(tokens, cursor - (3 if negated else 2)), None
                if before is not None and before.upper == "VALUES":
                    return None, position
                return None, None
        elif depth == 0:
            if token.kind == PUNCT and token.text == ",":
                position += 1
            elif token.kind not in {BIND, PLACEHOLDER, STRING, NUMBER}:
                return None, None  # an expression, not a plain list item
        cursor -= 1
    return None, None


def _bind(state: _State, index: int, position: int, clause: str) -> SqlBind:
    tokens = state.tokens
    if clause == "OFFSET":
        return SqlBind(position=position, role="row offset")
    if clause in {"FETCH", "LIMIT"}:
        return SqlBind(position=position, role="row limit")
    column, operator = _comparison_before(tokens, index)
    if column is None:
        column, operator = _comparison_after(tokens, index)
    if column is None:
        listed, item = _in_list(tokens, index)
        if listed is not None:
            column, operator = listed, "IN"
        elif item is not None and item < len(state.insert_columns):
            column, operator = state.insert_columns[item], "value of"
    if column is not None and column.upper() == "ROWNUM":
        return SqlBind(position=position, column=column, operator=operator, role="row limit")
    if operator == "=" and clause == "SET":
        operator = "set"
    return SqlBind(position=position, column=column, operator=operator)


def _placeholder(state: _State, index: int, clause: str) -> None:
    tokens = state.tokens
    name = tokens[index].text
    previous = tokens[index - 1] if index > 0 else None
    if previous is not None and previous.upper in {"FROM", "JOIN", "INTO", "UPDATE", "USING"}:
        return  # recorded by _table as an object name
    if previous is not None and previous.text == "," and clause == "FROM":
        return  # recorded by _table as an object name
    column, _ = _comparison_before(tokens, index)
    if column is None:
        column, _ = _comparison_after(tokens, index)
    if column is not None:
        _substitution(state, name, "comparison", column)
        return
    listed, _ = _in_list(tokens, index)
    if listed is not None:
        _substitution(state, name, "value list", listed)
    elif clause == "ORDER BY":
        _substitution(state, name, "ordering", None)
    else:
        _substitution(state, name, "other SQL text", None)


def _substitution(state: _State, name: str, context: str, column: str | None) -> None:
    item = state.placeholders.setdefault(name, _Substitution())
    item.count += 1
    if context not in item.contexts:
        item.contexts.append(context)
    if column is not None and item.column is None:
        item.column = column
