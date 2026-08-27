"""Static catalog of webMethods platform (``pub.*`` / ``wm.*``) service effects.

Built-in services are never present in an analyzed package, so they can never be
resolved from a snapshot. Before M9 they were reported only as unresolved targets
with ``UNKNOWN`` type, which discarded the richest semantic signal a FLOW carries:
``pub.art.transaction:startTransaction`` means the service is transactional, and
``pub.publish:publish`` means it emits a message.

This module is a fixed name-to-label lookup over documented platform services. It
does not parse adapters, triggers or resources, and it never infers behaviour for a
name it does not know -- unknown built-ins keep their previous unresolved treatment.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

BUILTIN_PREFIXES = ("pub.", "wm.")


class BuiltinFamily(StrEnum):
    """Coarse effect family used to derive a service layer and summary sentence."""

    TRANSACTION = "TRANSACTION"
    MESSAGING = "MESSAGING"
    REMOTE = "REMOTE"
    FILE = "FILE"
    IO = "IO"
    XML = "XML"
    JSON = "JSON"
    FLAT_FILE = "FLAT_FILE"
    DOCUMENT = "DOCUMENT"
    STRING = "STRING"
    DATE = "DATE"
    NUMERIC = "NUMERIC"
    LIST = "LIST"
    ERROR_HANDLING = "ERROR_HANDLING"
    FLOW_CONTROL = "FLOW_CONTROL"
    SECURITY = "SECURITY"
    SCHEMA = "SCHEMA"


@dataclass(frozen=True)
class BuiltinEffect:
    """A plain-language effect for one documented platform service."""

    label: str
    family: BuiltinFamily


_T = BuiltinFamily

# (service name, effect label, family). Only documented platform services appear here.
_CATALOG: tuple[tuple[str, str, BuiltinFamily], ...] = (
    ("pub.art.transaction:startTransaction", "starts a transaction", _T.TRANSACTION),
    ("pub.art.transaction:commitTransaction", "commits a transaction", _T.TRANSACTION),
    ("pub.art.transaction:rollbackTransaction", "rolls back a transaction", _T.TRANSACTION),
    ("pub.art.transaction:setTransactionTimeout", "sets a transaction timeout", _T.TRANSACTION),
    ("pub.publish:publish", "publishes a message", _T.MESSAGING),
    ("pub.publish:publishAndWait", "publishes a message and waits for a reply", _T.MESSAGING),
    ("pub.publish:deliver", "delivers a message to a destination", _T.MESSAGING),
    ("pub.publish:reply", "replies to a published message", _T.MESSAGING),
    ("pub.client:http", "calls an external HTTP endpoint", _T.REMOTE),
    ("pub.client:soapHTTP", "calls an external SOAP endpoint", _T.REMOTE),
    ("pub.client.ftp:put", "uploads a file over FTP", _T.REMOTE),
    ("pub.client.ftp:get", "downloads a file over FTP", _T.REMOTE),
    ("pub.remote:invoke", "invokes a service on a remote server", _T.REMOTE),
    ("pub.file:getFile", "reads a file", _T.FILE),
    ("pub.file:stringToFile", "writes a string to a file", _T.FILE),
    ("pub.file:bytesToFile", "writes bytes to a file", _T.FILE),
    ("pub.file:listFiles", "lists files in a directory", _T.FILE),
    ("pub.file:copy", "copies a file", _T.FILE),
    ("pub.file:delete", "deletes a file", _T.FILE),
    ("pub.file:move", "moves a file", _T.FILE),
    ("pub.io:close", "closes a stream", _T.IO),
    ("pub.io:streamToBytes", "reads a stream into bytes", _T.IO),
    ("pub.io:streamToString", "reads a stream into a string", _T.IO),
    ("pub.io:bytesToStream", "opens a stream over bytes", _T.IO),
    ("pub.xml:xmlStringToXMLNode", "parses XML text", _T.XML),
    ("pub.xml:xmlNodeToDocument", "converts XML into a document", _T.XML),
    ("pub.xml:documentToXMLString", "serializes a document as XML", _T.XML),
    ("pub.xml:queryXMLNode", "queries an XML node", _T.XML),
    ("pub.xml:freeXMLNode", "releases an XML node", _T.XML),
    ("pub.json:documentToJSONString", "serializes a document as JSON", _T.JSON),
    ("pub.json:jsonStringToDocument", "parses JSON text", _T.JSON),
    ("pub.flatFile:convertToValues", "parses a flat file", _T.FLAT_FILE),
    ("pub.flatFile:convertToString", "serializes a flat file", _T.FLAT_FILE),
    ("pub.document:documentToXMLValues", "converts a document to XML values", _T.DOCUMENT),
    ("pub.document:XMLValuesToDocument", "converts XML values to a document", _T.DOCUMENT),
    ("pub.string:concat", "joins strings", _T.STRING),
    ("pub.string:substring", "takes a substring", _T.STRING),
    ("pub.string:trim", "trims a string", _T.STRING),
    ("pub.string:toUpper", "upper-cases a string", _T.STRING),
    ("pub.string:toLower", "lower-cases a string", _T.STRING),
    ("pub.string:replace", "replaces text in a string", _T.STRING),
    ("pub.string:tokenize", "splits a string into tokens", _T.STRING),
    ("pub.string:padLeft", "pads a string", _T.STRING),
    ("pub.string:length", "measures a string", _T.STRING),
    ("pub.string:base64Encode", "base64-encodes a value", _T.STRING),
    ("pub.string:base64Decode", "base64-decodes a value", _T.STRING),
    ("pub.date:getCurrentDateString", "reads the current date", _T.DATE),
    ("pub.date:formatDate", "formats a date", _T.DATE),
    ("pub.date:dateTimeFormat", "reformats a date and time", _T.DATE),
    ("pub.date:dateBuild", "builds a date", _T.DATE),
    ("pub.math:addInts", "adds integers", _T.NUMERIC),
    ("pub.math:addFloats", "adds floating-point numbers", _T.NUMERIC),
    ("pub.list:sizeOfList", "measures a list", _T.LIST),
    ("pub.list:appendToDocumentList", "appends to a document list", _T.LIST),
    ("pub.list:appendToStringList", "appends to a string list", _T.LIST),
    ("pub.list:stringListToDocumentList", "converts a string list to documents", _T.LIST),
    ("pub.flow:getLastError", "captures the last error", _T.ERROR_HANDLING),
    ("pub.flow:throwExceptionForRetry", "raises a retryable exception", _T.ERROR_HANDLING),
    ("pub.flow:debugLog", "writes a log entry", _T.ERROR_HANDLING),
    ("pub.flow:clearPipeline", "clears the pipeline", _T.FLOW_CONTROL),
    ("pub.flow:savePipeline", "saves the pipeline", _T.FLOW_CONTROL),
    ("pub.flow:restorePipeline", "restores a saved pipeline", _T.FLOW_CONTROL),
    ("pub.flow:tracePipeline", "traces the pipeline", _T.FLOW_CONTROL),
    ("pub.flow:sleep", "pauses execution", _T.FLOW_CONTROL),
    ("pub.security.pki:sign", "signs data", _T.SECURITY),
    ("pub.security.pki:verify", "verifies a signature", _T.SECURITY),
    ("pub.security.util:createMessageDigest", "hashes data", _T.SECURITY),
    ("pub.schema:validate", "validates against a schema", _T.SCHEMA),
    ("pub.schema:validatePipeline", "validates the pipeline against a schema", _T.SCHEMA),
)

BUILTIN_SERVICES: dict[str, BuiltinEffect] = {
    name.casefold(): BuiltinEffect(label=label, family=family)
    for name, label, family in _CATALOG
}


def is_builtin_name(full_name: str) -> bool:
    """Report whether *full_name* addresses the platform rather than a package."""
    return full_name.casefold().startswith(BUILTIN_PREFIXES)


def builtin_effect(full_name: str) -> BuiltinEffect | None:
    """Return the catalogued effect for *full_name*, or None when it is not known."""
    return BUILTIN_SERVICES.get(full_name.casefold())
