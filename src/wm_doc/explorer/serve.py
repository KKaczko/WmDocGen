"""A minimal static web server for a built explorer folder (`wm-doc explorer serve`).

The app reads its data with `fetch`, which browsers do not allow from `file://` pages, so the
folder needs any plain HTTP server. This one binds to the loopback address by default, serves
only the given folder, never lists directories or serves hidden files, and sends a strict
Content Security Policy.
"""

from __future__ import annotations

import ipaddress
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

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
        parts = self.path.split("?", 1)[0].split("#", 1)[0].split("/")
        if any(part.startswith(".") and part not in {"", "."} for part in parts):
            self.send_error(404)
            return None
        return super().send_head()

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


def make_server(directory: Path, host: str = "127.0.0.1", port: int = 8765) -> ExplorerServer:
    handler = partial(ExplorerRequestHandler, directory=str(directory.resolve()))
    return ExplorerServer((host, port), handler)
