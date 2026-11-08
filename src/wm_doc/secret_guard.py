"""One secret guard for everything the tool may publish: names, values and diagnostics.

The analysis uses it before any disclosure mode is applied (literals, free text, unknown
attributes), the disclosure scan uses it for model text and Explorer text, and Graphviz and
provider diagnostics are redacted with it. One vocabulary, three rules:

- `is_secret_name`: a field, attribute or other name taken from the packages is secret-like
  when a word part contains a secret term (`userPassword`, `/request/pwd`), is a short one
  (`pw`, `pass`) or two parts form one (`api_key`, `privKey`). Broad on purpose: a value is
  withheld rather than risked.
- `is_secret_text`: a free text is secret-like when a word contains a secret term or two words
  form one ("the API key"); short words such as "pass" are ordinary in prose.
- `is_secret_key`: the key of a `key=value` pair inside a diagnostic must name the secret
  itself (`database_password`, `tokenValue`, `password1`), not something about it
  (`passwordPolicy`, `tokenizer`), so ordinary diagnostics stay readable. In a text to publish
  (model answers, Explorer text) a key that names an operation (`readPrivateKeys:`) or a
  service (`pkg.tokens:issue`) is not a pair either.

Values are also checked by shape (`secret_value_label`, `redact_secrets`): a secret-like
`key=value` pair, an Authorization header or bearer token, HTTP Basic credentials, a JSON Web
Token, a PEM or PGP private key, and a URL with a user name and password. Every pattern runs
in linear time, so long literals (Base64 payloads) cost little.
"""

from __future__ import annotations

import base64
import binascii
import re
from functools import lru_cache

SECRET_GUARD_STRATEGY_VERSION = "secret-guard.v2"

# A word part containing one of these is secret-like.
SECRET_WORDS = (
    "password",
    "passwd",
    "passw0rd",
    "pwd",
    "passphrase",
    "secret",
    "credential",
    "token",
    "apikey",
    "accesskey",
    "privatekey",
    "authorization",
    "bearer",
    "cookie",
    "sessionid",
)
# Whole name parts only (they are ordinary inside longer words and in prose).
SECRET_SHORT_PARTS = frozenset({"pw", "pswd", "pass"})
# Two neighbouring parts that together are a secret term: `api key`, `API_KEY`, `privKey`.
SECRET_PAIRS = frozenset(
    {("api", "key"), ("access", "key"), ("private", "key"), ("priv", "key"), ("session", "id")}
)
# A `key=value` key ending with one of these describes a secret rather than holding it.
DESCRIPTIVE_ENDINGS = frozenset(
    {
        "policy",
        "policies",
        "rule",
        "rules",
        "length",
        "min",
        "max",
        "minimum",
        "maximum",
        "expiry",
        "expires",
        "expiration",
        "hint",
        "type",
        "required",
        "enabled",
        "count",
        "size",
        "format",
        "strength",
        "url",
        "uri",
        "endpoint",
    }
)

# A key naming an operation (`readPrivateKeys`, `testGetToken`) is a service or step name in a
# text, not a value; only text detection uses this (diagnostics stay strict).
ACTION_WORDS = frozenset(
    {
        "get",
        "set",
        "read",
        "load",
        "save",
        "store",
        "create",
        "generate",
        "delete",
        "remove",
        "update",
        "check",
        "validate",
        "verify",
        "rotate",
        "reset",
        "fetch",
        "send",
        "encrypt",
        "decrypt",
        "sign",
        "list",
        "find",
        "lookup",
        "parse",
        "build",
        "write",
        "put",
        "add",
        "init",
        "import",
        "export",
        "issue",
        "revoke",
        "request",
        "mask",
        "hash",
        "encode",
        "decode",
        "test",
        "change",
        "handle",
        "process",
        "convert",
        "extract",
    }
)

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_PART_RE = re.compile(r"[a-z0-9]+")
_TRAILING_DIGITS_RE = re.compile(r"(?<=[a-z])[0-9]+$")


def name_parts(name: str) -> list[str]:
    """The lower-case word parts of a name: camel case, `_`, `-`, `.`, `/` and blanks split."""
    return _PART_RE.findall(_CAMEL_RE.sub(" ", name).casefold())


def _normal(part: str) -> str:
    """`password1` -> `password`, `keys` -> `key`: digits and a plural `s` do not hide a term."""
    part = _TRAILING_DIGITS_RE.sub("", part)
    return part[:-1] if len(part) > 3 and part.endswith("s") and not part.endswith("ss") else part


def _has_pair(parts: list[str]) -> bool:
    return any(pair in SECRET_PAIRS for pair in zip(parts, parts[1:], strict=False))


@lru_cache(maxsize=65_536)
def _secret_name(value: str) -> bool:
    parts = [_normal(part) for part in name_parts(value)]
    return (
        any(word in part for part in parts for word in SECRET_WORDS)
        or any(part in SECRET_SHORT_PARTS for part in parts)
        or _has_pair(parts)
    )


def is_secret_name(*values: str | None) -> bool:
    """Whether any name taken from the packages is secret-like."""
    return any(_secret_name(value) for value in values if value)


def is_secret_text(text: str | None) -> bool:
    """Whether a free text names a secret: a word containing a secret term, or a pair."""
    if not text:
        return False
    parts = [_normal(part) for part in name_parts(text)]
    return any(word in part for part in parts for word in SECRET_WORDS) or _has_pair(parts)


