"""
Vercel Python serverless function — HTTP wrapper around chat.answer().

Endpoint:  POST /api/chat
Request:   { "question": "...", "history": [...] }
Response:  { "answer": "...", "history": [...] }

Adds:
  - Per-IP rate limiting (in-memory; per-instance, not strict — fine for
    portfolio-scale traffic. For production at scale, swap for Vercel KV
    or Upstash Redis.)
  - Structured request logging (visible in Vercel dashboard → Functions → Logs)
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict
from http.server import BaseHTTPRequestHandler

# Make project root importable so we can `from chat import answer`
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from chat import answer  # noqa: E402


# ----------------------------------------------------------- rate-limit config

# Per-IP cap. Tune later if traffic patterns warrant.
RATE_WINDOW_SECONDS = 3600  # 1 hour
RATE_LIMIT_PER_WINDOW = 30  # questions per IP per window

# In-memory log of timestamps per IP. Survives between warm requests on the
# same instance; resets on cold start. NOT shared across Vercel instances —
# acceptable trade-off at this scale.
_ip_log: dict[str, list[float]] = defaultdict(list)


def _client_ip(request_headers) -> str:
    """Best-effort extract the originating client IP behind Vercel's edge."""
    fwd = request_headers.get("x-forwarded-for") or request_headers.get("X-Forwarded-For")
    if fwd:
        # First entry is the original client; rest are intermediaries
        return fwd.split(",")[0].strip()
    return request_headers.get("x-real-ip") or "unknown"


def _check_rate_limit(ip: str) -> tuple[bool, int]:
    """Return (allowed, remaining_in_window)."""
    now = time.time()
    cutoff = now - RATE_WINDOW_SECONDS
    # Drop expired timestamps
    _ip_log[ip] = [t for t in _ip_log[ip] if t > cutoff]
    if len(_ip_log[ip]) >= RATE_LIMIT_PER_WINDOW:
        return False, 0
    _ip_log[ip].append(now)
    return True, RATE_LIMIT_PER_WINDOW - len(_ip_log[ip])


# ----------------------------------------------------------- handler


class handler(BaseHTTPRequestHandler):
    """Vercel routes POST /api/chat to this class's do_POST."""

    def do_POST(self) -> None:
        start_time = time.time()
        ip = _client_ip(self.headers)

        # 1. Rate limit
        allowed, remaining = _check_rate_limit(ip)
        if not allowed:
            print(f"[chat] DENIED rate-limit ip={ip}")
            self._send_json(429, {
                "error": (
                    f"Rate limit exceeded ({RATE_LIMIT_PER_WINDOW} questions per hour). "
                    "Please try again later."
                )
            })
            return

        # 2. Parse body
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body."})
            return

        question = (body.get("question") or "").strip()
        history = body.get("history") or []

        if not question:
            self._send_json(400, {"error": "Field 'question' is required."})
            return
        if not isinstance(history, list):
            self._send_json(400, {"error": "Field 'history' must be a list."})
            return

        # 3. Generate
        try:
            text, new_history, _results = answer(question, history=history)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[chat] ERROR ip={ip} q={question[:80]!r} elapsed={elapsed:.2f}s err={type(e).__name__}: {e}")
            self._send_json(500, {"error": f"{type(e).__name__}: {e}"})
            return

        # 4. Log + respond
        elapsed = time.time() - start_time
        print(
            f"[chat] OK ip={ip} q={question[:80]!r} "
            f"answer_len={len(text)} elapsed={elapsed:.2f}s "
            f"remaining_window={remaining}"
        )
        self._send_json(200, {"answer": text, "history": new_history})

    def do_OPTIONS(self) -> None:
        # CORS preflight (same-origin in production but useful for local dev)
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    # ---------------------------------------------------------------- helpers

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, format: str, *args) -> None:
        # Suppress Vercel's default per-request HTTP access log line; we
        # already emit our own structured log above.
        return
