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
| `samples/jdbcadapter/jdbcadapter2/customSQLLong/` | `node.ndf`, `expected.json` | `com.wm.adapter.wmjdbc.services.CustomSQL`, SQL of 13,739 characters | 29,459 bytes |
| `samples/jdbcadapter/jdbcadapter3/customSQL127/`, `customSQL128/`, `customSQL255/`, `customSQL256/` | `node.ndf`, `expected.json` each | `com.wm.adapter.wmjdbc.services.CustomSQL`, ASCII SQL of exactly 127, 128, 255 and 256 characters | 1,950, 1,952, 2,206 and 2,211 bytes |

`samples/jdbcadapter/node.idf` is the namespace folder's node (`kkaczk.jdbcadapter`);
`jdbcadapter2/node.idf` and `jdbcadapter3/node.idf` are those of
`kkaczk.jdbcadapter.jdbcadapter2` and `kkaczk.jdbcadapter.jdbcadapter3`. Each
`expected.json` is the document IS exported itself: the decoded document directly, with no
wrapper added by the exporting FLOW service. The samples are read-only and protected by
`tests/fixtures/checksums.sha256`.

Method: the base64 value was decoded, dumped with offsets, and every byte was accounted for
against the reference JSON. `tests/unit/test_idata_binary.py` checks on every run that every
sample decodes to exactly the reference document: same keys, same values, same value types,
same array order.

## Confirmed layout

All multi-byte numbers are big-endian. Every object starts with a one-byte tag.

| Tag | Object | Layout after the tag | Seen |
| --- | --- | --- | --- |
| `0x0b` | Integer | `0x04`, then 4 bytes | values 0, 1, 2 |
| `0x04` | String of 0..255 code units | length *n* (one unsigned byte), then *n* UTF-16BE code units | lengths 0..83, 127, 128 (`04 80`), 255 (`04 ff`) |
| `0x84` | String of 256 or more code units | length *n* (four bytes, big-endian), then *n* UTF-16BE code units | lengths 256 (`84 00 00 01 00`) and 13,739, Polish letters included |
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
- **A long string is one object**: it takes one reference index like a `0x04` string. In the
  customSQLLong sample 32 references follow it (for example `realInputFields`, two references
  to the `inputField` strings) and all resolve to the values IS exported.

## The long string tag `0x84` (customSQLLong, 2026-11-26)

