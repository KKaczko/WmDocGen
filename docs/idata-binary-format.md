# The binary IData format of `IRTNODE_PROPERTY` (adapter services)

Adapter nodes (`svc_type` `AdapterService`) keep their configuration in `node.ndf` as one
base64 value, `IRTNODE_PROPERTY` (next to `IRTNODE_VERSION`). On Integration Server the
sequence `pub.string:base64Decode` -> `pub.document:bytesToDocument` ->
`pub.json:documentToJSONString` turns it into a document. wm-doc reads the same bytes
offline in `src/wm_doc/idata_binary.py`, without a server, Java, a database or any webMethods
library, and `src/wm_doc/adapters.py` interprets the decoded document.

This page records what was **confirmed** on real IS 10.15 values, what is **assumed**, and
what is **not known**. The decoder accepts only the confirmed parts and reports everything
else as an explicit, unsupported structure: it never guesses.

## Evidence

| Sample | Files | Template | Value size |
| --- | --- | --- | --- |
| `samples/jdbcadapter/dynamicSQL/` | `node.ndf`, `expected.json` | `com.wm.adapter.wmjdbc.services.DynamicSQL` | 1,976 bytes |
| `samples/jdbcadapter/customSQL/` | `node.ndf`, `expected.json` | `com.wm.adapter.wmjdbc.services.CustomSQL` | 1,926 bytes |

`samples/jdbcadapter/node.idf` is the namespace folder's node (`kkaczk.jdbcadapter`). Each
`expected.json` is the document IS exported itself: the decoded document directly, with no
wrapper added by the exporting FLOW service. The samples are read-only and protected by
`tests/fixtures/checksums.sha256`.

Method: the base64 value was decoded, dumped with offsets, and every byte was accounted for
against the reference JSON. `tests/unit/test_idata_binary.py` checks on every run that both
samples decode to exactly the reference documents: same keys, same values, same value types,
same array order.

## Confirmed layout

All multi-byte numbers are big-endian. Every object starts with a one-byte tag.

| Tag | Object | Layout after the tag | Seen |
| --- | --- | --- | --- |
| `0x0b` | Integer | `0x04`, then 4 bytes | values 0, 1, 2 |
| `0x04` | String | length *n* (one byte), then *n* UTF-16BE code units | lengths 0..83 |
| `0x05` | Document (IData) | `0x01`, the implementation class (an object, always a string), key/value pairs, then `0x02 0x00` | `com.wm.data.ISMemDataImpl` |
| `0x0a` | Array | count *n* (one byte), the component class (an object, always a string), then *n* objects | `java.lang.String`, 0..2 items |
| `0x00` | Reference | index (one byte) of an earlier object | indexes up to 92 |

- **The value** is an Integer `1` (read as the format version) followed by exactly one
  document and nothing else.