@lru_cache(maxsize=65_536)
def is_secret_key(key: str) -> bool:
    """Whether the key of a `key=value` pair in a diagnostic holds a secret value."""
    parts = [_normal(part) for part in name_parts(key)]
    if not parts or (len(parts) > 1 and parts[-1] in DESCRIPTIVE_ENDINGS):
        return False
    return (
        any(part.endswith(word) for part in parts for word in SECRET_WORDS)
        or any(part in SECRET_SHORT_PARTS for part in parts)
        or _has_pair(parts)
    )


# A key starts only where a run of name characters starts (linear scanning), and the scan
# never consumes values, so `Failed: password=x` finds `Failed` and `password`.
KEY_RE = re.compile(
    r"""(?x)
    (?<![A-Za-z0-9_.-])
    (?P<key>[A-Za-z_][A-Za-z0-9_.-]*)
    (?P<key_quote>["']?)
    (?P<separator>\s*[:=]\s*)
    """
)
# The value after a separator: a quoted string, or up to four words that are not a key.
VALUE_RE = re.compile(
    r"""(?x)
    "(?:[^"\\]|\\.)*" |
    '(?:[^'\\]|\\.)*' |
    [^\s,;|}\]]+(?:[ \t]+(?![A-Za-z_][A-Za-z0-9_.-]*["']?\s*[:=])[^\s,;|}\]]+){0,3}
    """
)
AUTHORIZATION_RE = re.compile(
    r"(?i)\b(authorization\s*[:=]\s*)"
    r"(?:(?:bearer|basic|digest|negotiate|token)\s+)?[^\s,;|}\]]+"
)
BEARER_RE = re.compile(r"(?i)\b(bearer\s+)[^\s,;|}\]]+")
BASIC_RE = re.compile(r"(?i)\b(basic\s+)([A-Za-z0-9+/]{4,}={0,2})(?![A-Za-z0-9+/=])")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*")
# Private keys only (certificates, public keys and PGP messages are not secrets); the body is
# the Base64 and header characters after the BEGIN line, so no END marker is searched for.
PEM_RE = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----[A-Za-z0-9+/=\s:,.-]*")
URL_USERINFO_RE = re.compile(r"(?i)(?<![a-z0-9+.-])([a-z][a-z0-9+.-]*://)[^\s/?#@:]+:[^\s/?#@]+@")
# Every value shape above contains one of these; texts without any skip the detailed checks.
_SHAPE_HINT_RE = re.compile(r"(?i)authorization|bearer|basic\s|eyJ|-----BEGIN|://")


def _is_basic_credentials(token: str) -> bool:
    """`user:password` in Base64, as sent in an HTTP Basic Authorization header."""
    try:
        decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
    except (binascii.Error, ValueError):
        return False
    return b":" in decoded and all(32 <= byte < 127 for byte in decoded)


def _holds_secret(match: re.Match[str]) -> bool:
    """Whether a `key: value` in a text to publish gives a secret value (not a name or step)."""
    key = match.group("key")
    if match.group("separator") == ":" and "." in key:
        return False  # `folder.subfolder:service`, a service name
    if any(_normal(part) in ACTION_WORDS for part in name_parts(key)):
        return False
    return is_secret_key(key)


def secret_value_label(text: str) -> str | None:
    """Name the first secret-like part of a text that is to be published, or None."""
    if ("=" in text or ":" in text) and any(
        _holds_secret(match) for match in KEY_RE.finditer(text)
    ):
        return "secret-like key/value"
    if not _SHAPE_HINT_RE.search(text):
        return None
    if AUTHORIZATION_RE.search(text) or BEARER_RE.search(text):
        return "authorization header or bearer value"
    if (
        JWT_RE.search(text)
        or PEM_RE.search(text)
        or URL_USERINFO_RE.search(text)
        or any(_is_basic_credentials(match.group(2)) for match in BASIC_RE.finditer(text))
    ):
        return "credential-like value"
    return None


def looks_like_secret(text: str | None) -> bool:
    return bool(text) and secret_value_label(text or "") is not None


def _redact_key_values(text: str, marker: str) -> str:
    pieces: list[str] = []
    last = 0
    for match in KEY_RE.finditer(text):
        if match.start() < last or not is_secret_key(match.group("key")):
            continue
        value = VALUE_RE.match(text, match.end())
        if value is None or value.end() == match.end():
            continue
        pieces += [text[last : match.end()], marker]
        last = value.end()
    pieces.append(text[last:])
    return "".join(pieces)


def redact_secrets(text: str, marker: str = "[REDACTED]") -> str:
    """Replace secret values in a diagnostic, keeping ordinary `key=value` pairs readable."""

    def basic(match: re.Match[str]) -> str:
        if not _is_basic_credentials(match.group(2)):
            return match.group(0)
        return f"{match.group(1)}{marker}"

    cleaned = _redact_key_values(text, marker) if "=" in text or ":" in text else text
    if not _SHAPE_HINT_RE.search(cleaned):
        return cleaned
    cleaned = AUTHORIZATION_RE.sub(lambda match: f"{match.group(1)}{marker}", cleaned)
    cleaned = BEARER_RE.sub(lambda match: f"{match.group(1)}{marker}", cleaned)
    cleaned = BASIC_RE.sub(basic, cleaned)
    cleaned = JWT_RE.sub(marker, cleaned)
    cleaned = PEM_RE.sub(marker, cleaned)
    return URL_USERINFO_RE.sub(lambda match: f"{match.group(1)}{marker}@", cleaned)
