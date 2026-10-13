"""Secure Vercel serverless proxy for the SecureDoc AI FastAPI backend on Railway.

The browser only ever talks to the Vercel origin. This function forwards the
three public API calls to the backend and injects the shared API key from a
server-only environment variable, so the key never reaches the client. Request
bodies (which may contain document text) are streamed straight through and are
never logged.
"""

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

# The only requests that may reach the backend. Everything else is rejected
# without a network call, so this surface cannot be walked to other endpoints.
ALLOWED = {
    ("POST", "/api/process-document"),
    ("POST", "/api/upload-document"),
    ("GET", "/api/version"),
}

# The backend caps uploads at 5 MB; refuse larger bodies so the function never
# buffers an unbounded request. (Vercel's own ~4.5 MB request limit applies
# first on the Hobby plan.)
MAX_BODY_BYTES = 6 * 1024 * 1024

# Keep below the function's maxDuration (60s). The LLM call can take tens of
# seconds; the backend caps its own provider call at 60s.
UPSTREAM_TIMEOUT_SECONDS = 55


def resolve_route(method: str, path: str) -> str | None:
    """Return the allowed route for this request, or None.

    Matches on exact path or a trailing match, so it works whether Vercel
    passes the bare path or a prefixed catch-all path.
    """
    method = method.upper()
    for allowed_method, route in ALLOWED:
        if method == allowed_method and (path == route or path.endswith(route)):
            return route
    return None


class handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        """Silence the default access log (never emit request details)."""

    def do_GET(self) -> None:
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _relay(self, status: int, body: bytes, content_type: str | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type or "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self) -> None:
        route = resolve_route(self.command, self.path.split("?", 1)[0])
        if route is None:
            self._send_json(404, {"message": "Not found"})
            return

        api_key = os.environ.get("SECUREDOC_API_KEY", "")
        backend = os.environ.get("BACKEND_URL", "").rstrip("/")
        if not api_key or not backend:
            self._send_json(503, {"message": "Proxy is not configured"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"message": "Request body too large"})
            return
        body = self.rfile.read(length) if length > 0 else None

        headers = {"X-API-Key": api_key}
        if self.headers.get("Content-Type"):
            headers["Content-Type"] = self.headers["Content-Type"]
        # Preserve the original client IP so the backend rate limiter keys on it
        # rather than on Vercel's shared egress address.
        for header in ("X-Forwarded-For", "X-Real-IP"):
            if self.headers.get(header):
                headers[header] = self.headers[header]

        request = urllib.request.Request(
            backend + route, data=body, headers=headers, method=self.command
        )
        try:
            with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as resp:
                self._relay(resp.status, resp.read(), resp.headers.get("Content-Type"))
        except urllib.error.HTTPError as exc:
            self._relay(exc.code, exc.read(), exc.headers.get("Content-Type"))
        except (urllib.error.URLError, TimeoutError, OSError):
            # Never surface upstream details or configuration.
            self._send_json(502, {"message": "Upstream backend unavailable"})


if __name__ == "__main__":
    # Tiny self-check: only the three documented routes resolve.
    assert resolve_route("POST", "/api/process-document") == "/api/process-document"
    assert resolve_route("POST", "/api/upload-document") == "/api/upload-document"
    assert resolve_route("GET", "/api/version") == "/api/version"
    assert resolve_route("GET", "/api/process-document") is None
    assert resolve_route("DELETE", "/api/version") is None
    assert resolve_route("GET", "/api/health") is None
    assert resolve_route("POST", "/api/../../admin") is None
    assert resolve_route("POST", "/api/process-document/") is None
    print("proxy routing self-check passed")
