"""Decoder for the binary IData encoding of `IRTNODE_PROPERTY` values.

Adapter nodes keep their configuration in node.ndf as a base64 value. Integration Server
turns it back into a document with `pub.document:bytesToDocument`; this module reads the same
bytes offline, without Java, a server or any webMethods library. It knows nothing about
adapters: `wm_doc.adapters` interprets the decoded document.

Confirmed on real IS 10.15 JDBC adapter services (see `docs/idata-binary-format.md` for the
evidence):

- the value starts with an Integer `1` and then holds one document, nothing after it;
- every object starts with a one-byte tag: `0x04` string, `0x05` document, `0x0a` array,
  `0x0b` Integer, `0x00` reference to an earlier object;
- a string is a length and that many UTF-16BE code units;
- a document is `0x05 0x01`, its implementation class (a string), then key/value pairs
  (keys are strings) and `0x02 0x00`;
- an array is a count, its component class (a string) and that many objects;
- an Integer is `0x04` and four big-endian bytes;
- a reference is the index of an earlier object; every object read counts, in the order its
  tag is read (containers before their content, references included), starting at 0 with
  the leading Integer.

`decode_idata` reads only that. Lengths, counts and indexes were only seen below 128, as one
byte, and no sample references an object written after a nested document closes.
`decode_idata_hypotheses` (owner decision, M15 extension) also tries the readings the samples
do not rule out for those two cases (`LENGTH_SCHEMES`, `END_NUMBERINGS`) and accepts a value
only when it parses to the end and every reading that does gives the same document; the
hypotheses it needed are returned so each such value can be checked against IS. A tag not
listed above, any other marker byte and a reference to a document or an array are always
reported as unsupported. Nothing found in the bytes is ever executed, instantiated or looked
up: class names are kept as text.
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Iterator
from dataclasses import dataclass, field

TAG_REFERENCE = 0x00
TAG_END = 0x02
TAG_STRING = 0x04
TAG_DOCUMENT = 0x05
TAG_ARRAY = 0x0A
TAG_INTEGER = 0x0B

DOCUMENT_START = 0x01
DOCUMENT_END = 0x00
INTEGER_WIDTH = 0x04
FORMAT_VERSION = 1
# The largest length, count or index seen in real values; above it the encoding is unknown.
MAX_CONFIRMED_SHORT = 0x7F
MAX_SHORT = 0x7FFF_FFFF

MAX_ENCODED_CHARS = 1_400_000
MAX_BYTES = 1_000_000
MAX_DEPTH = 16
MAX_OBJECTS = 200_000

# Hypotheses for a length, count or index of 128 or more (none is confirmed by a sample):
LENGTH_SCHEMES = (
    "leb128",  # 7-bit groups, least significant first, high bit = more follow (protobuf)
    "vlq",  # 7-bit groups, most significant first, high bit = more follow
    "byte",  # one unsigned byte, 0..255
    "u15",  # high bit set: 15 bits in two bytes, most significant first
)
# Hypotheses for numbering objects after a nested document's end marker:
END_NUMBERINGS = (
    "end-not-counted",  # the end marker is not an object
    "end-counted",  # the end marker takes an index of its own
)
# Errors a hypothesis can lift; every other error stands.
_LIFTABLE = {"unsupported_length", "ambiguous_reference"}


class IDataBinaryError(ValueError):
    """The value cannot be decoded; `code` names the reason, `offset` the byte."""

    def __init__(self, code: str, message: str, offset: int | None = None) -> None:
        where = f" at byte {offset}" if offset is not None else ""
        super().__init__(f"{message}{where}")
        self.code = code
        self.offset = offset


@dataclass(frozen=True, slots=True)
class BinaryDocument:
    """A decoded IData document: its implementation class and its entries in order."""

    class_name: str
    entries: tuple[tuple[str, Value], ...]

    def get(self, key: str) -> Value | None:
        """The value of the first entry named `key`, or None when there is none."""
        for name, value in self.entries:
            if name == key:
                return value
        return None

    def keys(self) -> tuple[str, ...]:
        return tuple(name for name, _ in self.entries)


@dataclass(frozen=True, slots=True)
class BinaryArray:
    """A decoded array: its declared component class and its items in order."""

    component_type: str
    items: tuple[Value, ...]


Value = str | int | BinaryDocument | BinaryArray


@dataclass(frozen=True)
class Decoded:
    """A decoded value and the unconfirmed readings it needed (empty: confirmed rules only).

    `hypotheses` names each reading that parsed the whole value, all to the same document,
    for example `("length:leb128", "length:vlq")` when both read a long length the same way.
    """

    document: BinaryDocument
    hypotheses: tuple[str, ...] = field(default=())


_CONTAINER = object()  # a document or array in the reference table: never referenced
_END = object()  # an end marker under "end-counted": never referenced


def decode_base64(text: str) -> bytes:
    """The bytes of a base64 value (whitespace ignored), within the size limit."""
    if len(text) > MAX_ENCODED_CHARS:
        raise IDataBinaryError("too_large", "the value is larger than the decoder accepts")
    try:
        raw = base64.b64decode("".join(text.split()), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IDataBinaryError("not_base64", "the value is not valid base64") from exc
    if not raw:
        raise IDataBinaryError("empty", "the value is empty")
    if len(raw) > MAX_BYTES:
        raise IDataBinaryError("too_large", "the value is larger than the decoder accepts")
    return raw


def decode_idata_base64(text: str) -> BinaryDocument:
    return decode_idata(decode_base64(text))


def decode_idata(raw: bytes) -> BinaryDocument:
    """The document a binary IData value holds, by the confirmed rules only."""
    return _decode(raw, None, None)[0]


def decode_idata_hypotheses(raw: bytes) -> Decoded:
    """The document, using unconfirmed readings only where the confirmed rules stop.

    The confirmed rules are tried first. Only when they stop at a long length, count or
    index, or at a reference past a nested document's end, is every combination of
    `LENGTH_SCHEMES` and `END_NUMBERINGS` tried; the value is accepted when at least one
    reads it to the end and all that do give the same document. Otherwise the confirmed
    rules' error stands, or `ambiguous` when readings disagree.
    """
    try:
        return Decoded(decode_idata(raw))
    except IDataBinaryError as error:
        if error.code not in _LIFTABLE:
            raise
        confirmed_error = error
    readings: list[tuple[BinaryDocument, tuple[str, ...]]] = []
    for scheme in (None, *LENGTH_SCHEMES):
        for numbering in (None, *END_NUMBERINGS):
            if scheme is None and numbering is None:
                continue
            try:
                document, used = _decode(raw, scheme, numbering)
            except IDataBinaryError:
                continue
            if used:  # a reading that needed nothing new is the confirmed one, which failed
                readings.append((document, used))
    documents = {document for document, _ in readings}
    if not documents:
        raise confirmed_error
    if len(documents) > 1:
        raise IDataBinaryError(
            "ambiguous",
            f"{len(documents)} unconfirmed readings give different documents",
            confirmed_error.offset,
        )
    hypotheses = sorted({label for _, used in readings for label in used})
    return Decoded(readings[0][0], tuple(hypotheses))


def to_plain(value: Value) -> object:
    """The value as `pub.json:documentToJSONString` shows it: JSON-like Python values.

    The JSON drops the document class and the array component class; Integers stay numbers.
    A document with two entries of the same name has no single JSON form and is refused.
    """
    if isinstance(value, BinaryDocument):
        plain: dict[str, object] = {}
        for key, item in value.entries:
            if key in plain:
                raise IDataBinaryError("duplicate_key", "a document repeats a key")
            plain[key] = to_plain(item)
        return plain
    if isinstance(value, BinaryArray):
        return [to_plain(item) for item in value.items]
    return value


def walk(value: Value) -> Iterator[tuple[str, Value]]:
    """Every (key, value) entry of the documents in `value`, depth first, in order."""
    if isinstance(value, BinaryDocument):
        for key, item in value.entries:
            yield key, item
            yield from walk(item)
    elif isinstance(value, BinaryArray):
        for item in value.items:
            yield from walk(item)


def _decode(
    raw: bytes, scheme: str | None, numbering: str | None
) -> tuple[BinaryDocument, tuple[str, ...]]:
    if len(raw) > MAX_BYTES:
        raise IDataBinaryError("too_large", "the value is larger than the decoder accepts")
    if not raw:
        raise IDataBinaryError("empty", "the value is empty")
    reader = _Reader(raw, scheme, numbering)
    if reader.peek() != TAG_INTEGER:
        raise IDataBinaryError(
            "unsupported_header", "the value does not start with the format version", 0
        )
    version = reader.value(0)
    if version != FORMAT_VERSION:
        raise IDataBinaryError(
            "unsupported_header", f"format version {version!r} is not supported", 0
        )
    if reader.peek() != TAG_DOCUMENT:
        raise IDataBinaryError(
            "unsupported_structure",
            "the format version is not followed by a document",
            reader.position,
        )
    document = reader.value(0)
    assert isinstance(document, BinaryDocument)
    if reader.position != len(raw):
        raise IDataBinaryError(
            "trailing_bytes", "bytes follow the end of the document", reader.position
        )
    return document, tuple(sorted(reader.used))


class _Reader:
    def __init__(self, raw: bytes, scheme: str | None, numbering: str | None) -> None:
        self.raw = raw
        self.position = 0
        self.scheme = scheme
        self.numbering = numbering
        self.used: set[str] = set()
        self.slots: list[object] = []
        # Objects from here on are numbered differently if a nested document's end marker
        # counts as an object; without a numbering hypothesis they are not referenced.
        self.uncertain_from: int | None = None

    def peek(self) -> int:
        if self.position >= len(self.raw):
            raise IDataBinaryError("truncated", "the value ends early", self.position)
        return self.raw[self.position]

    def byte(self) -> int:
        value = self.peek()
        self.position += 1
        return value

    def take(self, count: int) -> bytes:
        end = self.position + count
        if end > len(self.raw):
            raise IDataBinaryError("truncated", "the value ends early", self.position)
        chunk = self.raw[self.position : end]
        self.position = end
        return chunk

    def short(self, what: str) -> int:
        offset = self.position
        first = self.byte()
        if first <= MAX_CONFIRMED_SHORT:
            return first
        if self.scheme is None:
            raise IDataBinaryError(
                "unsupported_length",
                f"a {what} of 128 or more uses an encoding not confirmed by samples",
                offset,
            )
        value = self._long_short(first, offset)
        if value <= MAX_CONFIRMED_SHORT:
            # A small value written long: no encoder writes that; this reading is wrong.
            raise IDataBinaryError("unsupported_length", f"a {what} is not minimal", offset)
        if value > MAX_SHORT:
            raise IDataBinaryError("unsupported_length", f"a {what} is too large", offset)
        self.used.add(f"length:{self.scheme}")
        return value

    def _long_short(self, first: int, offset: int) -> int:
        if self.scheme == "byte":
            return first
        if self.scheme == "u15":
            return ((first & 0x7F) << 8) | self.byte()
        groups = [first & 0x7F]
        current = first
        while current & 0x80:
            if len(groups) >= 5:
                raise IDataBinaryError("unsupported_length", "a length is too long", offset)
            current = self.byte()
            groups.append(current & 0x7F)
        if self.scheme == "leb128":
            return sum(group << (7 * index) for index, group in enumerate(groups))
        value = 0
        for group in groups:  # vlq
            value = (value << 7) | group
        return value

    def slot(self, value: object) -> None:
        if len(self.slots) >= MAX_OBJECTS:
            raise IDataBinaryError("too_many_objects", "the value holds too many objects")
        self.slots.append(value)

    def value(self, depth: int) -> Value:
        offset = self.position
        tag = self.byte()
        if tag == TAG_STRING:
            return self._string(offset)
        if tag == TAG_REFERENCE:
            return self._reference(offset)
        if tag == TAG_INTEGER:
            return self._integer(offset)
        if tag == TAG_DOCUMENT:
            return self._document(offset, depth)
        if tag == TAG_ARRAY:
            return self._array(offset, depth)
        if tag == TAG_END:
            raise IDataBinaryError(
                "unsupported_structure", "a document end marker where a value belongs", offset
            )
        raise IDataBinaryError("unsupported_tag", f"type tag 0x{tag:02x} is not supported", offset)

    def _string(self, offset: int) -> str:
        length = self.short("string length")
        data = self.take(2 * length)
        try:
            text = data.decode("utf-16-be")
        except UnicodeDecodeError as exc:
            raise IDataBinaryError("invalid_text", "a string is not valid UTF-16", offset) from exc
        self.slot(text)
        return text

    def _reference(self, offset: int) -> Value:
        index = self.short("reference index")
        if index >= len(self.slots):
            raise IDataBinaryError(
                "invalid_reference", "a reference points past the objects read so far", offset
            )
        if self.uncertain_from is not None and index >= self.uncertain_from:
            if self.numbering is None:
                raise IDataBinaryError(
                    "ambiguous_reference",
                    "a reference past the end of a nested document is not confirmed by samples",
                    offset,
                )
            self.used.add(f"numbering:{self.numbering}")
        target = self.slots[index]
        if target is _CONTAINER or target is _END:
            raise IDataBinaryError(
                "unsupported_reference",
                "a reference to a document, an array or an end marker is not supported",
                offset,
            )
        assert isinstance(target, (str, int))
        self.slot(target)
        return target

    def _integer(self, offset: int) -> int:
        width = self.byte()
        if width != INTEGER_WIDTH:
            raise IDataBinaryError(
                "unsupported_marker",
                f"Integer width marker 0x{width:02x} is not supported",
                offset + 1,
            )
        value = int.from_bytes(self.take(4), "big", signed=True)
        self.slot(value)
        return value

    def _class_name(self, depth: int, what: str) -> str:
        offset = self.position
        name = self.value(depth + 1)
        if not isinstance(name, str):
            raise IDataBinaryError(
                "unsupported_structure", f"the {what} class is not text", offset
            )
        return name

    def _document(self, offset: int, depth: int) -> BinaryDocument:
        if depth >= MAX_DEPTH:
            raise IDataBinaryError("too_deep", "documents are nested too deeply", offset)
        marker = self.byte()
        if marker != DOCUMENT_START:
            raise IDataBinaryError(
                "unsupported_marker",
                f"document marker 0x{marker:02x} is not supported",
                offset + 1,
            )
        self.slot(_CONTAINER)
        class_name = self._class_name(depth, "document")
        entries: list[tuple[str, Value]] = []
        while self.peek() != TAG_END:
            key_offset = self.position
            key = self.value(depth + 1)
            if not isinstance(key, str):
                raise IDataBinaryError("invalid_key", "a document key is not text", key_offset)
            entries.append((key, self.value(depth + 1)))
        end_offset = self.position
        self.byte()
        closing = self.byte()
        if closing != DOCUMENT_END:
            raise IDataBinaryError(
                "unsupported_marker",
                f"document end marker 0x{closing:02x} is not supported",
                end_offset + 1,
            )
        if self.numbering == "end-counted":
            self.slot(_END)
        if self.uncertain_from is None:
            self.uncertain_from = len(self.slots) - (1 if self.numbering == "end-counted" else 0)
        return BinaryDocument(class_name, tuple(entries))

    def _array(self, offset: int, depth: int) -> BinaryArray:
        if depth >= MAX_DEPTH:
            raise IDataBinaryError("too_deep", "arrays are nested too deeply", offset)
        count = self.short("array length")
        self.slot(_CONTAINER)
        component = self._class_name(depth, "array component")
        items = tuple(self.value(depth + 1) for _ in range(count))
        return BinaryArray(component, items)


# --- encoder (synthetic packages and tests) ------------------------------------------------


def encode_idata(
    document: BinaryDocument,
    *,
    long_lengths: str | None = None,
    references: bool = False,
    numbering: str = "end-not-counted",
) -> bytes:
    """The binary form of `document` (synthetic packages and tests only).

    By default only the confirmed layout is written: every string in full and every length
    and count below 128 (anything else raises IDataBinaryError). `long_lengths` writes
    lengths, counts and indexes of 128 or more by one of the `LENGTH_SCHEMES` hypotheses, and
    `references` writes a repeated string as a reference to its first occurrence, numbering
    objects by the `numbering` hypothesis after a nested document's end.
    """
    writer = _Writer(long_lengths, references, numbering)
    writer.value(FORMAT_VERSION)
    writer.value(document)
    return bytes(writer.out)


class _Writer:
    def __init__(self, scheme: str | None, references: bool, numbering: str) -> None:
        self.out = bytearray()
        self.scheme = scheme
        self.references = references
        self.numbering = numbering
        self.count = 0  # objects written so far (their indexes)
        self.seen: dict[str, int] = {}

    def short(self, value: int) -> None:
        if 0 <= value <= MAX_CONFIRMED_SHORT:
            self.out.append(value)
            return
        if self.scheme is None or value > MAX_SHORT:
            raise IDataBinaryError("unsupported_length", "only lengths below 128 can be written")
        if self.scheme == "byte":
            if value > 0xFF:
                raise IDataBinaryError("unsupported_length", "a byte holds at most 255")
            self.out.append(value)
        elif self.scheme == "u15":
            if value > 0x7FFF:
                raise IDataBinaryError("unsupported_length", "15 bits hold at most 32767")
            self.out += bytes([0x80 | (value >> 8), value & 0xFF])
        else:
            groups: list[int] = []
            while True:
                groups.append(value & 0x7F)
                value >>= 7
                if not value:
                    break
            if self.scheme == "vlq":
                groups.reverse()
            self.out += bytes(
                group | (0x80 if index < len(groups) - 1 else 0)
                for index, group in enumerate(groups)
            )

    def value(self, value: Value) -> None:
        if isinstance(value, bool):
            raise IDataBinaryError("unsupported_tag", "booleans have no confirmed encoding")
        if isinstance(value, str):
            if self.references and value in self.seen:
                self.out.append(TAG_REFERENCE)
                self.short(self.seen[value])
            else:
                data = value.encode("utf-16-be")
                self.out.append(TAG_STRING)
                self.short(len(data) // 2)
                self.out += data
                self.seen.setdefault(value, self.count)
            self.count += 1
        elif isinstance(value, int):
            self.out += bytes([TAG_INTEGER, INTEGER_WIDTH]) + value.to_bytes(4, "big", signed=True)
            self.count += 1
        elif isinstance(value, BinaryDocument):
            self.out += bytes([TAG_DOCUMENT, DOCUMENT_START])
            self.count += 1
            self.value(value.class_name)
            for key, item in value.entries:
                self.value(key)
                self.value(item)
            self.out += bytes([TAG_END, DOCUMENT_END])
            if self.numbering == "end-counted":
                self.count += 1
        else:
            self.out.append(TAG_ARRAY)
            self.short(len(value.items))
            self.count += 1
            self.value(value.component_type)
            for item in value.items:
                self.value(item)
