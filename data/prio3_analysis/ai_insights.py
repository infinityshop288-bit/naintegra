"""Gera insights de IA via Supabase Edge Function ai-dashboard (batch diário)."""
from __future__ import annotations

import json
import os
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://voybsggeedpwcfdadnzt.supabase.co").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZveWJzZ2dlZWRwd2NmZGFkbnp0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMxNzU2MTQsImV4cCI6MjA4ODc1MTYxNH0.dy5AgSd1VWdP4WLGXy5V89pA4jgHijngHJjScApOo70",
)

try:
    import certifi

    _SSL = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001
    _SSL = ssl._create_unverified_context()


def _compact_patterns(data: dict) -> dict:
    series = []
    for s in data.get("series") or []:
        series.append({
            "id": s.get("id"),
            "nome": s.get("nome"),
            "categoria": s.get("categoria"),
            "ultimo": s.get("ultimo"),
            "tendencia": s.get("tendencia"),
            "vol_regime": s.get("vol_regime"),
            "previsao_pct_horizonte": s.get("previsao_pct_horizonte"),
            "padroes": s.get("padroes"),
            "engine": s.get("engine"),
        })
    return {
        "gerado": data.get("gerado"),
        "engine": data.get("engine"),
        "horizon_dias": data.get("horizon_dias"),
        "insights": data.get("insights"),
        "correlacoes": data.get("correlacoes"),
        "series": series,
    }


def _invoke(fn: str, body: dict) -> dict:
    url = f"{SUPABASE_URL}/functions/v1/{fn}"
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "apikey": SUPABASE_ANON_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=180, context=_SSL) as r:
        return json.loads(r.read().decode("utf-8"))


def build_ai_insights(patterns_path: Path | None = None) -> dict:
    p = patterns_path or ROOT / "ai_patterns.json"
    if not p.is_file():
        return {"error": "ai_patterns.json ausente", "gerado": datetime.now().isoformat()}
    patterns = json.loads(p.read_text(encoding="utf-8"))
    ctx = _compact_patterns(patterns)

    out: dict = {
        "gerado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "fonte": "supabase/ai-dashboard",
        "patterns_ref": patterns.get("gerado"),
    }

    try:
        providers = _invoke("ai-dashboard", {"type": "providers"})
        out["providers"] = providers
    except Exception as e:  # noqa: BLE001
        out["providers_error"] = str(e)

    try:
        market = _invoke("ai-dashboard", {"type": "market_insights", "context": ctx, "ai_provider": "gemini"})
        out["market"] = market
        out["provider"] = market.get("provider")
    except Exception as e1:  # noqa: BLE001
        try:
            market = _invoke("ai-dashboard", {"type": "market_insights", "context": ctx})
            out["market"] = market
            out["provider"] = market.get("provider")
        except Exception as e2:  # noqa: BLE001
            out["market_error"] = f"{e1}; retry: {e2}"

    try:
        patterns_ai = _invoke("ai-dashboard", {"type": "pattern_analysis", "context": ctx, "ai_provider": "openrouter"})
        out["patterns"] = patterns_ai
        if not out.get("provider"):
            out["provider"] = patterns_ai.get("provider")
    except Exception as e:  # noqa: BLE001
        out["patterns_error"] = str(e)

    return out


def main() -> None:
    out = build_ai_insights()
    path = ROOT / "ai_insights.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prov = out.get("provider") or "offline"
    err = out.get("market_error") or out.get("patterns_error")
    print(f"[OK] {path} · provider={prov}" + (f" · aviso: {err}" if err else ""))


if __name__ == "__main__":
    main()