**Symptom.** A real CustomSQL service with a long SQL template was not decoded
(`unsupported_tag: type tag 0x84 is not supported`); it fell back to the M12 reader
(`ADAPTER_CONFIGURATION_PARTIALLY_DECODED`, "runs custom SQL (not interpreted)") and its SQL
was never read. The byte offset depends on how long the strings before the `sql` key are
(362 in the owner's service, 380 in the sample).

**Bytes** (customSQLLong; text shown as its key name only):

```text
offset   bytes                       object
  368    05 01 00 02                 templateProperties document, class = reference to object 2
  372    04 03 0073 0071 006c        key "sql": string, one-byte length 3
  380    84 00 00 35 ab              long string: tag 0x84, length 0x000035ab = 13,739
  385    ... 27,478 bytes ...        13,739 UTF-16BE code units (the SQL template)
27863    04 0c 0073 0071 006c ...    key "sqlFieldType": string, one-byte length 12
```

**Cause.** Integration Server writes a string too long for the one-byte length with its own
tag, `0x84` (the string tag `0x04` with the high bit set), followed by the length as four
big-endian bytes. The decoder read objects by tag and did not know `0x84`, so it stopped at the
first byte of the value. It was not a misread length under `0x04`, not string content read as
a tag, not a wrong offset and not a reference problem: the decoder was in step up to that byte,
and everything after it reads correctly once the tag is known.

**Evidence.** The four bytes equal the number of UTF-16 code units of the SQL in the IS export
(13,739). Read this way, all 29,459 bytes parse to the end by the confirmed rules alone, no
hypothesis is used, and the document equals the IS export (`expected.json`, 13,739 characters,
8 of them Polish letters). The 32 references after the long string resolve to the exported
values, so it is numbered as one object.

**The switch point** (jdbcadapter3 exports, 2026-11-26): SQL templates of exactly 127, 128,
255 and 256 ASCII characters were written as `04 7f`, `04 80`, `04 ff` and
`84 00 00 01 00`, each followed by the text. So the one-byte length of `0x04` is unsigned
(0..255) and IS uses `0x84` from 256 code units on. The exports of 128 and 255 had been read
before by the `byte` hypothesis (marked unconfirmed); that reading is now the rule, and the
other readings (`leb128`, `vlq`, `u15`) are ruled out for string lengths. The reader also
accepts `0x84` for a shorter string (the four bytes say how long it is), which IS does not
write.

**Still not known.** Whether arrays or references have long forms (`0x8a`, `0x80` were not
seen and stay `unsupported_tag`), and how a count of 128 or more or an index past 127 is
written.

## Assumptions (consistent with the samples, not proven)

- The leading Integer is a format version; only `1` is accepted.
- Integers are signed (Java `int`); only small positive values were seen. The four-byte length
  of a long string is read the same way; a negative one is refused (`invalid_length`).
- Lengths count UTF-16 code units, so a character outside the Basic Multilingual Plane counts
  two. IS-written values show ASCII and Polish letters (customSQLLong); a character outside the
  Basic Multilingual Plane (an emoji) was seen only in the encoder's own output.

## Not known by the confirmed rules

| What | Why it matters | `decode_idata` (confirmed rules) |
| --- | --- | --- |
| An array count or reference index of 128 or more (a first byte `0x80`..`0xff` after `0x0a` or `0x00`) | String lengths are confirmed (one unsigned byte up to 255, then `0x84`); how arrays of 128 or more items and references past index 127 are written is not known. | `unsupported_length` |
| Whether a nested document's end marker counts as an object | No sample references an object written after a nested document closes. | a reference to such an object: `ambiguous_reference` |
| References to documents or arrays | Not seen. | `unsupported_reference` |
| Null values, booleans, other number types, byte arrays, dates; tags `0x01`, `0x03`, `0x06`..`0x09`, `0x0c` and above other than `0x84` (also `0x80`, `0x85`, `0x8a`, `0x8b`: the high bit on another tag) | Not seen. | `unsupported_tag` |
| A document marker other than `0x01`, an end marker other than `0x02 0x00`, an Integer width other than `0x04` | Not seen. | `unsupported_marker` |
| Documents with repeated keys | IData allows them; none seen. | decoded in order; `to_plain` refuses them |

The first two rows are the only ones a hypothesis may lift (next section); every other row
always stands.

## Hypotheses (owner decision, M15 extension; not confirmed)

The owner accepted, on 2026-11-25, that values the confirmed rules cannot read are read by
hypothesis, and checks the results against IS exports. `decode_idata_hypotheses` first runs
the confirmed rules; only when they stop at `unsupported_length` or `ambiguous_reference` does
it try every combination of:

| Count and index readings (`LENGTH_SCHEMES`; string lengths no longer use them) | Meaning of a first byte of 128 or more |
| --- | --- |
| `leb128` | 7-bit groups, least significant first, high bit set while more follow (protobuf) |
| `vlq` | 7-bit groups, most significant first, high bit set while more follow |
| `byte` | the byte itself, 128..255 |
| `u15` | 15 bits in two bytes: the low 7 bits of the first byte, then the second byte |

| Numbering after a nested document's end (`END_NUMBERINGS`) | |
| --- | --- |
| `end-not-counted` | the end marker is not an object |
| `end-counted` | the end marker takes an index (a reference to it is invalid) |

What the IS exports showed about them: a 13,739-character SQL is not `0x04` with a longer
length but the tag `0x84`, which none of these readings describes; because an unknown tag
(`unsupported_tag`) is never lifted by a hypothesis, that value stayed `partial` instead of
being read wrongly, until the tag was confirmed. For string lengths of 128..255 the `byte`
reading was right (customSQL128, customSQL255) and is now a confirmed rule. The readings
still apply only to a first byte of 128 or more after `0x0a` or `0x00`, which no sample
shows.

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
   in a new folder under `samples/jdbcadapter/` (any depth, for example
   `samples/jdbcadapter/<namespace folder>/<name>/` next to that folder's `node.idf`).
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
tested at every possible cut of the small samples), bytes after the document (`trailing_bytes`),
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
| Strings of 128 or more characters | read with a one-byte length (right up to 255), then resynchronises on later strings | by the confirmed rules: one unsigned length byte up to 255, the long string tag `0x84` from 256 |
| Repeated strings (references) | a key whose value is a reference is skipped | resolved |

## Recommended samples

To lift the limits above, export these from IS 10.15 the same way (node.ndf plus the JSON of
`bytesToDocument` -> `documentToJSONString`) and add them under `samples/jdbcadapter/<name>/`
(any folder name; the tests find every folder with a `node.ndf` and a `.json`):

1. (Done 2026-11-26: SQL of 127, 128, 255 and 256 characters, `jdbcadapter3/`.) Optional: one
   longer than 65,536 characters (three of the four length bytes in use).
2. A service with 130 or more input or output fields, or a long column list (counts and
   reference indexes past 127, and whether arrays and references have a long tag like `0x84`).
3. A service whose top-level fields after `templateProperties` repeat an earlier value, for
   example an input record name equal to an output field name (end-marker numbering).
4. One sample of each other template: SelectSQL, InsertSQL, UpdateSQL, DeleteSQL,
   BatchInsertSQL, BatchUpdateSQL, StoredProcedure, StoredProcedureWithSignature.
5. A JDBC connection (`ConnectionData`) and a JDBC notification, with dummy credentials, to move
   them from the M12 reader to the decoder.
6. A configuration with a missing optional field (for example no output fields), and one
   with non-ASCII text in a field name or a character outside the Basic Multilingual Plane
   (Polish letters in the SQL are confirmed by customSQLLong).

## Regression tests

| Test | Checks | Kind |
| --- | --- | --- |
| `test_decoding_equals_the_document_integration_server_exported` | every sample folder decodes to its IS export with no hypothesis (all seven samples) | IS export |
| `test_integration_server_switches_to_the_long_string_tag_at_256` | the bytes before the SQL of 127, 128, 255 and 256 characters are `04 7f`, `04 80`, `04 ff`, `84 00 00 01 00` | IS export and bytes |
| `test_integration_server_writes_a_long_string_as_tag_0x84_and_a_four_byte_length` | the bytes before the SQL are `84` and its code-unit count; the confirmed rules read it whole | IS export and bytes |
| `test_a_long_string_takes_one_reference_index_like_any_string` | references after the long string resolve (`realInputFields`) | IS export and bytes |
| `test_every_truncation_of_a_real_value_is_reported` | every cut of the small samples and a spread of cuts of customSQLLong is `truncated` | IS bytes |
| `test_strings_on_both_sides_of_the_switch_round_trip` | lengths 0..255 (one unsigned byte) and 256..200,000 (`0x84`) | synthetic |
| `test_long_strings_keep_unicode_and_special_characters`, `test_a_reference_to_a_long_string_resolves`, `test_a_long_form_used_for_a_short_string_is_read` | Polish letters, an emoji (two code units), `^ ' " \ ${}`, references | synthetic |
| `test_a_long_length_is_never_trusted_beyond_the_bytes_present`, `test_unsupported_or_invalid_structures_are_explicit` | lengths past the end, cut length bytes, negative length, broken text, high-bit tags other than `0x84`; no hypothesis lifts them | synthetic |
| `test_a_long_custom_sql_from_integration_server_is_read_and_analysed` (`tests/fixtures/test_jdbc_adapter_samples.py`) | customSQLLong is decoded without fallback or hypothesis, its SQL equals the export, is read by `sql_analysis`, and reaches the page, the prompt and the Explorer | IS export, end to end |
