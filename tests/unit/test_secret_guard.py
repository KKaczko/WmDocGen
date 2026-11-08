"""One secret guard (`wm_doc.secret_guard`) for literals, free text, model text and diagnostics.

The analysis used to know nine terms only, so a literal set into `pwd` or `apiKey` was stored
in plain text in `analysis.json` (and in the analysis cache) in the default include mode.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from flowxml import FlowPackage, map_, set_

from wm_doc.analysis_cache import input_fingerprint
from wm_doc.config import load_config
from wm_doc.disclosure import unsafe_disclosure_label
from wm_doc.flow_paths import path_ref
from wm_doc.ir import LiteralDisclosure
from wm_doc.secret_guard import (
    SECRET_GUARD_STRATEGY_VERSION,
    is_secret_key,
    is_secret_name,
    is_secret_text,
    redact_secrets,
    secret_value_label,
)

BASIC = "Basic dXNlcjpwYXNzd29yZA=="  # user:password
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJlLXZhbHVl"
PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIB\n-----END RSA PRIVATE KEY-----"


def _path(raw: str | None) -> str:
    ref = path_ref(raw)
    return ref.text() if ref is not None else ""


@pytest.mark.parametrize(
    "name",
    [
        "/request/pwd;1;0",
        "passwd",
        "userPassword",
        "apiKey",
        "API_KEY",
        "x-api-key",
        "private key",
        "privateKey",
        "accessKey",
        "client_secret",
        "Authorization",
        "bearerToken",
        "credentials",
        "passphrase",
        "db_pw",
        "userPswd",
        "passw0rd",
        "privKey",
        "apiKeys",
        "sessionId",
        "authCookie",
        "password1",
    ],
)
def test_secret_names_are_recognised_in_any_spelling(name: str) -> None:
    assert is_secret_name(name)


@pytest.mark.parametrize(
    "name",
    ["/order/status", "author", "authority", "orderId", "setup-wd", "apiVersion", "bypass"],
)
def test_ordinary_names_are_not_secret(name: str) -> None:
    assert not is_secret_name(name)


@pytest.mark.parametrize(
    ("key", "secret"),
    [
        ("database_password", True),
        ("access_token", True),
        ("apiKey", True),
        ("userPwd", True),
        ("Authorization", True),
        ("secretKey", True),
        ("tokenValue", True),
        ("passwordHash", True),
        ("password1", True),
        ("apiKeys", True),
        ("idtoken", True),
        ("tokenizer", False),
        ("passwordPolicy", False),
        ("secretary", False),
        ("node_id", False),
    ],
)
def test_keys_inside_a_text_must_be_or_end_with_a_secret_term(key: str, secret: bool) -> None:
    assert is_secret_key(key) is secret


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("pwd=abc123", "secret-like key/value"),
        ("Failed: password=hunter2", "secret-like key/value"),
        ("x: pwd=zz", "secret-like key/value"),
        ("GET http://h/x?a=1&token=abc", "secret-like key/value"),
        ("send apiKey: abc123 along", "secret-like key/value"),
        ("Bearer abc.def.ghi", "authorization header or bearer value"),
        (BASIC, "credential-like value"),
        (JWT, "credential-like value"),
        (PEM, "credential-like value"),
        ("https://user:s3cret@example.test/path", "credential-like value"),
        ("-----BEGIN PGP PRIVATE KEY BLOCK-----\nlQOYBF\n", "credential-like value"),
        ("-----BEGIN PGP MESSAGE-----\nhQEMAx\n-----END PGP MESSAGE-----", None),
        ("-----BEGIN CERTIFICATE-----\nMIIC\n-----END CERTIFICATE-----", None),
        ("readPrivateKeys: reads the key ring", None),
        ("Calls pgp.services.keys:readPrivateKeys: then testReadPrivateKeys: checks", None),
        ("Then pkg.tokens:issue runs", None),
        ("passwordPolicy: strict", None),
        ("Basic validation of the order", None),
        ("https://example.test/path", None),
        ("status: ACTIVE", None),
    ],
)
def test_secret_values_are_recognised_by_their_shape(text: str, label: str | None) -> None:
    assert secret_value_label(text) == label


@pytest.mark.parametrize(
    "text",
    [
        "A" * 200_000,
        "a." * 100_000,
        "eyJ" + "a" * 200_000,
        "-----BEGIN RSA PRIVATE KEY-----" + "M" * 200_000,
        "Basic " + "QUJD" * 50_000,
        "http://" + "a" * 200_000,
        "-----BEGIN RSA PRIVATE KEY-----\n" * 5_000,
        "a=b " * 50_000,
        "x: " * 70_000,
    ],
    ids=[
        "run",
        "dotted",
        "jwt-like",
        "pem-unterminated",
        "basic",
        "url",
        "pem-many",
        "pairs",
        "keys",
    ],
)
def test_long_values_are_checked_in_linear_time(text: str) -> None:
    started = time.perf_counter()

    secret_value_label(text)
    redact_secrets(text)
    is_secret_name(text)

    assert time.perf_counter() - started < 2.0


def test_free_text_uses_secret_terms_but_not_short_words() -> None:
    assert is_secret_text("Reads the API key from the vault.")
    assert is_secret_text("Refreshes the access token.")
    assert not is_secret_text("Pass the order to the warehouse, then pw ends.")


@pytest.mark.parametrize(
    ("text", "secret"),
    [
        ("Failed: password=hunter2 next", "hunter2"),
        ("error: token=abc", "abc"),
        ("x: pwd=zz", "zz"),
        ("GET http://h/x?a=1&token=abc-query", "abc-query"),
        ("secretKey=sk-1", "sk-1"),
        ("tokenValue=tv-2", "tv-2"),
        ("passwordHash=ph-3", "ph-3"),
        ("password1=p1-4", "p1-4"),
        ("apiKeys=ak-5", "ak-5"),
    ],
)
def test_a_secret_pair_is_redacted_wherever_it_stands(text: str, secret: str) -> None:
    assert secret not in redact_secrets(text)


def test_the_model_text_scan_uses_the_same_guard() -> None:
    assert unsafe_disclosure_label(f"It sends {BASIC} to the server.") == "credential-like value"
    assert unsafe_disclosure_label("It reads the order status.") is None


def test_diagnostics_lose_the_secret_and_keep_ordinary_pairs() -> None:
    text = (
        "failed Authorization: Bearer should-not-leak tokenizer=lexer "
        f"https://user:pw@host.test/x {BASIC} {JWT}"
    )

    cleaned = redact_secrets(text)

    for secret in ("should-not-leak", "user:pw", "dXNlcjpwYXNzd29yZA", JWT):
        assert secret not in cleaned
    assert "tokenizer=lexer" in cleaned
    assert "https://[REDACTED]@host.test/x" in cleaned


def test_literals_that_look_secret_are_never_stored(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Orders")
    pkg.service(
        "orders.api:call",
        map_(
            set_("/pwd", "hunter2-pwd"),
            set_("/apiKey", "k-123-api"),
            set_("/headers/value", "Bearer tok-456-bearer"),
            set_("/target/url", "https://svc:pw-789@api.test/orders"),
            set_("/order/status", "ACTIVE"),
        ),
    )

    analysis = pkg.analyze()  # the default literal mode includes values
    payload = analysis.model_dump_json()
    disclosures = {
        _path(operation.target_endpoint.raw_path): operation.literal.disclosure
        for operation in analysis.services[0].mapping_operations
        if operation.literal is not None and operation.target_endpoint is not None
    }

    for secret in ("hunter2-pwd", "k-123-api", "tok-456-bearer", "pw-789"):
        assert secret not in payload
    assert disclosures.pop("/order/status") is LiteralDisclosure.INCLUDED
    assert set(disclosures.values()) == {LiteralDisclosure.BLOCKED_SECRET}
    assert len(disclosures) == 4
    assert analysis.extraction_policy.secret_guard.strategy_version == SECRET_GUARD_STRATEGY_VERSION


def test_a_new_guard_version_invalidates_cached_analyses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_config(None)
    before = input_fingerprint(tmp_path, config, None, False)
    monkeypatch.setattr("wm_doc.analysis_cache.SECRET_GUARD_STRATEGY_VERSION", "secret-guard.v99")

    assert input_fingerprint(tmp_path, config, None, False) != before
