"""JDBC adapter configuration from the binary `IRTNODE_PROPERTY` value (owner-approved, M12).

JDBC adapter services (`svc_type` AdapterService), connections (`node_type` ConnectionData)
and notifications (`node_type` AdapterRuntimeNotification) keep their configuration as a
base64 binary value. Inside it, every string is the byte 0x04, a one-byte length and that
many UTF-16BE characters; a property's value is the string right after its key, and a
string array (the `tables.*` keys) puts `0a <count> 00 <byte>` between the key and its
items.

Only these keys are read, and each value must look like what the key names (a Java class,
a node name, a table name...), or it is dropped:

- services: `serviceTemplateName`, `connectionName`, `adapterType`, `tables.tableName`,
  `tables.schemaName`;
- connections: `adapterTypeName`, `datasourceClass`, `databaseName`, `transactionType`;
- notifications: `notificationClassName`, `adapterTypeName`, `connDataNodeName`,
  `publishableDocumentName`, `tables.tableName`, `tables.schemaName`.

Server, host, port, user, password, URL, SQL and every other property are skipped without
being decoded into text that is kept anywhere.
"""

from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable
from dataclasses import dataclass

from wm_doc.ir import AdapterDetails, AdapterRole

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


def decode_adapter_service(blob: str) -> AdapterDetails:
    values, tables = _read(blob, _SERVICE_KEYS, with_tables=True)
    template = values.get("serviceTemplateName")
    return AdapterDetails(
        role=AdapterRole.SERVICE,
        adapter_type=values.get("adapterType"),
        template=template,
        operation=_simple_name(template),
        connection=values.get("connectionName"),
        tables=tables,
    )


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
    """`selects rows from` / `runs custom SQL (not interpreted)` for a service's template."""
    with_table, without = OPERATIONS.get(details.operation or "", ("uses", "runs an operation"))
    return with_table if details.tables else without


def _simple_name(class_name: str | None) -> str | None:
    return class_name.rsplit(".", 1)[-1] if class_name else None


def _read(
    blob: str, keys: dict[str, Validator], *, with_tables: bool
) -> tuple[dict[str, str], list[str]]:
    raw = _decode(blob)
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