- **Keys** are string objects (they can be references too, like any string).
- **References**: every object read gets the next index, in the order its tag is read,
  starting at 0 with the leading Integer. Containers get their index before their content,
  and a reference gets an index of its own (it stands for the referenced value). Example
  from the DynamicSQL sample: index 15 is the first `java.lang.String`, and every later
  array's component class is `00 0f`; the nested `templateProperties` document names its
  class with `00 02` (the top document's class string); `realInputFields` of the CustomSQL
  sample is two references to the `inputField` strings.
- **Empty values**: an empty string is `04 00`; an empty array is `0a 00 <class>`.
- **Types are kept**: `metadataVersion` and `adapterServiceNodeVersion` are Integers (numbers
  in the JSON); `maxRow` `"0"` and `queryTimeOut` `"-1"` are strings (strings in the JSON).
- **JSON normalization** (the only one): `documentToJSONString` drops the document class and
  the array component class. `idata_binary.to_plain` does the same for the comparison; the
  decoded model keeps both.

## Assumptions (consistent with the samples, not proven)

- The leading Integer is a format version; only `1` is accepted.
- Integers are signed (Java `int`); only small positive values were seen.
- Lengths count UTF-16 code units, so a character outside the Basic Multilingual Plane counts
  two. Only ASCII was seen in IS-written values; the round-trip test covers Polish letters and
  an emoji in the encoder's own output.

## Not known by the confirmed rules

| What | Why it matters | `decode_idata` (confirmed rules) |
| --- | --- | --- |
| Lengths, counts and indexes of 128 or more | Every value seen was below 128, so it is not known whether the byte is a 7-bit varint, a plain unsigned byte (up to 255) or whether long strings use another tag. An SQL template longer than 127 characters, an array of 128 or more items, or a reference to an object past index 127 needs it. | `unsupported_length` |
| Whether a nested document's end marker counts as an object | No sample references an object written after a nested document closes. | a reference to such an object: `ambiguous_reference` |
| References to documents or arrays | Not seen. | `unsupported_reference` |
| Null values, booleans, other number types, byte arrays, dates; tags `0x01`, `0x03`, `0x06`..`0x09`, `0x0c` and above | Not seen. | `unsupported_tag` |
| A document marker other than `0x01`, an end marker other than `0x02 0x00`, an Integer width other than `0x04` | Not seen. | `unsupported_marker` |
| Documents with repeated keys | IData allows them; none seen. | decoded in order; `to_plain` refuses them |

The first two rows are the only ones a hypothesis may lift (next section); every other row
always stands.

## Hypotheses (owner decision, M15 extension; not confirmed)

The owner accepted, on 2026-11-25, that values the confirmed rules cannot read are read by
hypothesis, and checks the results against IS exports. `decode_idata_hypotheses` first runs
the confirmed rules; only when they stop at `unsupported_length` or `ambiguous_reference` does
it try every combination of:

| Length, count and index readings (`LENGTH_SCHEMES`) | Meaning of a first byte of 128 or more |
| --- | --- |
| `leb128` | 7-bit groups, least significant first, high bit set while more follow (protobuf) |
| `vlq` | 7-bit groups, most significant first, high bit set while more follow |
| `byte` | the byte itself, 128..255 |
| `u15` | 15 bits in two bytes: the low 7 bits of the first byte, then the second byte |

| Numbering after a nested document's end (`END_NUMBERINGS`) | |
| --- | --- |
| `end-not-counted` | the end marker is not an object |
| `end-counted` | the end marker takes an index (a reference to it is invalid) |

Values below 128 are one byte in every reading, so the confirmed samples read the same way.
A reading that writes a value below 128 in more bytes (not minimal) is rejected. A value is
accepted only when at least one reading parses it to the very end and every reading that does
gives the same document (two readings can agree, for example `81 01` is 129 both as `leb128`
and as `vlq`); readings that disagree give `ambiguous` and the service stays `partial`. The
readings used are reported: `AdapterDetails.decode_hypotheses` (for example `length:vlq`), the
INFO finding `ADAPTER_LONG_ENCODING_UNCONFIRMED`, an "Unconfirmed reading" note on the service
page, the artifacts inventory and the Explorer. They are tested by synthetic round trips through
`encode_idata(..., long_lengths=..., references=...)` only.

### Checking a hypothesis

1. Export the service from IS 10.15 as for the existing samples and put `node.ndf` and the JSON
   in a new folder `samples/jdbcadapter/<name>/`.
2. Compare directly: `uv run python scripts/decode_adapter.py samples/jdbcadapter` prints, per
   folder, `equal to <json>` or the paths that differ (never values), and the readings used.
   `uv run python scripts/decode_adapter.py <node.ndf>` prints the document in the shape of
   `pub.json:documentToJSONString` (byte-identical for the two samples; secret-like values are
   shown as `<redacted>` unless `--show-secrets`).
3. Register the files: `uv run python scripts/add_sample_checksums.py` (adds new files to the
   checksum manifest, never changes existing entries), then `uv run pytest
   tests/unit/test_idata_binary.py`: the golden test reads every sample folder; a passing new
   sample confirms the reading it needed for that value.

Other limits: at most 1,000,000 decoded bytes, 16 levels of nesting and 200,000 objects.
Malformed base64 (`not_base64`), an empty value (`empty`), a value cut short (`truncated`,
tested at every possible cut of both samples), bytes after the document (`trailing_bytes`),
invalid UTF-16 (`invalid_text`) and a non-text key (`invalid_key`) are reported with the byte
offset. No message repeats content of the value. Class names are kept as text and never
loaded or instantiated.

## When a value cannot be decoded

`adapters.decode_adapter_service` uses `decode_idata_hypotheses` and, when that fails, falls back to the M12 reader for the identity fields
approved then (template, connection, adapter type, configured tables): it scans for string
tokens and takes the string right after each allow-listed key. The result is marked
`decoding: partial` with the decoder's reason in `decode_problem`, and the service gets the
INFO finding `ADAPTER_CONFIGURATION_PARTIALLY_DECODED` (source: its `node.ndf`). The SQL,
the parameters and the SQL reading are then not available for that service; nothing else
in the package is affected.

Connections (`ConnectionData`) and notifications (`AdapterRuntimeNotification`) are still read
by the M12 reader only: no real sample of their documents has been checked against IS.

## The M12 reader compared with the decoder

| | M12 reader (before) | `idata_binary` (now) |
| --- | --- | --- |
| Method | scans for `0x04 <len>` tokens, takes the token after a known key | reads every object in order and checks every marker |
| On the two samples | template, connection, adapter type correct; tables none (correct: these templates have none); nothing else read | the complete document, equal to the IS export |
| Strings of 128 or more characters | read with a one-byte length (wrong if the real encoding differs), then resynchronises on later strings | refused by the confirmed rules; read by hypothesis when the readings agree (marked unconfirmed), else the M12 reader is used |
| Repeated strings (references) | a key whose value is a reference is skipped | resolved |

## Recommended samples

To lift the limits above, export these from IS 10.15 the same way (node.ndf plus the JSON of
`bytesToDocument` -> `documentToJSONString`) and add them under `samples/jdbcadapter/<name>/`
(any folder name; the tests find every folder with a `node.ndf` and a `.json`):

1. CustomSQL services whose SQL is about 200 characters, about 300 characters, and longer than
   16,384 characters (string length encoding).
2. A service with 130 or more input or output fields, or a long column list (counts and
   reference indexes past 127).
3. A service whose top-level fields after `templateProperties` repeat an earlier value, for
   example an input record name equal to an output field name (end-marker numbering).
4. One sample of each other template: SelectSQL, InsertSQL, UpdateSQL, DeleteSQL,
   BatchInsertSQL, BatchUpdateSQL, StoredProcedure, StoredProcedureWithSignature.
5. A JDBC connection (`ConnectionData`) and a JDBC notification, with dummy credentials, to move
   them from the M12 reader to the decoder.
6. A configuration with a missing optional field (for example no output fields), and one
   with non-ASCII text (Polish letters in the SQL or in a field name).
