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


CONFIRMED_SAMPLES = {"customSQL", "dynamicSQL"}


def test_both_real_templates_are_present() -> None:
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
    "long-string": (HEADER + OPEN + KEY + bytes([0x04, 0x80]) + CLOSE, "unsupported_length"),
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
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_unsupported_or_invalid_structures_are_explicit(name: str) -> None:
    raw, code = CASES[name]
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(raw)
    assert error.value.code == code
    assert error.value.offset is None or 0 <= error.value.offset <= len(raw)


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
def test_long_lengths_round_trip_under_each_hypothesis(scheme: str, chars: int) -> None:
    document = _long_document(chars)
    raw = encode_idata(document, long_lengths=scheme)
    with pytest.raises(IDataBinaryError) as error:
        decode_idata(raw)  # the confirmed rules alone never read it
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
    with pytest.raises(IDataBinaryError):
        encode_idata(_doc(("k", "x" * 128)))
    with pytest.raises(IDataBinaryError):
        encode_idata(_doc(("k", BinaryArray(STRING, tuple("x" * 128)))))


def test_duplicate_keys_have_no_json_form() -> None:
    with pytest.raises(IDataBinaryError) as error:
        to_plain(_doc(("k", "a"), ("k", "b")))
    assert error.value.code == "duplicate_key"
