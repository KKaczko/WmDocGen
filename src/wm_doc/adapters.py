"""JDBC adapter configuration from the binary `IRTNODE_PROPERTY` value (owner-approved, M12).

JDBC adapter services (`svc_type` AdapterService), connections (`node_type` ConnectionData)
and notifications (`node_type` AdapterRuntimeNotification) keep their configuration as a
base64 binary IData document.

Adapter services are decoded completely by `wm_doc.idata_binary` (checked against the
documents Integration Server 10.15 itself decodes, `samples/jdbcadapter/`) and then
interpreted here (owner decision, M15):

- every template: `serviceTemplateName`, `connectionName`, `adapterType`, `tables.tableName`,
  `tables.schemaName`, the metadata and node versions and the record names;
- `DynamicSQL` and `CustomSQL` (the templates checked on real samples) also: the SQL template
  (under the free-text policy, secret guard first), the DynamicSQL variables, the parallel
  input and output arrays (field, Java type, JDBC type, result field), the maximum rows,
  query timeout and row-count field, and a structural reading of the SQL
  (`wm_doc.sql_analysis`). Other templates keep the identity only and list their property
  names as not interpreted.

The user and password override settings (`userid`, `password` and their `*Type` / `input*Sign`
companions) and any secret-like key are never read. When the decoder meets a structure it
does not support, the M12 reader below is used instead: it scans for the allow-listed
identity keys only (every string is the byte 0x04, a one-byte length and that many UTF-16BE
characters; a value is the string right after its key; `tables.*` arrays put
`0a <count> 00 <byte>` before their items), and the result is marked `partial`.

Connections and notifications are read by that M12 reader (no real sample of their documents
has been checked yet). Only these keys are read, and each value must look like what the key
names (a Java class, a node name, a table name...), or it is dropped:

- connections: `adapterTypeName`, `datasourceClass`, `databaseName`, `transactionType`;
- notifications: `notificationClassName`, `adapterTypeName`, `connDataNodeName`,
  `publishableDocumentName`, `tables.tableName`, `tables.schemaName`.

Server, host, port, user, password, URL and every other connection property are skipped
without being decoded into text that is kept anywhere.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable
from dataclasses import dataclass

from wm_doc.idata_binary import (
    BinaryArray,
    BinaryDocument,
    IDataBinaryError,
    Value,
    decode_base64,
    decode_idata_hypotheses,
    walk,
)
from wm_doc.ir import (
    AdapterDecoding,
    AdapterDetails,
    AdapterRole,
    JdbcField,
    JdbcServiceConfig,
    JdbcVariable,
    TextDisclosure,
    TextValue,
)
from wm_doc.secret_guard import is_secret_name
from wm_doc.sql_analysis import analyze_sql

STRING_TOKEN = 0x04
ARRAY_MARKER = 0x0A
MAX_BLOB_BYTES = 1_000_000
MAX_TABLES = 20

SERVICE_TYPE = "AdapterService"
CONNECTION_NODE_TYPE = "ConnectionData"
NOTIFICATION_NODE_TYPE = "AdapterRuntimeNotification"
JDBC_TEMPLATE_PREFIX = "com.wm.adapter.wmjdbc."

_JAVA_CLASS_RE = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)+$")
_NODE_NAME_RE = re.compile(r"^[\w.$-]+:[\w.$-]+$")
_SIMPLE_NAME_RE = re.compile(r"^[\w.$-]{1,128}$")
_TABLE_RE = re.compile(r'^[\w$#." -]{1,128}$')
_TRANSACTION_RE = re.compile(r"^[A-Z_]{1,40}$")

# Placeholders the adapter stores when no schema or catalog was chosen.
_PLACEHOLDERS = {"<current schema>", "<current catalog>", ""}

# Database product by datasource class prefix (documented driver packages).
_PRODUCTS: tuple[tuple[str, str], ...] = (
    ("oracle.", "Oracle"),
    ("com.wm.dd.jdbc.oracle.", "Oracle"),
    ("org.postgresql.", "PostgreSQL"),
    ("com.mysql.", "MySQL"),
    ("com.wm.dd.jdbc.mysql.", "MySQL"),
    ("org.mariadb.", "MariaDB"),
    ("com.microsoft.sqlserver.", "Microsoft SQL Server"),
    ("com.wm.dd.jdbc.sqlserver.", "Microsoft SQL Server"),
    ("net.sourceforge.jtds.", "Microsoft SQL Server or Sybase (jTDS)"),
    ("com.ibm.db2.", "IBM Db2"),
    ("com.ibm.as400.", "IBM Db2 for i"),
    ("com.wm.dd.jdbc.db2.", "IBM Db2"),
    ("com.sybase.", "Sybase"),
    ("com.wm.dd.jdbc.sybase.", "Sybase"),
    ("com.informix.", "Informix"),
    ("com.wm.dd.jdbc.informix.", "Informix"),
    ("com.teradata.", "Teradata"),
    ("org.apache.derby.", "Apache Derby"),
    ("org.h2.", "H2"),
    ("org.hsqldb.", "HSQLDB"),
)

# Operation wording per JDBC service template class (simple name).
OPERATIONS: dict[str, tuple[str, str]] = {
    # template: (action with a table, action without one)
    "Select": ("selects rows from", "selects rows"),
    "Insert": ("inserts rows into", "inserts rows"),
    "Update": ("updates rows in", "updates rows"),
    "Delete": ("deletes rows from", "deletes rows"),
    "BatchInsert": ("batch-inserts rows into", "batch-inserts rows"),
    "BatchUpdate": ("batch-updates rows in", "batch-updates rows"),
    "CustomSQL": ("runs custom SQL on", "runs custom SQL (not interpreted)"),
    "DynamicSQL": ("runs dynamic SQL on", "runs dynamic SQL (not interpreted)"),
    "StoredProcedure": ("calls a stored procedure on", "calls a stored procedure"),
    "StoredProcedureWithSignature": ("calls a stored procedure on", "calls a stored procedure"),
    "ExecuteService": ("runs an adapter operation on", "runs an adapter operation"),
}


@dataclass(frozen=True)
class _Token:
    start: int
    end: int
    text: str


Validator = Callable[[str], str | None]


def _matching(pattern: re.Pattern[str]) -> Validator:
    def check(value: str) -> str | None:
        text = value.strip()
        return text if pattern.match(text) else None

    return check


_SERVICE_KEYS: dict[str, Validator] = {
    "serviceTemplateName": _matching(_JAVA_CLASS_RE),
    "connectionName": _matching(_NODE_NAME_RE),
    "adapterType": _matching(_SIMPLE_NAME_RE),
}
_CONNECTION_KEYS: dict[str, Validator] = {
    "adapterTypeName": _matching(_SIMPLE_NAME_RE),
    "datasourceClass": _matching(_JAVA_CLASS_RE),
    "databaseName": _matching(_SIMPLE_NAME_RE),
    "transactionType": _matching(_TRANSACTION_RE),
}
_NOTIFICATION_KEYS: dict[str, Validator] = {
    "notificationClassName": _matching(_JAVA_CLASS_RE),
    "adapterTypeName": _matching(_SIMPLE_NAME_RE),
    "connDataNodeName": _matching(_NODE_NAME_RE),
    "publishableDocumentName": _matching(_SIMPLE_NAME_RE),
}
_TABLE_KEYS = ("tables.tableName", "tables.schemaName")


class AdapterDecodeError(ValueError):
    """The value is not the expected base64 binary layout."""


# Templates whose document layout was checked against real IS 10.15 samples.
SUPPORTED_TEMPLATES = ("DynamicSQL", "CustomSQL")

# Never read: the user/password override settings of a service.
_CREDENTIAL_KEYS = frozenset(
    {"userid", "useridType", "inputUseridSign", "password", "passwordType", "inputPasswordSign"}
)
# Template properties read for DynamicSQL and CustomSQL.
_INTERPRETED = frozenset(
    {
        "sql", "sqlFieldType", "sqlOutputField", "sqlVariables", "sqlInputFields",
        "sqlInputFieldTypes", "inputField", "inputFieldType", "inputJDBCType", "outputField",
        "outputFieldType", "outputJDBCType", "resultField", "resultFieldType", "maxRow",
        "queryTimeOut", "resultRowField", "resultRowFieldType",
    }
)
MAX_NAME_CHARS = 256
MAX_FIELDS = 500
_JAVA_TYPE_RE = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*(?:\[\])*$")
_JDBC_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_ ]{0,63}$")
_NUMBER_TEXT_RE = re.compile(r"^-?\d{1,10}$")

SqlText = Callable[[str], TextValue | None]


def _sql_withheld(sql: str) -> TextValue:
    return TextValue(
        present=True, role="adapter.sql", disclosure=TextDisclosure.OMITTED, length=len(sql)
    )


def decode_adapter_service(blob: str, *, sql_text: SqlText | None = None) -> AdapterDetails:
    """The configuration of an adapter service node.

    `sql_text` applies the free-text policy to the SQL template (`analysis.py` passes it);
    without it the SQL text is not kept. AdapterDecodeError: the value is not base64.
    """
    try:
        raw = decode_base64(blob)
    except IDataBinaryError as exc:
        raise AdapterDecodeError(exc.code) from exc
    try:
        decoded = decode_idata_hypotheses(raw)
    except IDataBinaryError as exc:
        # A structure the decoder does not support: the M12 reader finds the identity keys.
        values, tables = _read_raw(raw, _SERVICE_KEYS, with_tables=True)
        template = values.get("serviceTemplateName")
        return AdapterDetails(
            role=AdapterRole.SERVICE,
            adapter_type=values.get("adapterType"),
            template=template,
            operation=_simple_name(template),
            connection=values.get("connectionName"),
            tables=tables,
            decoding=AdapterDecoding.PARTIAL,
            decode_problem=f"{exc.code}: {exc}",
        )
    details = _service_from_document(decoded.document, sql_text or _sql_withheld)
    if decoded.hypotheses:
        details = details.model_copy(update={"decode_hypotheses": list(decoded.hypotheses)})
    return details


def _service_from_document(document: BinaryDocument, sql_text: SqlText) -> AdapterDetails:
    template = _checked(document.get("serviceTemplateName"), _SERVICE_KEYS["serviceTemplateName"])
    operation = _simple_name(template)
    jdbc = (
        _jdbc_config(document, operation, sql_text)
        if operation and template and template.startswith(JDBC_TEMPLATE_PREFIX)
        else None
    )
    return AdapterDetails(
        role=AdapterRole.SERVICE,
        adapter_type=_checked(document.get("adapterType"), _SERVICE_KEYS["adapterType"]),
        template=template,
        operation=operation,
        connection=_checked(document.get("connectionName"), _SERVICE_KEYS["connectionName"]),
        tables=_document_tables(document),
        decoding=AdapterDecoding.DECODED,
        jdbc=jdbc,
    )


def _checked(value: Value | None, validator: Validator) -> str | None:
    return validator(value) if isinstance(value, str) else None


def _document_tables(document: BinaryDocument) -> list[str]:
    """`tables.tableName` / `tables.schemaName` arrays, wherever the document holds them."""
    parts: dict[str, list[str]] = {}
    for key, value in walk(document):
        if key in _TABLE_KEYS and key not in parts and isinstance(value, BinaryArray):
            parts[key] = [
                item.strip() for item in value.items[:MAX_TABLES] if isinstance(item, str)
            ]
    return _tables(parts)


def _jdbc_config(
    document: BinaryDocument, kind: str, sql_text: SqlText
) -> JdbcServiceConfig:
    issues: list[str] = []
    properties = document.get("templateProperties")
    metadata_version = _integer(document.get("metadataVersion"))
    node_version = _integer(document.get("adapterServiceNodeVersion"))
    input_record = _name(document.get("inputRecordName"), "inputRecordName", issues)
    output_record = _name(document.get("outputRecordName"), "outputRecordName", issues)
    if not isinstance(properties, BinaryDocument):
        issues.append("the configuration has no `templateProperties` document")
        return JdbcServiceConfig(
            template_kind=kind,
            supported=False,
            metadata_version=metadata_version,
            node_version=node_version,
            input_record=input_record,
            output_record=output_record,
            issues=_unique(issues),
        )
    readable = [key for key, _ in properties.entries if _readable_key(key)]
    if kind not in SUPPORTED_TEMPLATES:
        return JdbcServiceConfig(
            template_kind=kind,
            supported=False,
            metadata_version=metadata_version,
            node_version=node_version,
            input_record=input_record,
            output_record=output_record,
            uninterpreted=sorted(set(readable), key=str.casefold),
            issues=_unique(issues),
        )
    sql_value = properties.get("sql")
    sql = sql_value if isinstance(sql_value, str) else None
    if sql_value is not None and sql is None:
        issues.append("`sql` is not text")
    variables = _parallel(
        properties, ("sqlVariables", "sqlInputFields", "sqlInputFieldTypes"), issues
    )
    inputs = _parallel(properties, ("inputField", "inputFieldType", "inputJDBCType"), issues)
    outputs = _parallel(
        properties,
        ("outputField", "outputFieldType", "outputJDBCType", "resultField", "resultFieldType"),
        issues,
    )
    return JdbcServiceConfig(
        template_kind=kind,
        supported=True,
        metadata_version=metadata_version,
        node_version=node_version,
        input_record=input_record,
        output_record=output_record,
        sql=sql_text(sql) if sql is not None else None,
        sql_field_type=_java_type(properties.get("sqlFieldType"), "sqlFieldType", issues),
        sql_output_field=_name(properties.get("sqlOutputField"), "sqlOutputField", issues),
        variables=[
            JdbcVariable(
                name=name,
                field=_name(row[1], "sqlInputFields", issues),
                field_type=_java_type(row[2], "sqlInputFieldTypes", issues),
            )
            for row in variables
            if (name := _name(row[0], "sqlVariables", issues)) is not None
        ],
        inputs=[
            JdbcField(
                position=position,
                field=_name(row[0], "inputField", issues),
                field_type=_java_type(row[1], "inputFieldType", issues),
                jdbc_type=_jdbc_type(row[2], issues),
            )
            for position, row in enumerate(inputs, start=1)
        ],
        outputs=[
            JdbcField(
                position=position,
                field=_name(row[0], "outputField", issues),
                field_type=_java_type(row[1], "outputFieldType", issues),
                jdbc_type=_jdbc_type(row[2], issues),
                result_field=_name(row[3], "resultField", issues),
                result_type=_java_type(row[4], "resultFieldType", issues),
            )
            for position, row in enumerate(outputs, start=1)
        ],
        max_rows=_number_text(properties.get("maxRow"), "maxRow", issues),
        query_timeout=_number_text(properties.get("queryTimeOut"), "queryTimeOut", issues),
        result_row_field=_name(properties.get("resultRowField"), "resultRowField", issues),
        result_row_field_type=_java_type(
            properties.get("resultRowFieldType"), "resultRowFieldType", issues
        ),
        uninterpreted=sorted(
            {key for key in readable if key not in _INTERPRETED}, key=str.casefold
        ),
        issues=_unique(issues),
        sql_analysis=analyze_sql(sql) if sql is not None else None,
    )


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _readable_key(key: str) -> bool:
    return key not in _CREDENTIAL_KEYS and not is_secret_name(key)


def _parallel(
    properties: BinaryDocument, keys: tuple[str, ...], issues: list[str]
) -> list[tuple[Value | None, ...]]:
    """Rows of parallel arrays, position by position; None where an array is shorter."""
    columns: list[tuple[Value, ...]] = []
    for key in keys:
        value = properties.get(key)
        if value is None:
            columns.append(())
        elif isinstance(value, BinaryArray):
            columns.append(value.items[:MAX_FIELDS])
        else:
            issues.append(f"`{key}` is not an array")
            columns.append(())
    present = set(properties.keys())
    lengths = {
        len(column) for column, key in zip(columns, keys, strict=True) if key in present
    }
    if len(lengths) > 1:
        issues.append(
            "the arrays " + ", ".join(f"`{key}`" for key in keys) + " have different lengths"
        )
    rows = max((len(column) for column in columns), default=0)
    return [
        tuple(column[row] if row < len(column) else None for column in columns)
        for row in range(rows)
    ]


def _integer(value: Value | None) -> int | None:
    return value if isinstance(value, int) else None


def _plain(value: Value | None, key: str, issues: list[str]) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        issues.append(f"a value of `{key}` is not text")
        return None
    if len(value) > MAX_NAME_CHARS or not value.isprintable():
        issues.append(f"a value of `{key}` is not a plain name")
        return None
    return value


def _name(value: Value | None, key: str, issues: list[str]) -> str | None:
    return _plain(value, key, issues)


def _java_type(value: Value | None, key: str, issues: list[str]) -> str | None:
    text = _plain(value, key, issues)
    if text is None or text == "":
        return text
    if not _JAVA_TYPE_RE.match(text):
        issues.append(f"a value of `{key}` is not a Java type name")
        return None
    return text


def _jdbc_type(value: Value | None, issues: list[str]) -> str | None:
    text = _plain(value, "JDBC type", issues)
    if text is None or text == "":
        return text
    if not _JDBC_TYPE_RE.match(text):
        issues.append("a JDBC type is not a type name")
        return None
    return text


def _number_text(value: Value | None, key: str, issues: list[str]) -> str | None:
    text = _plain(value, key, issues)
    if text is None or text == "" or _NUMBER_TEXT_RE.match(text):
        return text
    issues.append(f"`{key}` is not a number")
    return None


# Wording per SQL statement type, for decoded DynamicSQL and CustomSQL services.
SQL_ACTIONS: dict[str, tuple[str, str]] = {
    # statement: (on a table it reads, on a table it writes)
    "SELECT": ("reads", "reads"),
    "INSERT": ("reads", "inserts rows into"),
    "UPDATE": ("reads", "updates rows in"),
    "DELETE": ("reads", "deletes rows from"),
    "MERGE": ("reads", "merges rows into"),
    "CALL": ("reads", "changes"),
}


def sql_action(statement: str | None, access: str) -> str:
    """`reads` / `inserts rows into` ... for one table of an analysed SQL template."""
    read, write = SQL_ACTIONS.get(statement or "", ("reads", "changes"))
    if access == "read-write":
        return f"{read} and {write}" if read != write else read
    return write if access == "write" else read


def decode_connection(blob: str) -> AdapterDetails:
    values, _ = _read(blob, _CONNECTION_KEYS, with_tables=False)
    datasource = values.get("datasourceClass")
    return AdapterDetails(
        role=AdapterRole.CONNECTION,
        adapter_type=values.get("adapterTypeName"),
        datasource_class=datasource,
        database_product=database_product(datasource),
        database_name=values.get("databaseName"),
        transaction_type=values.get("transactionType"),
    )


def decode_notification(blob: str, notification_full_name: str) -> AdapterDetails:
    values, tables = _read(blob, _NOTIFICATION_KEYS, with_tables=True)
    template = values.get("notificationClassName")
    document = values.get("publishableDocumentName")
    namespace = notification_full_name.rpartition(":")[0]
    return AdapterDetails(
        role=AdapterRole.NOTIFICATION,
        adapter_type=values.get("adapterTypeName"),
        template=template,
        operation=_simple_name(template),
        connection=values.get("connDataNodeName"),
        tables=tables,
        # The notification publishes a document type created next to it.
        published_document=f"{namespace}:{document}" if document and namespace else None,
    )


def database_product(datasource_class: str | None) -> str | None:
    if not datasource_class:
        return None
    for prefix, product in _PRODUCTS:
        if datasource_class.startswith(prefix):
            return product
    return None


def is_jdbc(details: AdapterDetails) -> bool:
    return (details.adapter_type or "").casefold() == "jdbcadapter" or (
        details.template or ""
    ).startswith(JDBC_TEMPLATE_PREFIX)


def operation_phrase(details: AdapterDetails) -> str:
    """`selects rows from` / `runs custom SQL (not interpreted)` for a service's template.

    A decoded DynamicSQL or CustomSQL service whose SQL was read names its statement type
    instead: `runs custom SQL (SELECT)`.
    """
    jdbc = details.jdbc
    analysis = jdbc.sql_analysis if jdbc is not None and jdbc.supported else None
    if analysis is not None and analysis.status != "not_analysed" and analysis.statement:
        kind = "dynamic SQL" if details.operation == "DynamicSQL" else "custom SQL"
        return f"runs {kind} ({analysis.statement})"
    with_table, without = OPERATIONS.get(details.operation or "", ("uses", "runs an operation"))
    return with_table if details.tables else without


def sql_objects_phrase(details: AdapterDetails) -> str:
    """`reading table `A` and writing table `B`` from an analysed SQL template, or ""."""
    jdbc = details.jdbc
    analysis = jdbc.sql_analysis if jdbc is not None and jdbc.supported else None
    if analysis is None:
        return ""
    groups: dict[str, list[str]] = {"read": [], "write": [], "read-write": []}
    for item in analysis.objects:
        name = f"{item.schema_name}.{item.name}" if item.schema_name else item.name
        groups[item.access].append(f"`{name}`")
    parts = []
    verbs = (("read", "reading"), ("write", "writing"), ("read-write", "reading and writing"))
    for access, verb in verbs:
        names = groups[access]
        if names:
            noun = "table" if len(names) == 1 else "tables"
            parts.append(f"{verb} {noun} {', '.join(names)}")
    if analysis.procedure:
        parts.append(f"calling procedure `{analysis.procedure}`")
    return " and ".join(parts)


def _simple_name(class_name: str | None) -> str | None:
    return class_name.rsplit(".", 1)[-1] if class_name else None


def _read(
    blob: str, keys: dict[str, Validator], *, with_tables: bool
) -> tuple[dict[str, str], list[str]]:
    return _read_raw(_decode(blob), keys, with_tables=with_tables)


def _read_raw(
    raw: bytes, keys: dict[str, Validator], *, with_tables: bool
) -> tuple[dict[str, str], list[str]]:
    """The M12 reader: allow-listed keys found by scanning for string tokens."""
    tokens = _tokens(raw)
    values: dict[str, str] = {}
    table_parts: dict[str, list[str]] = {}
    for index, token in enumerate(tokens[:-1]):
        key = token.text
        following = tokens[index + 1]
        if key in keys and key not in values and following.start == token.end:
            checked = keys[key](following.text)
            if checked is not None:
                values[key] = checked
        elif with_tables and key in _TABLE_KEYS and key not in table_parts:
            table_parts[key] = _array_items(raw, tokens, index)
    return values, _tables(table_parts)


def _decode(blob: str) -> bytes:
    try:
        raw = base64.b64decode("".join(blob.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AdapterDecodeError("not base64") from exc
    if not raw or len(raw) > MAX_BLOB_BYTES:
        raise AdapterDecodeError("unexpected size")
    return raw


def _tokens(raw: bytes) -> list[_Token]:
    """Every well-formed string token, scanning byte by byte past anything else."""
    tokens: list[_Token] = []
    index = 0
    while index < len(raw) - 1:
        if raw[index] == STRING_TOKEN:
            length = raw[index + 1]
            end = index + 2 + 2 * length
            if end <= len(raw):
                try:
                    text = raw[index + 2 : end].decode("utf-16-be")
                except UnicodeDecodeError:
                    text = None
                if text is not None and all(c.isprintable() for c in text):
                    tokens.append(_Token(index, end, text))
                    index = end
                    continue
        index += 1
    return tokens


def _array_items(raw: bytes, tokens: list[_Token], key_index: int) -> list[str]:
    """Items of the string array after a `tables.*` key: `0a <count> 00 xx` then strings."""
    key = tokens[key_index]
    header = raw[key.end : key.end + 4]
    if len(header) < 4 or header[0] != ARRAY_MARKER or header[2] != 0:
        return []
    count = header[1]
    items: list[str] = []
    position = key.end + 4
    for token in tokens[key_index + 1 :]:
        if len(items) >= min(count, MAX_TABLES) or token.start != position:
            break
        items.append(token.text.strip())
        position = token.end
    return items


def _tables(parts: dict[str, list[str]]) -> list[str]:
    names = parts.get("tables.tableName", [])
    schemas = parts.get("tables.schemaName", [])
    tables: list[str] = []
    for index, name in enumerate(names):
        if not _TABLE_RE.match(name) or name in _PLACEHOLDERS:
            continue
        schema = schemas[index] if index < len(schemas) else ""
        qualified = f"{schema}.{name}" if schema not in _PLACEHOLDERS and _TABLE_RE.match(
            schema
        ) else name
        if qualified not in tables:
            tables.append(qualified)
    return tables
