"""Pacote completo para postagem: copy Zamboni + slides + imagens."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from naintegra_meta.ai_providers import ProviderId, complete_text, parse_json_array, resolve_provider_settings
from naintegra_meta.carousel_renderer import render_slides_from_package
from naintegra_meta.content_sources import pick_flashcard_context
from naintegra_meta.image_providers import ImageProviderId, generate_image, list_image_provider_statuses
from naintegra_meta.marketing_library import build_marketing_context, get_package_system_prompt
from naintegra_meta.zamboni_style import EXPOSURE_RULES

REPO = Path(__file__).resolve().parents[2]
GENERATED_ROOT = REPO / "data" / "delegado" / "generated"

def _strip_to_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        items = parse_json_array(text)
        if items:
            data = items[0]
        else:
            raise
    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict):
        raise RuntimeError("IA não retornou objeto de pacote")
    return data


def _normalize_package(raw: dict[str, Any], *, tema: str, formato: str) -> dict[str, Any]:
    """Converte resposta estilo Marketing Digital para o schema do pacote NaIntegra."""

    out = dict(raw)
    if not out.get("titulo"):
        out["titulo"] = tema[:120]
    if not out.get("legenda") and out.get("caption"):
        out["legenda"] = str(out["caption"])
    if not out.get("gancho"):
        out["gancho"] = "Indo DIRETO ao ponto"
    if not out.get("formato_sugerido"):
        out["formato_sugerido"] = formato

    hashtags = out.get("hashtags")
    if isinstance(hashtags, str):
        out["hashtags"] = [t for t in hashtags.split() if t.startswith("#")]
    elif not isinstance(hashtags, list):
        out["hashtags"] = []

    norm_slides: list[dict[str, Any]] = []
    for i, slide in enumerate(out.get("slides") or [], start=1):
        if isinstance(slide, dict):
            if slide.get("text_content") is not None:
                txt = str(slide["text_content"])
                num = int(slide.get("slide_number") or i)
                norm_slides.append(
                    {
                        "numero": num,
                        "titulo": txt.split("\n", 1)[0][:80] or f"Slide {num}",
                        "corpo": txt,
                        "image_prompt": txt[:400],
                    }
                )
            else:
                slide.setdefault("numero", slide.get("numero") or i)
                norm_slides.append(slide)
        else:
            norm_slides.append(
                {"numero": i, "titulo": f"Slide {i}", "corpo": str(slide), "image_prompt": str(slide)[:400]}
            )
    if norm_slides:
        out["slides"] = norm_slides
    return out


def _rich_fallback(tema: str, formato: str, ctx: dict[str, str]) -> dict[str, Any]:
    macro = tema[:120]
    slides = [
        {
            "numero": i + 1,
            "titulo": t,
            "corpo": c,
            "destaque": macro[:60],
            "image_prompt": f"Legal education slide about {macro}, item {i+1}, dark gold theme",
        }
        for i, (t, c) in enumerate(
            [
                ("Capa", macro),
                ("Fato para a prova", "Cenário hipotético baseado no edital — sem pessoas reais."),
                ("Artigo-chave", (ctx.get("contexto") or "Revise CP/CPP no material NaIntegra.")[:300]),
                ("Pegadinha", "O que confunde 90% dos candidatos na hora da prova."),
                ("Jurisprudência", "Confira súmula/tema no seu cronograma Lex."),
                ("CTA", "Comente MATERIAL — PDF no inbox."),
            ]
        )
    ]
    legenda = "\n\n".join(
        [
            f"Indo DIRETO ao ponto: {macro}",
            "1) Contexto do tema no edital de delegado/concurso policial.",
            "2) Regra principal e por que ela cai.",
            "3) Exceção e pegadinha clássica.",
            "4) Como eu aplicaria na prática (didático, sem caso real).",
            "5) O que revisar hoje no NaIntegra Lex.",
            "Qual a sua opinião? Escreve nos comentários!",
            "Conteúdo educacional. Não representa posição institucional.",
            "Comente MATERIAL para receber o material.",
        ]
    )
    return {
        "titulo": macro,
        "gancho": "Indo DIRETO ao ponto",
        "texto_overlay": "[EXPLICAÇÃO NA LEGENDA]",
        "roteiro_falas": (
            f"Olá, sou o Delegado Luiz Carlos. Hoje: {macro}. "
            "Abra a legenda — deixei a análise numerada. Comente MATERIAL."
        ),
        "legenda": legenda,
        "hashtags": [
            "#direitopenal",
            "#concursopolicial",
            "#delegado",
            "#naintegra",
        ],
        "cta": "Comente MATERIAL",
        "formato_sugerido": formato,
        "slides": slides,
        "cover_image_prompt": f"Instagram cover legal education {macro}, dark and gold",
    }


def generate_content_package(
    *,
    tema: str,
    formato: str = "carrossel",
    text_provider: ProviderId | None = None,
    image_provider: ImageProviderId | None = None,
    discipline: str | None = None,
    generate_images: bool = True,
    use_ai_images: bool = True,
) -> dict[str, Any]:
    """Pacote com assets em data/delegado/generated/<id>/."""

    cfg = resolve_provider_settings()
    pid: ProviderId = text_provider or cfg["provider"]  # type: ignore[assignment]
    ctx = pick_flashcard_context(deck_slug=discipline)
    marketing = build_marketing_context()
    user_prompt = (
        f"Tema: {tema}\nFormato: {formato}\n"
        f"--- LEX ---\n{ctx['contexto'][:6000]}\n\n"
        f"--- MARKETING DIGITAL ---\n{marketing}\n"
    )
    source = "fallback"
    try:
        raw, used, model = complete_text(
            system=get_package_system_prompt(),
            user_prompt=user_prompt,
            provider=pid,
            cfg=cfg,
        )
        package = _normalize_package(_strip_to_object(raw), tema=tema, formato=formato)
        source = f"{used}:{model}"
    except Exception:
        package = _rich_fallback(tema, formato, ctx)

    pkg_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    out_dir = GENERATED_ROOT / pkg_id
    out_dir.mkdir(parents=True, exist_ok=True)

    assets: list[dict[str, Any]] = []
    if generate_images:
        if use_ai_images:
            cover_prompt = str(package.get("cover_image_prompt") or package.get("gancho") or tema)
            cover_path = out_dir / "00_cover_ai.png"
            try:
                path, ip, im = generate_image(
                    cover_prompt,
                    cover_path,
                    provider=image_provider,
                    slide_title=str(package.get("titulo") or tema)[:80],
                    slide_body=str(package.get("gancho") or "")[:200],
                )
                assets.append(
                    {
                        "path": str(path),
                        "url": f"/content/assets/{pkg_id}/00_cover_ai.png",
                        "kind": "cover",
                        "image_provider": ip,
                        "image_model": im,
                    }
                )
            except Exception as exc:
                package.setdefault("_warnings", []).append(f"capa IA: {exc}")

        slides = package.get("slides") or []
        if isinstance(slides, list):
            for slide in slides[:8]:
                if not isinstance(slide, dict):
                    continue
                num = int(slide.get("numero") or len(assets))
                prompt = str(slide.get("image_prompt") or slide.get("titulo") or tema)
                fname = f"{num:02d}_slide_ai.png"
                slide_path = out_dir / fname
                if use_ai_images:
                    try:
                        path, ip, im = generate_image(
                            prompt,
                            slide_path,
                            provider=image_provider,
                            slide_title=str(slide.get("titulo") or "")[:80],
                            slide_body=str(slide.get("corpo") or "")[:400],
                        )
                        assets.append(
                            {
                                "path": str(path),
                                "url": f"/content/assets/{pkg_id}/{fname}",
                                "kind": "slide",
                                "numero": num,
                                "image_provider": ip,
                            }
                        )
                        continue
                    except Exception:
                        pass

        pil_dir = out_dir / "pil"
        local_assets = render_slides_from_package(package, pil_dir, formato=formato)
        for la in local_assets:
            rel = Path(la["path"]).relative_to(out_dir).as_posix()
            if not any(a.get("path") == la["path"] for a in assets):
                assets.append(
                    {
                        **la,
                        "url": f"/content/assets/{pkg_id}/{rel}",
                        "image_provider": "pillow",
                    }
                )

    (out_dir / "package.json").write_text(
        json.dumps(package, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    hashtags = package.get("hashtags") or []
    if not isinstance(hashtags, list):
        hashtags = []
    legenda = str(package.get("legenda") or "")
    full_caption = "\n\n".join(
        p
        for p in [
            package.get("gancho"),
            legenda,
            " ".join(str(h) for h in hashtags),
            package.get("cta"),
        ]
        if p
    )

    return {
        "package_id": pkg_id,
        "titulo": package.get("titulo") or tema,
        "formato": package.get("formato_sugerido") or formato,
        "legenda": full_caption,
        "hashtags": hashtags,
        "status": "aguardando_aprovacao",
        "text_source": source,
        "image_providers": [s.__dict__ for s in list_image_provider_statuses()],
        "assets": assets,
        "meta": {
            "package": package,
            "deck_slug": ctx["deck_slug"],
            "requires_manual_publish": True,
            "roteiro_falas": package.get("roteiro_falas"),
            "texto_overlay": package.get("texto_overlay"),
            "slides": package.get("slides"),
            "marketing_context_chars": len(marketing),
        },
    }


def compare_all_providers(tema: str, formato: str = "carrossel") -> dict[str, Any]:
    """Texto por provedor (preview) + status de imagem."""

    from naintegra_meta.ai_providers import compare_providers

    cfg = resolve_provider_settings()
    marketing = build_marketing_context()[:2000]
    user_prompt = f"Tema: {tema}\nFormato: {formato}\nMarketing:\n{marketing}\nGere o objeto JSON do pacote."
    text_results = compare_providers(
        system=get_package_system_prompt(),
        user_prompt=user_prompt,
        providers=("ollama", "anthropic", "openai", "gemini", "grok", "groq", "openrouter"),
    )
    return {
        "text": text_results,
        "image_providers": [s.__dict__ for s in list_image_provider_statuses()],
    }
