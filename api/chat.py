"""
Vercel Python serverless function — HTTP wrapper around chat.answer().

Endpoint:  POST /api/chat
Request:   { "question": "...", "history": [...] }
Response:  { "answer": "...", "history": [...] }
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Make project root importable so we can `from chat import answer`
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from chat import answer  # noqa: E402


class handler(BaseHTTPRequestHandler):
    """Vercel routes POST /api/chat to this class's do_POST."""

    def do_POST(self) -> None:
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

        try:
            text, new_history, _results = answer(question, history=history)
        except Exception as e:
            # Surface error class + message so the client can show something useful
            self._send_json(500, {"error": f"{type(e).__name__}: {e}"})
            return

        self._send_json(200, {"answer": text, "history": new_history})

    def do_OPTIONS(self) -> None:
        # CORS preflight — same-origin in production, but useful in local dev
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
