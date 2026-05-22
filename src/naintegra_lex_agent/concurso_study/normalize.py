from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _letter_key(tok: str) -> str:
    t = tok.strip().upper()
    return t[:1] if len(t) == 1 else t


_SCATTER_ALT_KEY = re.compile(
    r"^(?:alternativa|opcao|opção|alt|choice|item)_([a-z])(?:_texto|_text|_descricao)?$",
    re.I,
)


def scatter_alternativas_from_flat_keys(d: dict[str, Any]) -> dict[str, str]:
    """Campos soltos ``alternativa_a`` / ``opcao_b`` comuns em APIs PHP/JS (ex.: agregadores)."""

    out: dict[str, str] = {}
    for k, v in d.items():
        if not isinstance(k, str) or v is None:
            continue
        m = _SCATTER_ALT_KEY.match(k.strip())
        if not m:
            continue
        s = str(v).strip()
        if s:
            out[_letter_key(m.group(1))] = s
    return out


def flatten_alternativas(raw: Any) -> dict[str, str]:
    """Converte vários formatos de crawl em dict letra→texto (A,B,C...)."""

    if raw is None:
        return {}

    if isinstance(raw, dict):
        out: dict[str, str] = {}
        for k, v in raw.items():
            if v is None:
                continue
            key = _letter_key(str(k))
            out[key] = str(v).strip()
        return out

    if isinstance(raw, list):
        out = {}
        for item in raw:
            if isinstance(item, str):
                m = re.match(r"^\s*\(?([A-Za-z])\)?\s*[\).\:-]\s*(.+)", item.strip(), re.DOTALL)
                if m:
                    out[_letter_key(m.group(1))] = m.group(2).strip()
                continue
            if not isinstance(item, dict):
                continue
            letra = (
                item.get("letra")
                or item.get("label")
                or item.get("opcao")
                or item.get("col")
                or item.get("sigla")
                or item.get("codigo")
                or item.get("letter")
            )
            ordem = item.get("ordem") or item.get("order") or item.get("index")
            if letra is None and isinstance(ordem, int) and 1 <= ordem <= 26:
                letra = chr(ordem + 64)
            txt = (
                item.get("texto")
                or item.get("text")
                or item.get("conteudo")
                or item.get("valor")
                or item.get("descricao")
                or item.get("description")
                or item.get("alternativa")
                or item.get("conteudo_html")
            )
            if letra is not None and txt is not None:
                out[_letter_key(str(letra))] = str(txt).strip()
        return out

    if isinstance(raw, str):
        # tenta JSON embutido
        try:
            parsed = json.loads(raw)
            return flatten_alternativas(parsed)
        except (json.JSONDecodeError, TypeError):
            pairs = re.findall(
                r"^\s*\(?([A-Za-z])\)?\s*[\).\:-]\s*(.+)$", raw, flags=re.MULTILINE
            )
            return {_letter_key(a): b.strip() for a, b in pairs}

    return {}


def pick_enunciado(r: dict[str, Any]) -> str:
    for key in (
        "enunciado",
        "pergunta",
        "titulo_questao",
        "texto_questao",
        "statement",
        "questao",
        "stem",
        "titulo",
        "descricao",
        "nome",
        "texto",
        "conteudo",
        "conteúdo",
        "statement_html",
        "html_statement",
        "text",
        "question_text",
        "questionText",
        "tituloQuestao",
        "enunciado_html",
    ):
        val = r.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    vb = r.get("verbatim_body") or r.get("body")
    if vb and str(vb).strip():
        return str(vb).strip()
    return ""


def pick_answer_user(r: dict[str, Any]) -> str | None:
    for key in (
        "resposta_usuario",
        "marcacao",
        "marcada",
        "resposta_marcada",
        "usuario_resposta",
        "alternativa_marcada",
    ):
        v = r.get(key)
        if v is None or str(v).strip() == "":
            continue
        return str(v).strip().upper()[:16]
    return None


def pick_resposta_discursiva(r: dict[str, Any]) -> str | None:
    """Referência / gabarito de questão discursiva (API ou export manual)."""

    for key in (
        "resposta_modelo",
        "gabarito_discursivo",
        "resposta_oficial",
        "padrao_resposta",
        "espelho_correcao",
        "ponto_avaliacao",
        "resposta_esperada",
        "gabarito_texto",
        "correcao_comentario",
        "official_answer",
        "expected_answer",
    ):
        v = r.get(key)
        if v is None:
            continue
        s = str(v).strip()
        if len(s) >= 10:
            return s[:50_000]
    return None


