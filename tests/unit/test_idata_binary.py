"""The binary IData decoder against Integration Server's own decoding, and its limits.

Golden part: every sample under `samples/jdbcadapter/` holds a node.ndf and the document IS
10.15 produced from the same `IRTNODE_PROPERTY` with `pub.document:bytesToDocument` and
`pub.json:documentToJSONString`. The comparison is semantic (key order free, array order and
value types exact). The only normalization is the one JSON itself makes: the document and
array classes are not part of the JSON (`to_plain`).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from jdbc_samples import property_blob, property_bytes, reference_json, sample_dirs

from wm_doc.analysis_cache import input_fingerprint
from wm_doc.config import load_config
from wm_doc.idata_binary import (
    LENGTH_SCHEMES,
    MAX_DEPTH,
    BinaryArray,
    BinaryDocument,
    IDataBinaryError,
    Value,
    decode_base64,
    decode_idata,
    decode_idata_base64,
    decode_idata_hypotheses,
    encode_idata,
    to_plain,
)

STRING = "java.lang.String"
MEM = "com.wm.data.ISMemDataImpl"
SAMPLES = sample_dirs()
IDS = [folder.name for folder in SAMPLES]


# Samples read by the confirmed rules alone (no unconfirmed reading needed).
CONFIRMED_SAMPLES = {
    "customSQL",
    "dynamicSQL",
    "customSQLLong",
    "customSQL127",
    "customSQL128",
    "customSQL255",
    "customSQL256",
}


def test_every_real_sample_is_present() -> None:
    assert set(IDS) >= CONFIRMED_SAMPLES


@pytest.mark.parametrize("folder", SAMPLES, ids=IDS)
def test_decoding_equals_the_document_integration_server_exported(folder: Path) -> None:
    # Every sample folder with a node.ndf and an exported JSON is checked; a new one may need
    # the unconfirmed readings, and passing here is what confirms them for that sample.
    result = decode_idata_hypotheses(decode_base64(property_blob(folder)))
    decoded = to_plain(result.document)
    expected = reference_json(folder)

    assert decoded == expected
    # Same JSON, whatever the key order; lists keep their order and values their types.
    assert json.dumps(decoded, sort_keys=True) == json.dumps(expected, sort_keys=True)
    if folder.name in CONFIRMED_SAMPLES:
        assert result.hypotheses == ()
        assert decode_idata_base64(property_blob(folder)) == result.document


@pytest.mark.parametrize("folder", SAMPLES, ids=IDS)
def test_the_whole_value_is_read_and_classes_are_kept(folder: Path) -> None:
    document = decode_idata(property_bytes(folder))
    properties = document.get("templateProperties")

    assert document.class_name == MEM
    assert isinstance(properties, BinaryDocument) and properties.class_name == MEM
    arrays = [value for _, value in properties.entries if isinstance(value, BinaryArray)]
    assert arrays and all(array.component_type == STRING for array in arrays)
    # Integers stay numbers, numeric text stays text (as in the reference JSON).
    assert document.get("metadataVersion") == 0
    assert document.get("adapterServiceNodeVersion") == 2
    assert properties.get("maxRow") == "0"
    assert properties.get("resultRowField") == ""


def test_back_references_resolve_to_the_earlier_value() -> None:
    folder = next(folder for folder in SAMPLES if folder.name == "customSQL")
    properties = decode_idata(property_bytes(folder)).get("templateProperties")
    assert isinstance(properties, BinaryDocument)
    # `realInputFields` is written as two references to the `inputField` strings.
    assert properties.get("realInputFields") == properties.get("inputField")
    assert properties.get("inputColIndexes") == BinaryArray(STRING, ("-1", "-1"))
    assert properties.get("inputExpression") == BinaryArray(STRING, ())


# --- string lengths: one unsigned byte up to 255, tag 0x84 from 256 (IS exports) -------------


def _sample(name: str) -> Path:
    return next(folder for folder in SAMPLES if folder.name == name)


def _long_sample() -> Path:
    return _sample("customSQLLong")


@pytest.mark.parametrize(
    ("name", "prefix"),
    [
        ("customSQL127", bytes([0x04, 0x7F])),
        ("customSQL128", bytes([0x04, 0x80])),
        ("customSQL255", bytes([0x04, 0xFF])),
        ("customSQL256", bytes([0x84, 0x00, 0x00, 0x01, 0x00])),
    ],
)
def test_integration_server_switches_to_the_long_string_tag_at_256(
    name: str, prefix: bytes
) -> None:
    # Byte evidence, IS 10.15 exports of SQL templates of exactly 127, 128, 255 and 256
    # characters: up to 255 the length is one unsigned byte after `04`, from 256 on IS writes
    # `84` and the length in four bytes. The confirmed rules read all four with no hypothesis.
    folder = _sample(name)
    raw = property_bytes(folder)
    expected = reference_json(folder)
    assert isinstance(expected, dict)
    sql = expected["templateProperties"]["sql"]
    assert len(sql) == int(name.removeprefix("customSQL")) and sql.isascii()
    at = raw.find(sql.encode("utf-16-be"))
    assert at > 0 and raw[at - len(prefix) : at] == prefix
    properties = decode_idata(raw).get("templateProperties")
    assert isinstance(properties, BinaryDocument) and properties.get("sql") == sql
    assert decode_idata_hypotheses(raw).hypotheses == ()


def test_integration_server_writes_a_long_string_as_tag_0x84_and_a_four_byte_length() -> None:
    # Byte evidence, IS 10.15 customSQLLong: the `sql` key is followed by `84`, then the
    # number of UTF-16 code units in four big-endian bytes, then the text; the one-byte form
    # `04 <length>` is not used for it.
    folder = _long_sample()
    raw = property_bytes(folder)
    expected = reference_json(folder)
    assert isinstance(expected, dict)
    sql = expected["templateProperties"]["sql"]
    data = sql.encode("utf-16-be")
    at = raw.find(data)
    key = "sql".encode("utf-16-be")
    assert len(sql) > 0x7F and at > 0
    assert raw[at - 5 : at] == bytes([0x84]) + (len(data) // 2).to_bytes(4, "big")
    assert raw[at - 5 - len(key) - 2 : at - 5] == bytes([0x04, 3]) + key
    # The confirmed rules read it whole, Polish letters included, with no other reading.
    properties = decode_idata(raw).get("templateProperties")
    assert isinstance(properties, BinaryDocument)
    assert properties.get("sql") == sql
    assert any(ord(char) > 0x7F for char in sql)
    assert decode_idata_hypotheses(raw).hypotheses == ()


def test_a_long_string_takes_one_reference_index_like_any_string() -> None:
    # References written after the long SQL (realInputFields) resolve to the right strings,
    # so the long string is numbered as one object.
    raw = property_bytes(_long_sample())
    properties = decode_idata(raw).get("templateProperties")
    assert isinstance(properties, BinaryDocument)
    fields = properties.get("inputField")
    assert isinstance(fields, BinaryArray) and fields.items
    assert properties.get("realInputFields") == fields
    for name in fields.items:
        assert isinstance(name, str)
        # Written once as text: the second occurrence is a reference to it.
        assert raw.count(bytes([0x04, len(name)]) + name.encode("utf-16-be")) == 1


LENGTHS = [0, 1, 126, 127, 128, 129, 254, 255, 256, 257, 300, 16_384, 65_535, 65_536, 200_000]


@pytest.mark.parametrize("chars", LENGTHS)
def test_strings_on_both_sides_of_the_switch_round_trip(chars: int) -> None:
    # Synthetic (the encoder writes the layout the IS exports show): up to 255 code units the
    # one-byte form, from 256 on the long form.
    document = _doc(("sql", "S" * chars), ("after", "x"))
    raw = encode_idata(document)
    start = raw.find("sql".encode("utf-16-be")) + 6
    if chars <= 255:
        assert raw[start : start + 2] == bytes([0x04, chars])
    else:
        assert raw[start : start + 5] == bytes([0x84]) + chars.to_bytes(4, "big")
    assert decode_idata(raw) == document
    assert decode_idata_hypotheses(raw).hypotheses == ()


def test_long_strings_keep_unicode_and_special_characters() -> None:
    text = "SELECT '^' || \"q\" || '\\' || '${name}' -- Zażółć gęślą jaźń \U0001f600\n" * 40
    document = _doc(("sql", text), ("list", BinaryArray(STRING, (text, "ü"))))
    raw = encode_idata(document)
    assert decode_idata(raw) == document
    # The length counts UTF-16 code units: the emoji counts two.
    units = len(text.encode("utf-16-be")) // 2
    assert units == len(text) + 40
    assert bytes([0x84]) + units.to_bytes(4, "big") in raw


def test_a_long_form_used_for_a_short_string_is_read() -> None:
    # Synthetic: IS writes `84` only from 256 on, but the four-byte length is self-describing,
    # so a short value in the long form reads the same.
    raw = HEADER + OPEN + KEY + bytes([0x84, 0, 0, 0, 2]) + "ab".encode("utf-16-be") + CLOSE
    assert decode_idata(raw).get("k") == "ab"


def test_a_reference_to_a_long_string_resolves() -> None:
    long_text = "x" * 500
    document = _doc(("a", long_text), ("b", long_text))
    raw = encode_idata(document, references=True)
    assert raw.count(bytes([0x84])) == 1  # the second one is a reference
    assert decode_idata(raw) == document


def test_a_long_length_is_never_trusted_beyond_the_bytes_present() -> None:
    for length in (0x7FFF_FFFF, 0x0010_0000, 2):
        raw = HEADER + OPEN + KEY + bytes([0x84]) + length.to_bytes(4, "big") + b"\x00"
        with pytest.raises(IDataBinaryError) as error:
            decode_idata(raw)
        assert error.value.code == "truncated"
        assert error.value.offset is not None and error.value.offset <= len(raw)
    # Cut inside the four length bytes.
    for cut in range(1, 5):
        with pytest.raises(IDataBinaryError) as error:
            decode_idata(HEADER + OPEN + KEY + bytes([0x84, 0, 0, 0, 1])[:cut])
        assert error.value.code == "truncated"


def _doc(*entries: tuple[str, Value]) -> BinaryDocument:
    return BinaryDocument(MEM, tuple(entries))


def test_round_trip_of_nested_documents_arrays_unicode_and_empty_values() -> None:
    document = _doc(
        ("name", "Zażółć gęślą jaźń €"),
        ("emoji", "\U0001f600"),
        ("empty", ""),
        ("number", -7),
        ("big", 2_147_483_647),
        ("list", BinaryArray(STRING, ("a", "", "ü"))),
        ("none", BinaryArray(STRING, ())),
        ("inner", _doc(("deeper", _doc(("x", 1))))),
        ("docs", BinaryArray("com.wm.data.IData", (_doc(("k", "v")),))),
    )
    assert decode_idata(encode_idata(document)) == document


def test_unicode_is_utf16_big_endian_code_units() -> None:
    raw = encode_idata(_doc(("k", "\U0001f600")))
    # The emoji is two UTF-16 code units: length 2, then a surrogate pair.
    assert bytes([0x04, 0x02, 0xD8, 0x3D, 0xDE, 0x00]) in raw


def test_malformed_base64_is_reported() -> None:
    with pytest.raises(IDataBinaryError) as error:
        decode_base64("not base64 at all!")
    assert error.value.code == "not_base64"
    with pytest.raises(IDataBinaryError) as error:
        decode_base64("   ")
    assert error.value.code == "empty"


@pytest.mark.parametrize("folder", SAMPLES, ids=IDS)
def test_every_truncation_of_a_real_value_is_reported(folder: Path) -> None:
    raw = property_bytes(folder)
    step = max(1, len(raw) // 2000)  # every cut of the small samples, a spread of a big one
    for end in range(1, len(raw), step):
        with pytest.raises(IDataBinaryError) as error:
            decode_idata(raw[:end])
        assert error.value.code in {"truncated", "unsupported_length"}, end
        with pytest.raises(IDataBinaryError):
            decode_idata_hypotheses(raw[:end])


def test_trailing_bytes_are_reported() -> None:
    raw = encode_idata(_doc(("k", "v")))
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(raw + b"\x00")
    assert error.value.code == "trailing_bytes"


HEADER = bytes([0x0B, 0x04, 0, 0, 0, 1])
CLOSE = bytes([0x02, 0x00])


def _string(text: str) -> bytes:
    return bytes([0x04, len(text)]) + text.encode("utf-16-be")


OPEN = bytes([0x05, 0x01]) + _string("M")  # a document of class "M"
KEY = _string("k")

CASES = {
    "version-2": (bytes([0x0B, 0x04, 0, 0, 0, 2]) + OPEN + CLOSE, "unsupported_header"),
    "no-version": (OPEN + CLOSE, "unsupported_header"),
    "no-document": (HEADER + _string("x"), "unsupported_structure"),
    "unknown-tag": (HEADER + OPEN + KEY + bytes([0x07]) + CLOSE, "unsupported_tag"),
    # `04 80` is a string of 128 code units (one unsigned byte); the bytes are not there.
    "one-byte-length-past-the-end": (
        HEADER + OPEN + KEY + bytes([0x04, 0x80]) + CLOSE,
        "truncated",
    ),
    "long-array": (HEADER + OPEN + KEY + bytes([0x0A, 0x90]) + CLOSE, "unsupported_length"),
    "forward-reference": (HEADER + OPEN + KEY + bytes([0x00, 0x09]) + CLOSE, "invalid_reference"),
    "reference-to-a-document": (
        HEADER + OPEN + KEY + bytes([0x00, 0x01]) + CLOSE,
        "unsupported_reference",
    ),
    "integer-width": (
        HEADER + OPEN + KEY + bytes([0x0B, 0x08, 0, 0, 0, 1]) + CLOSE,
        "unsupported_marker",
    ),
    "document-marker": (HEADER + bytes([0x05, 0x02]) + _string("M") + CLOSE, "unsupported_marker"),
    "document-end-marker": (
        HEADER + OPEN + KEY + _string("v") + bytes([0x02, 0x01]),
        "unsupported_marker",
    ),
    "non-text-key": (HEADER + OPEN + bytes([0x0B, 0x04, 0, 0, 0, 1]) + CLOSE, "invalid_key"),
    "end-in-value-position": (HEADER + OPEN + KEY + CLOSE + CLOSE, "unsupported_structure"),
    "lone-surrogate": (
        HEADER + OPEN + KEY + bytes([0x04, 0x01, 0xD8, 0x00]) + CLOSE,
        "invalid_text",
    ),
    "long-string-lone-surrogate": (
        HEADER + OPEN + KEY + bytes([0x84, 0, 0, 0, 1, 0xD8, 0x00]) + CLOSE,
        "invalid_text",
    ),
    "long-string-negative-length": (
        HEADER + OPEN + KEY + bytes([0x84, 0xFF, 0xFF, 0xFF, 0xFF]) + CLOSE,
        "invalid_length",
    ),
    "long-string-past-the-end": (
        HEADER + OPEN + KEY + bytes([0x84, 0, 0, 1, 0]) + CLOSE,
        "truncated",
    ),
    # Only the string has a confirmed long form; the same high bit on other tags is not read.
    "high-bit-reference-tag": (
        HEADER + OPEN + KEY + bytes([0x80, 0, 0, 0, 1]) + CLOSE,
        "unsupported_tag",
    ),
    "high-bit-array-tag": (
        HEADER + OPEN + KEY + bytes([0x8A, 0, 0, 0, 0]) + CLOSE,
        "unsupported_tag",
    ),
    "high-bit-document-tag": (HEADER + OPEN + KEY + bytes([0x85, 0x01]) + CLOSE, "unsupported_tag"),
    "high-bit-integer-tag": (
        HEADER + OPEN + KEY + bytes([0x8B, 0x04, 0, 0, 0, 1]) + CLOSE,
        "unsupported_tag",
    ),
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_unsupported_or_invalid_structures_are_explicit(name: str) -> None:
    raw, code = CASES[name]
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(raw)
    assert error.value.code == code
    assert error.value.offset is None or 0 <= error.value.offset <= len(raw)
    if code != "unsupported_length":
        # No unconfirmed reading lifts an unknown tag, a bad length or broken text.
        with pytest.raises(IDataBinaryError) as lifted:
            decode_idata_hypotheses(raw)
        assert lifted.value.code == code


def test_a_reference_after_a_nested_document_end_is_not_guessed() -> None:
    inner = bytes([0x05, 0x01, 0x00, 0x02]) + _string("a") + _string("b") + CLOSE
    # Objects: 0 version, 1 document, 2 "M", 3 "inner", 4 document, 5 reference to 2, 6 "a",
    # 7 "b"; whether the end marker after them is an object was never observed.
    start = HEADER + OPEN + _string("inner") + inner
    # A reference to an object written before the nested end is fine ...
    assert decode_idata(start + _string("again") + bytes([0x00, 0x06]) + CLOSE).get("again") == "a"
    # ... one to an object written after it may be numbered either way: refused.
    after = start + _string("after") + bytes([0x00, 0x08]) + CLOSE
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(after)
    assert error.value.code == "ambiguous_reference"
    # Counting the end marker would point at the marker itself, so one reading is left.
    result = decode_idata_hypotheses(after)
    assert result.document.get("after") == "after"
    assert result.hypotheses == ("numbering:end-not-counted",)


def test_readings_that_disagree_are_refused() -> None:
    inner = bytes([0x05, 0x01, 0x00, 0x02]) + _string("a") + _string("b") + CLOSE
    # Index 9 is "x" if the end marker is not an object and "after" if it is.
    raw = (
        HEADER
        + OPEN
        + _string("inner")
        + inner
        + _string("after")
        + _string("x")
        + _string("again")
        + bytes([0x00, 0x09])
        + CLOSE
    )
    with pytest.raises(IDataBinaryError) as error:
        decode_idata_hypotheses(raw)
    assert error.value.code == "ambiguous"


def _long_document(chars: int) -> BinaryDocument:
    return _doc(
        ("sql", "S" * chars),
        ("text", "Zażółć " * 30),
        ("fields", BinaryArray(STRING, tuple(f"f{index}" for index in range(130)))),
    )


@pytest.mark.parametrize("scheme", LENGTH_SCHEMES)
@pytest.mark.parametrize("chars", [128, 200, 255])
def test_long_counts_round_trip_under_each_hypothesis(scheme: str, chars: int) -> None:
    # The strings of 128..255 code units need no hypothesis (confirmed); the array count of
    # 130 does.
    document = _long_document(chars)
    raw = encode_idata(document, long_lengths=scheme)
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(raw)  # the confirmed rules alone never read the count
    assert error.value.code == "unsupported_length"
    result = decode_idata_hypotheses(raw)
    assert result.document == document
    assert f"length:{scheme}" in result.hypotheses


@pytest.mark.parametrize("scheme", ["leb128", "vlq", "u15"])
def test_very_long_texts_and_references_past_index_127(scheme: str) -> None:
    names = tuple(f"field{index}" for index in range(140))
    document = _doc(
        ("sql", "SELECT " + "x, " * 7000 + "y FROM t"),
        ("inputField", BinaryArray(STRING, names)),
        ("realInputFields", BinaryArray(STRING, names)),  # written as references
    )
    raw = encode_idata(document, long_lengths=scheme, references=True)
    assert len(raw) < len(encode_idata(document, long_lengths=scheme))
    result = decode_idata_hypotheses(raw)
    assert result.document == document
    assert result.hypotheses == (f"length:{scheme}",)


def test_excessive_nesting_is_refused() -> None:
    document = _doc(("leaf", 1))
    for _ in range(MAX_DEPTH + 1):
        document = _doc(("child", document))
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(encode_idata(document))
    assert error.value.code == "too_deep"


def test_oversized_values_are_refused_before_decoding() -> None:
    with pytest.raises(IDataBinaryError) as error:
        decode_base64(base64.b64encode(b"\x00" * 1_000_001).decode("ascii"))
    assert error.value.code == "too_large"


def test_the_encoder_only_writes_confirmed_lengths() -> None:
    # Strings of any length have a confirmed form; a long array or a high index has none.
    assert bytes([0x04, 0xFF]) in encode_idata(_doc(("k", "x" * 255)))
    assert bytes([0x84, 0, 0, 1, 0]) in encode_idata(_doc(("k", "x" * 256)))
    with pytest.raises(IDataBinaryError):
        encode_idata(_doc(("k", BinaryArray(STRING, tuple("x" * 128)))))
    many = _doc(*((f"k{index}", f"v{index}") for index in range(70)), ("again", "v69"))
    with pytest.raises(IDataBinaryError):
        encode_idata(many, references=True)  # "v69" is object 142: an index past 127


def test_a_new_decoder_version_invalidates_cached_analyses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # An analysis cached before the decoder read 0x84 kept such a service `partial`.
    config = load_config(None)
    before = input_fingerprint(tmp_path, config, None, False)
    monkeypatch.setattr("wm_doc.analysis_cache.IDATA_DECODER_VERSION", "idata-binary.v99")
    assert input_fingerprint(tmp_path, config, None, False) != before


def test_duplicate_keys_have_no_json_form() -> None:
    with pytest.raises(IDataBinaryError) as error:
        to_plain(_doc(("k", "a"), ("k", "b")))
    assert error.value.code == "duplicate_key"
