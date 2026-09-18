"""Gera insights de IA para o dashboard (batch diário).

Chama os provedores de IA direto (ai_providers) quando há chave disponível —
no GitHub Actions o GitHub Models atende com o token automático do job. Se não
houver nenhuma chave, cai para a Edge Function ai-dashboard do Supabase.
"""
from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import ai_providers

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
            "ticker": s.get("ticker"),
            "setor": s.get("setor"),
            "categoria": s.get("categoria"),
            "ultimo": s.get("ultimo"),
            "tendencia": s.get("tendencia"),
            "vol_regime": s.get("vol_regime"),
            "previsao_pct_horizonte": s.get("previsao_pct_horizonte"),
            "padroes": s.get("padroes"),
            "engine": s.get("engine"),
        })
    destaques = data.get("destaques") or {}
    return {
        "gerado": data.get("gerado"),
        "engine": data.get("engine"),
        "horizon_dias": data.get("horizon_dias"),
        "papeis_analisados": data.get("papeis_analisados"),
        "insights": data.get("insights"),
        "setores": data.get("setores"),
        "destaques": {k: destaques.get(k) for k in ("alta", "baixa", "anomalias")},
        "correlacoes": data.get("correlacoes"),
        "series": series,
    }


def _papeis_do_contexto(ctx: dict) -> list[dict]:
    out = []
    for s in ctx.get("series") or []:
        if s.get("categoria") not in ("acoes_b3", "fiis") or not s.get("ticker"):
            continue
        out.append({
            "ticker": s["ticker"],
            "nome": s.get("nome"),
            "setor": s.get("setor"),
            "preco": s.get("ultimo"),
            "tendencia": s.get("tendencia"),
            "previsao_pct": s.get("previsao_pct_horizonte"),
            "vol_regime": s.get("vol_regime"),
            "padroes": s.get("padroes") or [],
        })
    return out


def _prompt_market(ctx: dict) -> str:
    return f"""Você é analista quantitativo de mercado de capitais brasileiro (ações da B3, petróleo, FIIs, macro).

O JSON abaixo cobre TODOS os papéis da plataforma (ações e FIIs) com previsões estatísticas/TimesFM, além de
volatilidade, cripto e tráfego web. Considere o conjunto dos papéis — não apenas PRIO3 — e produza análise acionável.

Retorne APENAS JSON válido (sem markdown) neste formato:
{{
  "resumo": "2-3 frases sobre o cenário do conjunto de papéis",
  "riscos": ["risco 1", "risco 2"],
  "oportunidades": ["oportunidade 1", "oportunidade 2"],
  "series_destaque": [{{"id":"...", "leitura":"..."}}],
  "papeis_destaque": [{{"ticker":"...", "leitura":"..."}}],
  "leitura_setorial": "quais setores estão melhor/pior posicionados",
  "macro_juros": "impacto de juros/Selic no cenário",
  "cripto_fluxo": "leitura BTC/ETH vs emergentes",
  "confianca": 0.0
}}

Dados:
{json.dumps(ctx, ensure_ascii=False)[:20000]}"""


def _prompt_patterns(ctx: dict) -> str:
    return f"""Analise padrões temporais (preços de ações e FIIs, demanda via volume, volatilidade, tráfego web, cripto).
Analise todas as categorias e todos os papéis.

Retorne APENAS JSON:
{{
  "padroes_detectados": [{{"serie":"...", "padrao":"...", "impacto":"..."}}],
  "regime_mercado": "risk-on|risk-off|neutro",
  "sinal_prio3": "compra|venda|neutro|aguardar",
  "papeis_em_destaque": [{{"ticker":"...", "padrao":"...", "sinal":"compra|venda|neutro|aguardar"}}],
  "justificativa": "texto curto"
}}

Contexto:
{json.dumps(ctx, ensure_ascii=False)[:18000]}"""


def _prompt_signals(papeis: list[dict], horizonte, macro: str) -> str:
    return f"""Avalie CADA papel da B3 abaixo (ações e FIIs) usando os dados quantitativos fornecidos:
tendência, previsão do modelo em {horizonte or 21} pregões, regime de volatilidade e padrões técnicos detectados.

Contexto macro: {macro[:800]}

Retorne APENAS JSON válido (sem markdown), com exatamente um objeto por papel recebido e na mesma ordem:
{{"sinais":[{{"ticker":"PRIO3","sinal":"compra|neutro|venda","confianca":0,"tese":"até 180 caracteres","risco":"até 120 caracteres"}}]}}

Papéis:
{json.dumps(papeis, ensure_ascii=False)[:12000]}"""


def _analise(prompt: str, max_tokens: int, corpo_edge: dict) -> dict:
    """Provedor direto quando há chave; Edge Function como reserva."""
    erro_direto = None
    if ai_providers.configurados():
        try:
            conteudo, provedor = ai_providers.gerar(prompt, max_tokens)
            try:
                out = _json_from_text(conteudo)
            except Exception:  # noqa: BLE001
                out = {"resumo": conteudo, "raw": True}
            out["provider"] = provedor
            return out
        except Exception as e:  # noqa: BLE001
            erro_direto = e
    try:
        return _invoke_retry("ai-dashboard", corpo_edge)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"direto: {erro_direto}; edge: {e}" if erro_direto else str(e)) from None


