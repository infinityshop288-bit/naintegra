#!/usr/bin/env python3
"""Gera carrossel Lei Henry Borel — fundo branco, texto preto."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from naintegra_meta.carousel_renderer import render_slides_from_package

TEMA = (
    "Lei Henry Borel (Lei 14.344/2022): violência doméstica contra crianças, "
    "agravantes, medidas protetivas e impacto em provas de Direito Penal"
)

PACKAGE = {
    "titulo": "Lei Henry Borel — o que cai na prova",
    "gancho": "Indo DIRETO ao ponto",
    "texto_overlay": "[EXPLICAÇÃO NA LEGENDA]",
    "roteiro_falas": (
        "Olá! A Lei Henry Borel mudou o jogo na proteção de crianças e adolescentes "
        "em contexto de violência doméstica. Abra a legenda: deixei os pontos que a banca "
        "mais cobra. Comente MATERIAL se quiser o PDF."
    ),
    "legenda": (
        "Indo DIRETO ao ponto: a Lei 14.344/2022 — conhecida como Lei Henry Borel.\n\n"
        "1) Contexto: após o assassinato do menino Henry Borel (4 anos), o Congresso "
        "alterou o CP, a Lei Maria da Penha e normas correlatas para reforçar a proteção "
        "de crianças e adolescentes em violência doméstica e familiar.\n\n"
        "2) Violência doméstica contra a criança: o art. 121-A do CP tipifica homicídio "
        "qualificado em contexto de violência doméstica; a lei reforça agravantes e a "
        "atuação integrada com medidas protetivas.\n\n"
        "3) Agravante do art. 121, §2º-A, I: crime praticado contra menor de 14 anos — "
        "pegadinha clássica: não confundir com outras qualificadoras do homicídio.\n\n"
        "4) Medidas protetivas de urgência (Lei 11.340/2006, art. 22-A): podem ser "
        "aplicadas também em favor da criança/adolescente, inclusive afastamento do agressor.\n\n"
        "5) Para a prova: revise CP + Lei Maria da Penha + ECA; jurisprudência recente "
        "do STJ sobre aplicação imediata das alterações.\n\n"
        "Qual a sua opinião? A lei endureceu o suficiente? Escreve nos comentários!\n\n"
        "Conteúdo educacional. Caso ilustrativo com base em notícia pública. "
        "Não representa posição institucional da PF.\n\n"
        "Comente MATERIAL para receber material NaIntegra no inbox."
    ),
    "hashtags": [
        "#leihenryborel",
        "#direitopenal",
        "#violenciadomestica",
        "#concursopolicial",
        "#delegado",
        "#naintegra",
        "#estudecomquemvive",
    ],
    "cta": "Comente MATERIAL — PDF NaIntegra no inbox.",
    "formato_sugerido": "carrossel",
    "slides": [
        {
            "numero": 1,
            "titulo": "Lei Henry Borel",
            "corpo": "Lei 14.344/2022 — proteção de crianças em violência doméstica",
        },
        {
            "numero": 2,
            "titulo": "Por que existe?",
            "corpo": "Reação ao caso Henry Borel: reforço penal e medidas protetivas",
        },
        {
            "numero": 3,
            "titulo": "CP — homicídio",
            "corpo": "Art. 121-A e agravantes: atenção a menor de 14 anos (§2º-A, I)",
        },
        {
            "numero": 4,
            "titulo": "Lei Maria da Penha",
            "corpo": "Art. 22-A: medidas protetivas de urgência também para criança/adolescente",
        },
        {
            "numero": 5,
            "titulo": "Pegadinha de prova",
            "corpo": "Não misture qualificadoras do art. 121 — leia o tipo especializado",
        },
        {
            "numero": 6,
            "titulo": "O que revisar hoje",
            "corpo": "CP + Lei 11.340/2006 + ECA + súmulas STJ recentes",
        },
    ],
}


def main() -> int:
    pkg_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_henryborel"
    out_dir = REPO / "data" / "delegado" / "generated" / pkg_id
    slides_dir = out_dir / "slides_branco"
    assets = render_slides_from_package(
        PACKAGE,
        slides_dir,
        formato="carrossel",
        slide_style="minimal_white",
    )

    preview_html = out_dir / "preview.html"
    imgs = sorted(slides_dir.glob("*.png"))
    img_tags = "\n".join(
        f'<figure><img src="slides_branco/{p.name}" alt="{p.stem}"/><figcaption>{p.stem}</figcaption></figure>'
        for p in imgs
    )
    preview_html.write_text(
        f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"/>
<title>Lei Henry Borel — @delegadoluizcarlos</title>
<style>
body{{font-family:system-ui;max-width:900px;margin:2rem auto;padding:0 1rem;background:#f5f5f5}}
h1{{color:#111}} .legenda{{white-space:pre-wrap;background:#fff;padding:1rem;border:1px solid #ddd}}
.grid{{display:grid;gap:1rem}} img{{width:100%;max-width:540px;border:1px solid #ccc;background:#fff}}
figure{{margin:0}} figcaption{{font-size:0.85rem;color:#444}}
</style></head><body>
<h1>Lei Henry Borel — carrossel (fundo branco)</h1>
<p><strong>Pacote:</strong> {pkg_id}</p>
<div class="legenda">{PACKAGE["legenda"]}</div>
<h2>Slides</h2>
<div class="grid">{img_tags}</div>
</body></html>""",
        encoding="utf-8",
    )

    (out_dir / "package.json").write_text(
        json.dumps(PACKAGE, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    manifest = {
        "package_id": pkg_id,
        "tema": TEMA,
        "slide_style": "minimal_white",
        "assets": assets,
        "preview_html": str(preview_html),
        "legenda": PACKAGE["legenda"],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(pkg_id)
    print(preview_html)
    for a in assets:
        print(a["path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
