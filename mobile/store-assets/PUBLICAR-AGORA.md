# Publicar NaIntegra Lex — app gratuito (v1.1.0)

O app passou a ser **gratuito e sem login obrigatório**. Assinatura, checkout Mercado Pago e
In-App Purchase da Apple foram removidos do código. Detalhes da mudança e da resposta à
rejeição da Apple: [`APP-STORE-REJECTION-FIXES.md`](./APP-STORE-REJECTION-FIXES.md).

| Item | Valor |
|------|-------|
| Package / Bundle ID | `br.com.naintegracursos.lex` |
| Android | versionName **1.1.0** · versionCode **4** |
| iOS | MARKETING_VERSION **1.1.0** · build **6** |
| Conta Play | Arnold Scott (`5476168127224845991`) |
| App Store Connect | adamId `6778567767` · Team `D7323783Z5` |

## Pré-requisito: publicar o site

O app carrega o conteúdo de `https://www.naintegracursos.com.br/lex/`. **Enquanto o site não
for atualizado, o app instalado continua mostrando o paywall antigo** — e a revisão das lojas
reprovaria de novo.

```bash
python3 scripts/deploy_lex_hostinger.py --source lex
```

Requer `FTP_USERNAME` e `FTP_PASSWORD` preenchidos em `.env.deploy`
(Hostinger → hPanel → Sites → Arquivos → Detalhes FTP).

Validar depois:

```bash
curl -s https://www.naintegracursos.com.br/lex/js/config.js | grep -c subscriptionPlans   # deve ser 0
curl -s -o /dev/null -w '%{http_code}\n' https://www.naintegracursos.com.br/lex/privacidade.html  # deve ser 200
```

## Gerar os binários

```bash
cd mobile
npm run build:aab      # → dist/naintegra-lex-release.aab
npm run archive:ios    # → dist/App.xcarchive
```

## Google Play

1. **Monetização** — App **gratuito**, sem compras no app, sem anúncios.
2. **Acesso ao app** — marcar *"Todas as funcionalidades estão disponíveis sem restrições"*.
   Não é mais necessário fornecer conta de teste ao revisor.
3. **Ficha da loja** — textos em [`play-store.md`](./play-store.md).
   Capturas: `store-assets/generated/phone/` (regenerar com `npm run play:screenshots`).
4. **Enviar a versão** e depois **Enviar alterações para revisão** no painel de publicação.

Automação:

```bash
cd mobile
npm run publish:play:api -- --track production --countries BR   # requer android/play-service-account.json
# ou, via navegador:
npm run play:complete-review
```

## App Store

1. **Remover os IAPs** `lex_mensal` / `lex_anual` da versão (não enviar para revisão).
2. **Informações para revisão** — desmarcar *"Sign-in required"*.
3. **Preço** — Grátis.
4. **Política de privacidade** — `https://www.naintegracursos.com.br/lex/privacidade.html`
5. **Rótulos de privacidade** — sem dados financeiros; ver [`app-store.md`](./app-store.md).
6. Vincular a compilação **1.1.0 (6)** e reenviar para revisão.

Automação:

```bash
cd mobile
npm run appstore:publish          # archive + upload + submit
npm run appstore:complete-review  # completa a ficha via navegador
```

## Notas da versão

`store-assets/release-notes-pt-BR.txt`
