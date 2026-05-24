# Checklist — Google Play Console (NaIntegra Lex)

Use após gerar o app no [Google AI Studio](https://aistudio.google.com/apps?source=start) ou o `.aab` local.

## Antes do upload

- [ ] Package name: `br.com.naintegracursos.lex`
- [ ] Versão: 1.0.0 (versionCode 1)
- [ ] `assetlinks.json` publicado com SHA-256
- [ ] Smoke test: `python3 mobile/scripts/smoke-mobile-apps.py`

## Ficha da loja

Textos prontos em `mobile/store-assets/play-store.md`:

- [ ] Título: **NaIntegra Lex**
- [ ] Descrição curta e completa
- [ ] Ícone 512×512 (`web/lex/icons/icon-512.png`)
- [ ] Feature graphic 1024×500
- [ ] Capturas 1080×1920 (mín. 2)
- [ ] Categoria: **Educação**
- [ ] E-mail: contato@naintegracursos.com.br
- [ ] Política de privacidade: https://www.naintegracursos.com.br/lex/#/contato

## Internal testing

- [ ] Upload `.aab` (AI Studio ou `mobile/dist/naintegra-lex-release.aab`)
- [ ] Adicionar testadores (e-mails)
- [ ] Instalar via link opt-in
- [ ] Testar: login Google, Lei Seca, flashcards, TTS
- [ ] Testar deep link: `https://www.naintegracursos.com.br/lex/#/lei-seca`

## Após Play App Signing

- [ ] Play Console → Integridade do app → copiar SHA-256 **Certificado de assinatura do app**
- [ ] `python3 mobile/scripts/update-assetlinks.py --add "SHA256"`
- [ ] `python3 scripts/sync_site_root_to_cursos.py --push`
- [ ] Re-testar deep link no dispositivo

## Promover para produção

- [ ] Closed testing → Open testing (opcional)
- [ ] Production → revisão Google
- [ ] Classificação de conteúdo preenchida
- [ ] Declaração de público-alvo (13+ / educação)
