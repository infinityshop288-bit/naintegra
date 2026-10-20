"""Agente de chat: Responses API + tools de acervo, documentos e skills."""

from __future__ import annotations

import json
import logging
from typing import Any

from naintegra_lex_agent.provas_juridicas.codex_client import (
    DEFAULT_MODEL,
    create_response_turn,
    extract_output_text,
)

from .documents import list_documents, save_document
from .search import read_document, search_acervo
from .skills import list_skills, read_skill, save_skill, seed_builtin_skills

logger = logging.getLogger(__name__)

INSTRUCTIONS = """Tu és o assistente jurídico do NaIntegra Lex.

Podes pesquisar o acervo local (lei, súmula, tema, doutrina e provas), ler o texto oficial,
elaborar peças/pareceres/resumos e gravar skills.

Regras:
- Não inventes artigo, súmula, tema ou processo. Se precisar de base, chama buscar_acervo e ler_documento.
- Comandos do usuário: /pesquisar, /elaborar, /skill, /gravar-skill, /docs.
- Quando elaborares um documento completo, grava com gravar_documento.
- Skills são instruções persistentes em SKILL.md; aplica a skill ativa e as que o usuário pedir.
- Responde em português, em Markdown.
"""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "buscar_acervo",
        "description": "Pesquisa legislação, jurisprudência, doutrina ou provas no acervo local.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termos da busca"},
                "kind": {
                    "type": "string",
                    "description": "all | legislacao | juris | doutrina | prova",
                },
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "type": "function",
        "name": "ler_documento",
        "description": "Lê o texto de um item do acervo pelo id ou URL.",
        "parameters": {
            "type": "object",
            "properties": {"id": {"type": "string"}},
            "required": ["id"],
        },
    },
    {
        "type": "function",
        "name": "gravar_documento",
        "description": "Grava um documento elaborado (peça, parecer, resumo).",
        "parameters": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string"},
                "tipo": {"type": "string"},
                "markdown": {"type": "string"},
            },
            "required": ["titulo", "markdown"],
        },
    },
    {
        "type": "function",
        "name": "listar_skills",
        "description": "Lista skills gravadas.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "ler_skill",
        "description": "Lê o conteúdo de uma skill pelo slug.",
        "parameters": {
            "type": "object",
            "properties": {"slug": {"type": "string"}},
            "required": ["slug"],
        },
    },
    {
        "type": "function",
        "name": "gravar_skill",
        "description": "Cria ou atualiza uma skill (SKILL.md).",
        "parameters": {
            "type": "object",
            "properties": {
                "nome": {"type": "string"},
                "descricao": {"type": "string"},
                "instrucoes": {"type": "string"},
            },
            "required": ["nome", "instrucoes"],
        },
    },
    {
        "type": "function",
        "name": "listar_documentos",
        "description": "Lista documentos já elaborados e gravados no chat.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def rewrite_command(text: str) -> str:
    raw = (text or "").strip()
    if raw.startswith("/pesquisar"):
        q = raw.split(None, 1)[1] if " " in raw else ""
        return f"Comando /pesquisar. Busque no acervo e explique os melhores resultados: {q}"
    if raw.startswith("/elaborar"):
        q = raw.split(None, 1)[1] if " " in raw else "documento jurídico"
        return (
            f"Comando /elaborar. Pesquise o acervo se preciso, elabore o documento e grave-o: {q}"
        )
    if raw.startswith("/skill"):
        q = raw.split(None, 1)[1] if " " in raw else ""
        return f"Comando /skill. Leia e aplique a skill '{q}' na tarefa atual, ou liste as skills se o nome estiver vazio."
    if raw.startswith("/gravar-skill"):
        q = raw.split(None, 1)[1] if " " in raw else ""
        return f"Comando /gravar-skill. Grave uma skill SKILL.md com estas instruções: {q}"
    if raw.startswith("/docs"):
        return "Comando /docs. Liste os documentos já gravados neste chat."
    return raw


def _exec(name: str, args: dict[str, Any], *, skill: str) -> str:
    if name == "buscar_acervo":
        hits = search_acervo(str(args.get("query") or ""), kind=str(args.get("kind") or "all"), limit=int(args.get("limit") or 8))
        return json.dumps(hits, ensure_ascii=False)
    if name == "ler_documento":
        doc = read_document(str(args.get("id") or ""))
        return json.dumps(doc or {"erro": "não encontrado"}, ensure_ascii=False)
    if name == "gravar_documento":
        rec = save_document(
            title=str(args.get("titulo") or "Documento"),
            kind=str(args.get("tipo") or "outro"),
            markdown=str(args.get("markdown") or ""),
            skill=skill,
        )
        return json.dumps(rec, ensure_ascii=False)
    if name == "listar_skills":
        return json.dumps(list_skills(), ensure_ascii=False)
    if name == "ler_skill":
        sk = read_skill(str(args.get("slug") or ""))
        return json.dumps(sk or {"erro": "skill inexistente"}, ensure_ascii=False)
    if name == "gravar_skill":
        sk = save_skill(str(args.get("nome") or ""), str(args.get("descricao") or ""), str(args.get("instrucoes") or ""))
        return json.dumps(sk, ensure_ascii=False)
    if name == "listar_documentos":
        return json.dumps(list_documents(30), ensure_ascii=False)
    return json.dumps({"erro": f"ferramenta desconhecida: {name}"})


def run_turn(
    messages: list[dict[str, str]],
    *,
    skill: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    seed_builtin_skills()
    chosen_skill = read_skill(skill) if skill else None
    extra = ""
    if chosen_skill:
        extra = (
            f"\n\nSkill ativa ({chosen_skill['slug']}): {chosen_skill['description']}\n\n"
            f"{chosen_skill['body']}"
        )
    history: list[dict[str, Any]] = []
    for msg in messages[-16:]:
        role = msg.get("role") or "user"
        content = str(msg.get("content") or "")
        if role == "user":
            content = rewrite_command(content)
        history.append({"role": role, "content": [{"type": "input_text" if role == "user" else "output_text", "text": content}]})

    used: list[str] = []
    saved_docs: list[dict[str, Any]] = []
    saved_skills: list[dict[str, Any]] = []

    for _ in range(12):
        data = create_response_turn(
            input_items=history,
            instructions=INSTRUCTIONS + extra,
            tools=TOOLS,
            model=model or DEFAULT_MODEL,
        )
        calls: list[dict[str, Any]] = []
        for item in data.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"reasoning", "message"}:
                history.append(item)
            if item.get("type") == "function_call":
                calls.append(item)
        if not calls:
            text = extract_output_text(data)
            return {
                "text": text or "Não consegui elaborar a resposta.",
                "tools": used,
                "documents": saved_docs,
                "skills": saved_skills,
            }
        for call in calls:
            history.append(call)
            raw_args = call.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {}
            name = str(call.get("name") or "")
            used.append(name)
            try:
                output = _exec(name, args if isinstance(args, dict) else {}, skill=skill or "")
                if name == "gravar_documento":
                    saved_docs.append(json.loads(output))
                if name == "gravar_skill":
                    saved_skills.append(json.loads(output))
            except Exception as exc:
                output = json.dumps({"erro": str(exc)}, ensure_ascii=False)
            history.append(
                {
                    "type": "function_call_output",
                    "call_id": call.get("call_id"),
                    "output": output[:20000],
                }
            )
    return {
        "text": "Atingi o limite de ferramentas nesta volta. Reformule o comando.",
        "tools": used,
        "documents": saved_docs,
        "skills": saved_skills,
    }
