"""Serve o Lex e a API do chat (Responses API no servidor)."""

from __future__ import annotations

import json
import logging
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .agent import run_turn
from .documents import list_documents
from .skills import list_skills, read_skill, save_skill, seed_builtin_skills

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "web" / "lex"
PORT = 8770
logger = logging.getLogger(__name__)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.end_headers()

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/lex-chat/skills":
            seed_builtin_skills()
            self._json({"skills": list_skills()})
            return
        if path == "/api/lex-chat/documentos":
            self._json({"documents": list_documents()})
            return
        if path.startswith("/api/lex-chat/skills/"):
            slug = path.rsplit("/", 1)[-1]
            skill = read_skill(slug)
            if not skill:
                self._json({"error": "skill não encontrada"}, 404)
                return
            self._json(skill)
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            body = self._read_json()
        except json.JSONDecodeError:
            self._json({"error": "JSON inválido"}, 400)
            return
        if path == "/api/lex-chat/skills":
            try:
                saved = save_skill(str(body.get("nome") or body.get("name") or ""), str(body.get("descricao") or body.get("description") or ""), str(body.get("instrucoes") or body.get("body") or ""))
            except Exception as exc:
                self._json({"error": str(exc)}, 400)
                return
            self._json(saved)
            return
        if path in {"/api/lex-chat", "/api/lex-chat/turn"}:
            messages = body.get("messages") or []
            if not isinstance(messages, list) or not messages:
                self._json({"error": "messages vazio"}, 400)
                return
            clean = []
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                clean.append({"role": str(msg.get("role") or "user"), "content": str(msg.get("content") or "")})
            try:
                result = run_turn(clean, skill=str(body.get("skill") or "") or None, model=body.get("model"))
            except Exception as exc:
                logger.exception("chat")
                self._json({"error": str(exc)}, 500)
                return
            self._json(result)
            return
        self._json({"error": "not found"}, 404)

    def log_message(self, fmt: str, *args: Any) -> None:
        first = str(args[0]) if args else ""
        if "/api/" in first:
            super().log_message(fmt, *args)


def serve(port: int = PORT) -> None:
    seed_builtin_skills()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    logger.info("Chat Lex em http://127.0.0.1:%s/#/chat", port)
    httpd.serve_forever()