def pick_gabarito(r: dict[str, Any], _depth: int = 0) -> str | None:
    if _depth > 3:
        return None

    gab_obj = r.get("gabarito")
    if isinstance(gab_obj, dict):
        nested = pick_gabarito(gab_obj, _depth + 1)
        if nested:
            return nested

    for key in (
        "gabarito",
        "resposta_correta",
        "alternativa_correta",
        "alternativaCorreta",
        "correta",
        "solucao",
        "solução",
        "right_answer",
        "correct_answer_letter",
        "correctAnswer",
        "opcao_correta",
        "opcaoCorreta",
        "resposta_letra",
        "letter_answer",
        "letra",
        "sigla",
    ):
        v = r.get(key)
        if isinstance(v, dict):
            continue
        if v is None or (isinstance(v, str) and str(v).strip() == ""):
            continue
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            if 0 <= v <= 4:
                return chr(ord("A") + v)
            if 1 <= v <= 5:
                return chr(ord("A") + v - 1)
            if 0 <= v <= 25:
                return chr(ord("A") + v)
            if 1 <= v <= 26:
                return chr(ord("A") + v - 1)
            continue
        # pode vir "Alternativa B" ou só "B"
        s = str(v).strip().upper()
        one = re.search(r"\b([A-E])\b", s)
        if one:
            return one.group(1)
        return s[:1] if len(s) == 1 else s[:16]
    return None


def pick_disciplina(r: dict[str, Any]) -> str | None:
    for key in (
        "disciplina",
        "materia",
        "subject",
        "tema_principal",
        "area",
        "conteudo_programatico",
    ):
        v = r.get(key)
        if not v:
            continue
        s = str(v).strip()
        if s:
            return s[:500]
    return None


def pick_source_id(r: dict[str, Any]) -> str | None:
    for key in (
        "id",
        "external_id",
        "question_id",
        "questao_id",
        "public_id",
        "hash",
        "codigo",
        "pk",
        "slug",
        "uuid",
    ):
        v = r.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


_QCONCURSO_SOURCE_NEEDLES = frozenset(
    (
        "qconcursos.com",
        "www.qconcursos.com",
        "qconcurso.com",
        "www.qconcurso.com",
        "qconcursos.com.br",
        "www.qconcursos.com.br",
        "qconcursos",
        "qconcurso",
    )
)


def record_hints_qconcurso_source(record: dict[str, Any]) -> bool:
    """True se o JSON sugere origem QConcursos (qconcursos.com; inclui domínios legados)."""

    blob = json.dumps(record, ensure_ascii=False).lower()
    return any(n in blob for n in _QCONCURSO_SOURCE_NEEDLES)


def is_wrong_question(r: dict[str, Any]) -> bool | None:
    """True/errado; None se não dá para concluir (registro deve ser ignorado na consolidação)."""

    ex = (
        ("acertou", False),
        ("usuario_acertou", False),
        ("correto_usuario", False),
        ("errou", True),
        ("is_wrong", True),
        ("incorreta", True),
        ("incorrect", True),
    )
    for k, wanted in ex:
        if k in r and isinstance(r[k], bool) and r[k] == wanted:
            return True

    res = str(r.get("resultado", "")).strip().lower()
    if res in ("errado", "erro", "incorrect", "falso"):
        return True

    gab = pick_gabarito(r)
    usr = pick_answer_user(r)
    if gab and usr:
        g_letter = re.search(r"\b([A-E])\b", gab)
        u_letter = re.search(r"\b([A-E])\b", usr)
        gs = g_letter.group(1) if g_letter else gab[:1]
        us = u_letter.group(1) if u_letter else usr[:1]
        if gs and us and gs != us:
            return True

    if r.get("acertou") is True:
        return False
    if r.get("errou") is False and r.get("classificacao") == "CERTA":
        return False

    return None


def stem_key(enunciado: str, alternativas: dict[str, str]) -> str:
    ne = normalize_ws(enunciado)
    pairs = "|".join(f"{k}:{normalize_ws(v)}" for k, v in sorted(alternativas.items()))
    blob = f"{ne}\n{pairs}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
