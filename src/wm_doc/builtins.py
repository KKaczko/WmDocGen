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
    LOGGING = "LOGGING"
    STORAGE = "STORAGE"
    FLOW_CONTROL = "FLOW_CONTROL"
    SECURITY = "SECURITY"
    SCHEMA = "SCHEMA"


# How much each family matters to a reader deciding what a service does, most first.
# Summaries list effects in this order instead of call order, so a publish is not
# crowded out by list or string helpers that happen to run earlier.
FAMILY_RANK: dict[BuiltinFamily, int] = {
    family: rank
    for rank, family in enumerate(
        (
            BuiltinFamily.TRANSACTION,
            BuiltinFamily.MESSAGING,
            BuiltinFamily.REMOTE,
            BuiltinFamily.FILE,
            BuiltinFamily.STORAGE,
            BuiltinFamily.SECURITY,
            BuiltinFamily.SCHEMA,
            BuiltinFamily.FLAT_FILE,
            BuiltinFamily.XML,
            BuiltinFamily.JSON,
            BuiltinFamily.DOCUMENT,
            BuiltinFamily.IO,
            BuiltinFamily.DATE,
            BuiltinFamily.NUMERIC,
            BuiltinFamily.STRING,
            BuiltinFamily.LIST,
            BuiltinFamily.FLOW_CONTROL,
            BuiltinFamily.LOGGING,
            BuiltinFamily.ERROR_HANDLING,
        )
    )
}


@dataclass(frozen=True)
class DataEffectSpec:
    """How a platform call touches data outside the pipeline, and where to look for it.

    `object_inputs` and `where_inputs` name documented input fields; when a FLOW sets or
    maps one of them, the value (or its source path) identifies the object or location.
    A field the FLOW does not set simply yields "not determined" -- nothing is guessed.
    """

    object_label: str
    system: str
    object_inputs: tuple[str, ...] = ()
    where_inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuiltinEffect:
    """A plain-language effect for one documented platform service."""

    label: str
    family: BuiltinFamily
    data: DataEffectSpec | None = None


_T = BuiltinFamily
_D = DataEffectSpec

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
    ("pub.flow:debugLog", "writes a log entry", _T.LOGGING),
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
    # M12 additions: services common in production FLOWs.
    ("pub.jms:send", "sends a JMS message", _T.MESSAGING),
    ("pub.jms:sendAndWait", "sends a JMS message and waits for a reply", _T.MESSAGING),
    ("pub.jms:sendBatch", "sends a batch of JMS messages", _T.MESSAGING),
    ("pub.jms:reply", "replies to a JMS message", _T.MESSAGING),
    ("pub.client:smtp", "sends an email", _T.REMOTE),
    ("pub.client:ftp", "transfers a file over FTP", _T.REMOTE),
    ("pub.client.sftp:put", "uploads a file over SFTP", _T.REMOTE),
    ("pub.client.sftp:get", "downloads a file over SFTP", _T.REMOTE),
    ("pub.client:soapClient", "calls an external SOAP endpoint", _T.REMOTE),
    ("pub.file:copyFile", "copies a file", _T.FILE),
    ("pub.file:moveFile", "moves a file", _T.FILE),
    ("pub.file:deleteFile", "deletes a file", _T.FILE),
    ("pub.file:streamToFile", "writes a stream to a file", _T.FILE),
    ("pub.file:checkFileExistence", "checks whether a file exists", _T.FILE),
    ("pub.storage:put", "stores an entry in Integration Server storage", _T.STORAGE),
    ("pub.storage:get", "reads an entry from Integration Server storage", _T.STORAGE),
    ("pub.storage:remove", "removes an entry from Integration Server storage", _T.STORAGE),
    ("pub.cache:put", "puts an entry in a cache", _T.STORAGE),
    ("pub.cache:get", "reads an entry from a cache", _T.STORAGE),
    ("pub.cache:remove", "removes an entry from a cache", _T.STORAGE),
    ("pub.json:jsonStreamToDocument", "parses a JSON stream", _T.JSON),
    ("pub.flow:setResponseCode", "sets the HTTP response code", _T.FLOW_CONTROL),
    ("pub.flow:setResponse2", "sets the HTTP response body", _T.FLOW_CONTROL),
    ("pub.flow:setResponseHeader", "sets an HTTP response header", _T.FLOW_CONTROL),
    ("pub.flow:getTransportInfo", "reads transport details of the request", _T.FLOW_CONTROL),
    ("pub.flow:invokeService", "invokes a service named at runtime", _T.FLOW_CONTROL),
    ("pub.flow:getRetryCount", "reads the retry count", _T.ERROR_HANDLING),
    ("pub.string:messageFormat", "formats a message from a pattern", _T.STRING),
    ("pub.string:numericFormat", "formats a number", _T.STRING),
    ("pub.string:makeString", "joins a list into a string", _T.STRING),
    ("pub.string:objectToString", "converts an object to a string", _T.STRING),
    ("pub.string:bytesToString", "converts bytes to a string", _T.STRING),
    ("pub.string:stringToBytes", "converts a string to bytes", _T.STRING),
    ("pub.string:indexOf", "finds text in a string", _T.STRING),
    ("pub.string:lookupTable", "looks up a value in a table", _T.STRING),
    ("pub.date:compareDates", "compares dates", _T.DATE),
    ("pub.date:incrementDate", "shifts a date", _T.DATE),
    ("pub.date:calculateDateDifference", "measures the time between dates", _T.DATE),
    ("pub.math:multiplyInts", "multiplies integers", _T.NUMERIC),
    ("pub.math:subtractInts", "subtracts integers", _T.NUMERIC),
    ("pub.math:divideInts", "divides integers", _T.NUMERIC),
    ("pub.math:toNumber", "converts a string to a number", _T.NUMERIC),
    ("pub.list:addItemToVector", "adds an item to a list", _T.LIST),
    ("pub.list:vectorToArray", "converts a list to an array", _T.LIST),
    ("pub.document:documentListToDocument", "turns a document list into a document", _T.DOCUMENT),
    ("pub.document:documentToDocumentList", "turns a document into a list", _T.DOCUMENT),
    ("pub.document:deleteDocuments", "removes documents from a list", _T.DOCUMENT),
    ("pub.document:groupDocuments", "groups documents", _T.DOCUMENT),
    ("pub.document:sortDocuments", "sorts documents", _T.DOCUMENT),
    ("pub.document:searchDocuments", "searches a document list", _T.DOCUMENT),
)

