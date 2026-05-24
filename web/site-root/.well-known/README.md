# Digital Asset Links — NaIntegra Lex (Android)

Arquivo publicado em:

`https://www.naintegracursos.com.br/.well-known/assetlinks.json`

## Atualizar SHA-256 (após primeiro upload na Play Console)

1. [Play Console](https://play.google.com/console) → **NaIntegra Lex** → **Configuração** → **Integridade do app**
2. Copie **SHA-256** do **Certificado de assinatura do app** (e do upload key se diferente)
3. No repo naintegra:

```bash
python3 mobile/scripts/update-assetlinks.py --add "AA:BB:CC:..."
python3 scripts/sync_site_root_to_cursos.py --push
```

Ou a partir de keystore local:

```bash
bash mobile/scripts/generate-release-keystore.sh   # primeira vez
python3 mobile/scripts/update-assetlinks.py --from-keystore mobile/android/release.keystore
python3 scripts/sync_site_root_to_cursos.py --push
```

## Validar

```bash
curl -s https://www.naintegracursos.com.br/.well-known/assetlinks.json | python3 -m json.tool
```

[Google Statement List Tester](https://developers.google.com/digital-asset-links/tools/generator)

## Teste no dispositivo

```bash
adb shell am start -a android.intent.action.VIEW \
  -d "https://www.naintegracursos.com.br/lex/#/lei-seca"
```

Deve abrir o app (não o Chrome) quando fingerprints estiverem corretos.
