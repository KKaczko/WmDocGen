"""A minimal static web server for a built explorer folder (`wm-doc explorer serve`).

The app reads its data with `fetch`, which browsers do not allow from `file://` pages, so the
folder needs any plain HTTP server. This one binds to the loopback address by default, serves
only the given folder, never lists directories or serves hidden files (checked on the decoded
path, so `%2E` is a dot too), and sends a strict Content Security Policy. On a loopback
address it answers only requests whose Host header names this computer, so a web page that
points its own domain name at 127.0.0.1 (DNS rebinding) cannot read the explorer data.
"""

from __future__ import annotations

import ipaddress
import re
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

LOOPBACK_NAMES = ("localhost", "127.0.0.1", "[::1]")

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cache-Control": "no-cache",
}


class ExplorerRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".svg": "image/svg+xml",
        ".txt": "text/plain; charset=utf-8",
    }

    def send_head(self) -> Any:
        allowed = getattr(self.server, "allowed_hosts", None)
        host = (self.headers.get("Host") or "").strip().casefold()
        if allowed is not None and host not in allowed:
            self.send_error(HTTPStatus.MISDIRECTED_REQUEST)
            return None
        if self._hidden():
            self.send_error(404)
            return None
        return super().send_head()

    def _hidden(self) -> bool:
        """Whether the request names a dot file or folder, as written or as it would be served."""
        path = unquote(self.path.split("?", 1)[0].split("#", 1)[0])
        if any(part.startswith(".") and part not in {"", "."} for part in re.split(r"[/\\]", path)):
            return True
        # The file actually served: translate_path decodes and drops `..` its own way.
        served = Path(self.translate_path(self.path))
        try:
            parts = served.relative_to(self.directory).parts
        except ValueError:
            return True
        return any(part.startswith(".") for part in parts)

    def list_directory(self, path: Any) -> None:
        self.send_error(404)
        return None

    def end_headers(self) -> None:
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, value)
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        return


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class ExplorerServer(ThreadingHTTPServer):
    # The default backlog of 5 drops connections when a few browsers load the app at once.
    request_queue_size = 128
    daemon_threads = True
    # Host header values answered; None answers every one (a non-loopback address the
    # user chose to share, reached by whatever name the network gives it).
    allowed_hosts: frozenset[str] | None = None


def make_server(directory: Path, host: str = "127.0.0.1", port: int = 8765) -> ExplorerServer:
    handler = partial(ExplorerRequestHandler, directory=str(directory.resolve()))
    server = ExplorerServer((host, port), handler)
    if is_loopback(host):
        bound = server.server_address[1]
        listened = f"[{host}]" if ":" in host else host
        names = {*LOOPBACK_NAMES, listened.casefold(), "localhost."}
        server.allowed_hosts = frozenset(
            item for name in names for item in (name, f"{name}:{bound}")
        )
    return server