# Where data leaves the service. Field names are documented inputs of each service.
_DATA_EFFECTS: dict[str, DataEffectSpec] = {
    "pub.publish:publish": _D("document", "Broker/UM", object_inputs=("documentTypeName",)),
    "pub.publish:publishAndWait": _D(
        "document", "Broker/UM", object_inputs=("documentTypeName",)
    ),
    "pub.publish:deliver": _D("document", "Broker/UM", object_inputs=("documentTypeName",)),
    "pub.publish:reply": _D("document", "Broker/UM", object_inputs=("documentTypeName",)),
    "pub.jms:send": _D(
        "message", "JMS", where_inputs=("destinationName", "connectionAliasName")
    ),
    "pub.jms:sendAndWait": _D(
        "message", "JMS", where_inputs=("destinationName", "connectionAliasName")
    ),
    "pub.jms:sendBatch": _D(
        "message", "JMS", where_inputs=("destinationName", "connectionAliasName")
    ),
    "pub.jms:reply": _D("message", "JMS", where_inputs=("connectionAliasName",)),
    "pub.client:http": _D("HTTP request", "HTTP", where_inputs=("url", "method")),
    "pub.client:soapHTTP": _D("SOAP request", "SOAP over HTTP", where_inputs=("address",)),
    "pub.client:soapClient": _D("SOAP request", "SOAP", where_inputs=("address",)),
    "pub.client:smtp": _D("email", "SMTP", where_inputs=("to",)),
    "pub.client:ftp": _D("file", "FTP", where_inputs=("serverhost", "dirpath", "remotefile")),
    "pub.client.ftp:put": _D("file", "FTP", where_inputs=("remotefile",)),
    "pub.client.ftp:get": _D("file", "FTP", where_inputs=("remotefile",)),
    "pub.client.sftp:put": _D("file", "SFTP", where_inputs=("remoteFile",)),
    "pub.client.sftp:get": _D("file", "SFTP", where_inputs=("remoteFile",)),
    "pub.remote:invoke": _D(
        "service",
        "remote Integration Server",
        object_inputs=("$service",),
        where_inputs=("$alias",),
    ),
    "pub.file:getFile": _D("file", "file system", where_inputs=("filename",)),
    "pub.file:stringToFile": _D("file", "file system", where_inputs=("fileName",)),
    "pub.file:bytesToFile": _D("file", "file system", where_inputs=("fileName",)),
    "pub.file:streamToFile": _D("file", "file system", where_inputs=("fileName",)),
    "pub.file:listFiles": _D("directory listing", "file system", where_inputs=("directory",)),
    "pub.file:copyFile": _D("file", "file system", where_inputs=("fileName",)),
    "pub.file:moveFile": _D("file", "file system", where_inputs=("fileName",)),
    "pub.file:deleteFile": _D("file", "file system", where_inputs=("fileName",)),
    "pub.storage:put": _D("stored entry", "IS storage", where_inputs=("storeName",)),
    "pub.storage:get": _D("stored entry", "IS storage", where_inputs=("storeName",)),
    "pub.storage:remove": _D("stored entry", "IS storage", where_inputs=("storeName",)),
    "pub.cache:put": _D("cache entry", "cache", where_inputs=("cacheName",)),
    "pub.cache:get": _D("cache entry", "cache", where_inputs=("cacheName",)),
    "pub.cache:remove": _D("cache entry", "cache", where_inputs=("cacheName",)),
}

BUILTIN_SERVICES: dict[str, BuiltinEffect] = {
    name.casefold(): BuiltinEffect(label=label, family=family, data=_DATA_EFFECTS.get(name))
    for name, label, family in _CATALOG
}


def is_builtin_name(full_name: str) -> bool:
    """Report whether *full_name* addresses the platform rather than a package."""
    return full_name.casefold().startswith(BUILTIN_PREFIXES)


def builtin_effect(full_name: str) -> BuiltinEffect | None:
    """Return the catalogued effect for *full_name*, or None when it is not known."""
    return BUILTIN_SERVICES.get(full_name.casefold())
