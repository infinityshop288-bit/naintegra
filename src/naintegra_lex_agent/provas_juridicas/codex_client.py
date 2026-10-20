"""Cliente da Responses API em api.codexilimitado.com (POST /v1/responses)."""

from __future__ import annotations

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BASE = "https://api.codexilimitado.com"
DEFAULT_MODEL = "gpt-5.6-sol"
ALLOWED_MODELS = frozenset({"gpt-5.6-sol", "gpt-6-astra", "gpt-6-sol", "gpt-6-luna"})
CLIENT_TIMEOUT = 900  # respostas com raciocínio pesado; timeout curto aborta o stream
_env_file: dict[str, str] | None = None

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()


def _read_env_file() -> dict[str, str]:
    global _env_file
    if _env_file is not None:
        return _env_file
    found: dict[str, str] = {}
    path = ROOT / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value:
                found.setdefault(key.strip(), value)
    _env_file = found
    return found


def env(name: str, default: str = "") -> str:
    value = (os.environ.get(name) or "").strip()
    if value:
        return value
    return (_read_env_file().get(name) or default).strip()


def resolve_model(name: str | None) -> str:
    chosen = (name or env("CODEX_MODEL") or DEFAULT_MODEL).strip()
    if chosen not in ALLOWED_MODELS:
        raise ValueError(f"modelo inválido {chosen!r}; use um de {sorted(ALLOWED_MODELS)}")
    return chosen


def extract_output_text(data: dict[str, Any]) -> str:
    direto = str(data.get("output_text") or "").strip()
    if direto:
        return direto
    parts: list[str] = []
    for item in data.get("output") or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for chunk in item.get("content") or []:
            if not isinstance(chunk, dict):
                continue
            if chunk.get("type") in {"output_text", "text"} and chunk.get("text"):
                parts.append(str(chunk["text"]))
    return "".join(parts).strip()


def _post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
            status, body = resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{exc.code}: {detail}") from None
    if not body.strip():
        raise RuntimeError(f"{status}: resposta vazia")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{status}: resposta não-JSON: {body[:200]}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{status}: JSON inesperado")
    if parsed.get("error"):
        err = parsed["error"]
        msg = err.get("message") if isinstance(err, dict) else err
        raise RuntimeError(f"{status}: {msg}")
    return parsed


def post_responses(
    payload: dict[str, Any],
    *,
    timeout: float = CLIENT_TIMEOUT,
) -> dict[str, Any]:
    key = env("CODEX_API_KEY")
    if not key:
        raise RuntimeError("CODEX_API_KEY ausente")
    base = (env("CODEX_BASE_URL") or DEFAULT_BASE).rstrip("/")
    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": "curl/8.7.1",
        "Accept": "application/json",
    }
    url = f"{base}/v1/responses"
    wait, last = 2.0, None
    for attempt in range(4):
        try:
            return _post(url, payload, headers, timeout)
        except RuntimeError as exc:
            last = exc
            code = str(exc).split(":", 1)[0].strip()
            if code not in {"429", "500", "502", "503", "504"}:
                raise
            logger.warning("Codex %s (tentativa %s/4): %s", code, attempt + 1, exc)
            time.sleep(wait)
            wait = min(wait * 2, 30)
    raise last  # type: ignore[misc]


def create_response(
    *,
    input_text: str,
    instructions: str,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = CLIENT_TIMEOUT,
) -> str:
    payload = {
        "model": resolve_model(model),
        "instructions": instructions,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": input_text}]}],
        "stream": False,
        "temperature": temperature,
    }
    data = post_responses(payload, timeout=timeout)
    text = extract_output_text(data)
    if not text:
        raise RuntimeError("resposta sem texto")
    return text


def create_response_turn(
    *,
    input_items: list[dict[str, Any]],
    instructions: str,
    tools: list[dict[str, Any]] | None = None,
    model: str | None = None,
    temperature: float = 0.2,
    timeout: float = CLIENT_TIMEOUT,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": resolve_model(model),
        "instructions": instructions,
        "input": input_items,
        "stream": False,
        "temperature": temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return post_responses(payload, timeout=timeout)