def _json_from_text(txt: str) -> dict:
    t = (txt or "").strip()
    if t.startswith("```"):
        t = t.split("```")[1] if "```" in t[3:] else t.strip("`")
        t = t[4:].strip() if t.lower().startswith("json") else t.strip()
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("sem JSON na resposta")
    return json.loads(t[i : j + 1])


def _sinais_por_papel(ctx: dict, lote: int = 8) -> tuple[list[dict], str | None]:
    """Sinal da IA para cada papel da plataforma, em lotes para caber no prompt."""
    papeis = _papeis_do_contexto(ctx)
    macro = "; ".join(ctx.get("insights") or [])[:600]
    sinais: list[dict] = []
    erros: list[str] = []
    for k in range(0, len(papeis), lote):
        bloco = papeis[k : k + lote]
        body = {
            "type": "ticker_signals",
            "papeis": bloco,
            "horizon_dias": ctx.get("horizon_dias"),
            "macro": macro,
        }
        try:
            resp = _analise(_prompt_signals(bloco, ctx.get("horizon_dias"), macro), 3072, body)
            linhas = resp.get("sinais")
            if not linhas:  # provedor devolveu texto em vez de JSON estruturado
                linhas = (_json_from_text(str(resp.get("resumo") or ""))).get("sinais")
            for row in linhas or []:
                if row.get("ticker"):
                    row["provider"] = resp.get("provider")
                    sinais.append(row)
        except Exception as e:  # noqa: BLE001
            erros.append(f"lote {k // lote + 1}: {e}")
    return sinais, "; ".join(erros) or None


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
    try:
        with urllib.request.urlopen(req, timeout=180, context=_SSL) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"HTTP {e.code}: {detalhe}") from None


def _invoke_retry(fn: str, body: dict, tries: int = 3, wait: float = 20.0) -> dict:
    """Provedores de IA falham por cota/sobrecarga — tenta de novo antes de desistir.

    Erros permanentes (402/403, p.ex. projeto restrito) não são repetidos.
    """
    last: Exception | None = None
    for i in range(tries):
        try:
            return _invoke(fn, body)
        except Exception as e:  # noqa: BLE001
            last = e
            if any(c in str(e) for c in ("HTTP 402", "HTTP 403", "HTTP 404")):
                break
            if i < tries - 1:
                time.sleep(wait * (i + 1))
    raise last  # type: ignore[misc]


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
        "papeis_analisados": patterns.get("papeis_analisados"),
    }

    diretos = ai_providers.configurados()
    out["fonte"] = f"provedores diretos ({', '.join(diretos)})" if diretos else "supabase/ai-dashboard"
    if diretos:
        out["providers"] = {"priority": diretos, "configured_count": len(diretos)}
    else:
        try:
            out["providers"] = _invoke("ai-dashboard", {"type": "providers"})
        except Exception as e:  # noqa: BLE001
            out["providers_error"] = str(e)

    try:
        market = _analise(_prompt_market(ctx), 4096, {"type": "market_insights", "context": ctx})
        out["market"] = market
        out["provider"] = market.get("provider")
    except Exception as e:  # noqa: BLE001
        out["market_error"] = str(e)

    try:
        patterns_ai = _analise(_prompt_patterns(ctx), 2048, {"type": "pattern_analysis", "context": ctx})
        out["patterns"] = patterns_ai
        if not out.get("provider"):
            out["provider"] = patterns_ai.get("provider")
    except Exception as e:  # noqa: BLE001
        out["patterns_error"] = str(e)

    sinais, sinais_erro = _sinais_por_papel(ctx)
    out["sinais"] = sinais
    if sinais and not out.get("provider"):
        out["provider"] = sinais[0].get("provider")
    if sinais_erro:
        out["sinais_error"] = sinais_erro

    return out


def _preservar_anterior(out: dict, path: Path) -> dict:
    """Se a IA falhou, mantém a última análise boa em vez de publicar um stub vazio."""
    if out.get("sinais") or not path.is_file():
        return out
    try:
        antigo = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return out
    if not antigo.get("sinais"):
        return out
    antigo["stale"] = True
    antigo["stale_desde"] = out.get("gerado")
    antigo["stale_motivo"] = (
        out.get("market_error") or out.get("sinais_error") or out.get("providers_error") or "IA indisponível"
    )[:300]
    return antigo


def main() -> None:
    out = build_ai_insights()
    path = ROOT / "ai_insights.json"
    out = _preservar_anterior(out, path)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    prov = out.get("provider") or "offline"
    err = out.get("market_error") or out.get("patterns_error") or out.get("sinais_error")
    n = len(out.get("sinais") or [])
    if out.get("stale"):
        print(f"[AVISO] {path} · IA indisponível — mantidos {n} sinais de {out.get('gerado')}"
              f" · motivo: {out.get('stale_motivo')}")
        return
    print(f"[OK] {path} · provider={prov} · {n} papéis com sinal"
          + (f" · aviso: {err}" if err else ""))


if __name__ == "__main__":
    main()
