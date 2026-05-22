"""Heurísticas para converter respostas JSON da rede em registros ingestíveis pela inbox."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from .normalize import (
    flatten_alternativas,
    is_wrong_question,
    pick_answer_user,
    pick_disciplina,
    pick_enunciado,
    pick_gabarito,
    pick_resposta_discursiva,
    pick_source_id,
    scatter_alternativas_from_flat_keys,
)

HarvestEmitMode = Literal["wrong_only", "all_with_gabarito"]


def network_source_system(source_url_note: str) -> str:
    """Classifica origem pela URL da API/página (multi-site harvest)."""

    low = source_url_note.lower()
    if "tecconcursos" in low:
        return "tecconcursos_network"
    if "qconcursos" in low or "qconcurso" in low:
        return "qconcurso_network"
    if "fcconcursos" in low:
        return "fcconcursos_network"
    if "cebraspe" in low or "cespe" in low:
        return "cebraspe_network"
    if "vunesp" in low:
        return "vunesp_network"
    if "fgv" in low:
        return "fgv_network"
    return "exam_network"


def looks_like_question_bundle(d: dict[str, Any]) -> bool:
    if not isinstance(d, dict):
        return False

    alts: dict[str, str] = dict(scatter_alternativas_from_flat_keys(d))
    for src in (
        d.get("alternativas"),
        d.get("opcoes"),
        d.get("choices"),
        d.get("itens"),
        d.get("options"),
        d.get("alternative_list"),
        d.get("alternatives"),
        d.get("answer_options"),
        d.get("respostas"),
        d.get("alternativa_lista"),
        d.get("alternativasLista"),
        d.get("question_alternatives"),
    ):
        alts.update(flatten_alternativas(src))
        if len(alts) >= 2:
            break

    stem = pick_enunciado(d)
    return bool(stem and len(alts) >= 2)


def looks_like_discursive_bundle(d: dict[str, Any]) -> bool:
    stem = pick_enunciado(d)
    if not stem or len(stem.strip()) < 15:
        return False
    alts: dict[str, str] = dict(scatter_alternativas_from_flat_keys(d))
    for src in (
        d.get("alternativas"),
        d.get("opcoes"),
        d.get("choices"),
        d.get("itens"),
        d.get("options"),
        d.get("alternative_list"),
        d.get("alternatives"),
        d.get("answer_options"),
        d.get("respostas"),
        d.get("alternativa_lista"),
        d.get("alternativasLista"),
        d.get("question_alternatives"),
    ):
        alts.update(flatten_alternativas(src))
    if len(alts) >= 2:
        return False
    return pick_resposta_discursiva(d) is not None


def flatten_for_wrong_check(d: dict[str, Any]) -> dict[str, Any]:
    """Alinha vários camelCase/snake_cases para reutilizar is_wrong_question."""

    out: dict[str, Any] = dict(d)

    if "usuario_acertou" not in out:
        for k in ("answered_correctly", "answeredCorrectly", "usuarioAcertou"):
            if k in d:
                out["usuario_acertou"] = d[k]
                break

    if "resposta_usuario" not in out or out.get("resposta_usuario") in (None, ""):
        for k in ("user_answer", "userAnswer", "respostaMarcada", "marcacao_usuario", "user_option"):
            if k in d and d[k] not in (None, ""):
                out["resposta_usuario"] = d[k]
                break

    ac = out.get("acertou")
    if ac is None and isinstance(out.get("usuario_acertou"), bool):
        out["acertou"] = out["usuario_acertou"]

    if out.get("acertou") is None and "correct" in d and isinstance(d["correct"], bool):
        out["acertou"] = d["correct"]

    if pick_gabarito(out) is None:
        for k in ("gabaritoOfficial", "resposta_certa", "correct_answer", "correctAnswer"):
            if k in d:
                cand = {"gabarito": d[k]}
                g = pick_gabarito(cand)
                if g:
                    out["gabarito"] = g
                break

    return out


def infer_wrong_for_network(d: dict[str, Any]) -> bool | None:
    keyed = flatten_for_wrong_check(d)

    r = keyed.get("resultado") or d.get("result") or d.get("statusResolve")
    if isinstance(r, str) and r.strip().lower() in ("errado", "erro", "incorrect", "incorrecta"):
        return True

    if d.get("errou") is True or keyed.get("is_wrong") is True:
        return True

    if keyed.get("acertou") is False:
        return True
    if keyed.get("acertou") is True:
        return False

    norm: dict[str, Any] = {**keyed}
    norm["resposta_usuario"] = norm.get("resposta_usuario") or pick_answer_user(d)
    norm["gabarito"] = norm.get("gabarito") or pick_gabarito(d)
    if isinstance(r, str):
        norm["resultado"] = r
    return is_wrong_question(norm)


def _alternativas_dict(fragment: dict[str, Any]) -> dict[str, str]:
    alts: dict[str, str] = dict(scatter_alternativas_from_flat_keys(fragment))
    for pool in (
        fragment.get("alternativas"),
        fragment.get("opcoes"),
        fragment.get("choices"),
        fragment.get("options"),
        fragment.get("itens"),
        fragment.get("answer_options"),
    ):
        alts.update(flatten_alternativas(pool))
        if len(alts) >= 2:
            break
    return alts


def _titulo_questao(*, tipo: str, disciplina: str | None, oid: object | None, stem: str) -> str:
    parts: list[str] = []
    parts.append("Questão objetiva" if tipo == "obj" else "Questão discursiva")
    if disciplina and str(disciplina).strip():
        parts.append(str(disciplina).strip()[:200])
    if oid is not None and str(oid).strip():
        parts.append(f"id {str(oid).strip()[:40]}")
    base = " · ".join(parts)
    if len(base) > 220:
        return base[:217] + "…"
    if len(base) < 24 and stem.strip():
        return (stem[:200] + ("…" if len(stem) > 200 else "")).strip()
    return base


def _objective_row_lex_fields(
    *,
    fragment: dict[str, Any],
    keyed: dict[str, Any],
    stem: str,
    alts: dict[str, str],
    gab: str | None,
    wrong: bool | None,
    emit_if_wrong_unknown: bool,
    source_url_note: str,
    harvest_emit_mode: HarvestEmitMode,
) -> dict[str, Any]:
    oid = pick_source_id(fragment) or fragment.get("uuid") or fragment.get("_id")
    disciplina = (
        fragment.get("disciplina")
        or keyed.get("disciplina")
        or fragment.get("subject_name")
        or fragment.get("materia_nome")
        or fragment.get("discipline")
    )
    disc_str = disciplina.strip()[:500] if isinstance(disciplina, str) and disciplina.strip() else None
    titulo = _titulo_questao(
        tipo="obj",
        disciplina=disc_str,
        oid=oid,
        stem=stem,
    )
    alt_list = [{"letra": k, "texto": v} for k, v in sorted(alts.items())]
    row: dict[str, Any] = {
        "source": source_url_note,
        "source_system": network_source_system(source_url_note),
        "type": "questoes_objetivas",
        "doc_type": "questoes_objetivas",
        "titulo": titulo,
        "texto_questao": stem or "",
        "enunciado": stem or "",
        "alternativas": alt_list,
        "_network_capture": True,
        "_harvest_emit_mode": harvest_emit_mode,
    }
    if disc_str:
        row["disciplina"] = disc_str
        row["materia"] = disc_str
    if oid:
        row["id"] = str(oid)

    usr = pick_answer_user(fragment) or pick_answer_user(keyed)
    if keyed.get("acertou") is not None:
        row["acertou"] = keyed["acertou"]
    elif wrong is True:
        row["acertou"] = False
    elif wrong is False:
        row["acertou"] = True
    elif wrong is None and emit_if_wrong_unknown:
        row["acertou"] = False
        row["_assumed_wrong_no_flag"] = True

    if gab:
        row["gabarito"] = gab
    if usr:
        row["resposta_usuario"] = usr

    if row.get("acertou") is False:
        row.setdefault("resultado", "errado")

    return row


def api_fragment_to_inbox_records(
    fragment: dict[str, Any],
    *,
    harvest_emit_mode: HarvestEmitMode,
    emit_if_wrong_unknown: bool,
    source_url_note: str,
) -> list[dict[str, Any]]:
    if looks_like_question_bundle(fragment):
        keyed = flatten_for_wrong_check(fragment)
        stem = pick_enunciado(fragment)
        alts = _alternativas_dict(fragment)
        gab = pick_gabarito(fragment) or pick_gabarito(keyed)
        wrong = infer_wrong_for_network(fragment)

        if harvest_emit_mode == "all_with_gabarito":
            if len(alts) < 2 or not gab:
                return []
            row = _objective_row_lex_fields(
                fragment=fragment,
                keyed=keyed,
                stem=stem or "",
                alts=alts,
                gab=gab,
                wrong=wrong,
                emit_if_wrong_unknown=emit_if_wrong_unknown,
                source_url_note=source_url_note,
                harvest_emit_mode=harvest_emit_mode,
            )
            return [row]

        if wrong is not True:
            if not (wrong is None and emit_if_wrong_unknown):
                return []
        row = _objective_row_lex_fields(
            fragment=fragment,
            keyed=keyed,
            stem=stem or "",
            alts=alts,
            gab=gab,
            wrong=wrong,
            emit_if_wrong_unknown=emit_if_wrong_unknown,
            source_url_note=source_url_note,
            harvest_emit_mode=harvest_emit_mode,
        )
        return [row]

    if harvest_emit_mode == "all_with_gabarito" and looks_like_discursive_bundle(fragment):
        stem = pick_enunciado(fragment)
        ans = pick_resposta_discursiva(fragment)
        if not stem or not ans:
            return []
        oid = pick_source_id(fragment) or fragment.get("uuid") or fragment.get("_id")
        disc = pick_disciplina(fragment)
        disc_str = disc.strip()[:500] if isinstance(disc, str) and disc.strip() else None
        titulo = _titulo_questao(tipo="disc", disciplina=disc_str, oid=oid, stem=stem)
        row: dict[str, Any] = {
            "source": source_url_note,
            "source_system": network_source_system(source_url_note),
            "type": "questoes_subjetivas",
            "doc_type": "questoes_subjetivas",
            "titulo": titulo,
            "enunciado_questao": stem,
            "texto_questao": stem,
            "resposta_modelo": ans,
            "_network_capture": True,
            "_harvest_emit_mode": harvest_emit_mode,
        }
        if oid:
            row["id"] = str(oid)
        if disc_str:
            row["disciplina"] = disc_str
            row["materia"] = disc_str
        return [row]

    return []


def api_fragment_to_inbox_record(
    fragment: dict[str, Any],
    *,
    emit_if_wrong_unknown: bool = False,
    source_url_note: str = "https://www.qconcursos.com/",
) -> dict[str, Any] | None:
    """Compatível com chamadas antigas — apenas modo ``wrong_only``."""

    got = api_fragment_to_inbox_records(
        fragment,
        harvest_emit_mode="wrong_only",
        emit_if_wrong_unknown=emit_if_wrong_unknown,
        source_url_note=source_url_note,
    )
    return got[0] if got else None


def walk_json_yield_dicts(payload: Any, *, max_visits: int = 2500) -> list[dict[str, Any]]:
    stack: list[Any] = [payload]
    found: list[dict[str, Any]] = []
    visited = 0
    ptr_seen: set[int] = set()

    while stack and visited < max_visits:
        cur = stack.pop()
        visited += 1

        if isinstance(cur, dict):
            pid = id(cur)
            if pid in ptr_seen:
                continue
            ptr_seen.add(pid)
            found.append(cur)
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for item in cur:
                if isinstance(item, (dict, list)):
                    stack.append(item)

    return found


def dedupe_signature_objetiva(rec: dict[str, Any]) -> str:
    slug = {"e": rec.get("texto_questao") or rec.get("enunciado"), "a": rec.get("alternativas")}
    blob = json.dumps(slug, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def dedupe_signature_discursiva(rec: dict[str, Any]) -> str:
    slug = {
        "t": "disc",
        "e": rec.get("enunciado_questao") or rec.get("texto_questao"),
        "r": (rec.get("resposta_modelo") or "")[:2000],
    }
    blob = json.dumps(slug, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def extract_inbox_records_from_json_payload(
    payload: Any,
    *,
    emit_if_wrong_unknown: bool,
    harvest_emit_mode: HarvestEmitMode = "all_with_gabarito",
    dedupe_keys_seen: set[str],
    source_url_note: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for frag in walk_json_yield_dicts(payload):
        for rec in api_fragment_to_inbox_records(
            frag,
            harvest_emit_mode=harvest_emit_mode,
            emit_if_wrong_unknown=emit_if_wrong_unknown,
            source_url_note=source_url_note,
        ):
            if rec.get("doc_type") == "questoes_subjetivas":
                sig = "disc:" + dedupe_signature_discursiva(rec)
            else:
                sig = "obj:" + dedupe_signature_objetiva(rec)
            if sig in dedupe_keys_seen:
                continue
            dedupe_keys_seen.add(sig)
            records.append(rec)
    return records
