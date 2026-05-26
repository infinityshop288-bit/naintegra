# Publicar NaIntegra Lex — ações manuais (5 min)

Automação concluiu **AAB v1.0.1 (versionCode 2)** e **archive iOS**. Falta confirmar na Play (países + testadores + implantar) e exportar iOS no Xcode.

Conta Play: **Arnold Scott** (`5476168127224845991`)

## Google Play — teste fechado (obrigatório)

Abra nesta ordem (logado como `infinity.shop288@gmail.com`):

1. **Países** — marque **Brasil** → Salvar  
   https://play.google.com/console/u/0/developers/5476168127224845991/app/br.com.naintegracursos.lex/tracks/closed-testing/countries

2. **Testadores** — lista `NaIntegra Lex testers` com e-mails Google:
   - `infinity.shop288@gmail.com`
   - `contato@naintegracursos.com.br`
   - `teste.naintegra.lex@gmail.com`
   → Salvar  
   https://play.google.com/console/u/0/developers/5476168127224845991/app/br.com.naintegracursos.lex/tracks/closed-testing/testers

   Automação:

   ```bash
   cd mobile && npm run play:setup-test-access
   ```

3. **Versão 2** — Revisar → **Iniciar implantação para teste fechado**  
   https://play.google.com/console/u/0/developers/5476168127224845991/app/br.com.naintegracursos.lex/tracks/closed-testing

4. **Enviar para revisão** — Painel de publicação → **Enviar alterações para revisão** → Confirmar  
   https://play.google.com/console/u/0/developers/5476168127224845991/app/br.com.naintegracursos.lex/publishing/overview

   Credenciais revisor (Acesso ao app — Google Play e Apple):

   | Campo | Valor |
   |-------|--------|
   | E-mail | `teste.naintegra.lex@gmail.com` |
   | Senha | `NaIntegraLex2026!` |

   Assinatura Lex **ativa** no Supabase até 2027-05-26.

   Automação rápida (só teste fechado + revisão):

   ```bash
   cd mobile && npm run play:complete-review:fast
   ```

AAB local (se precisar reenviar):  
`~/Documents/NaIntegra-Lex-GooglePlay/naintegra-lex-release-v1.0.1-offline.aab`

### Automatizar de vez (recomendado)

Play Console → **Configurações** → **Acesso à API** → criar service account → baixar JSON para:

`mobile/android/play-service-account.json`

Depois:

```bash
cd mobile
npm run publish:play:api -- --track alpha --countries BR --testers "seu@gmail.com"
```

(`alpha` = teste fechado na API)

---

## App Store — iOS

Archive já gerado: `mobile/dist/App.xcarchive`

1. Abrir Xcode: `cd mobile && npm run ios`
2. **Window → Organizer** → selecionar archive **App**
3. **Distribute App** → App Store Connect → Upload  
   (conta Apple Developer paga + Team **D7323783Z5**)

Se export falhar: Xcode → **Settings → Accounts** → `infinity.shop288@gmail.com` → **Download Manual Profiles**

---

## Aviso ProGuard

Pode **ignorar** — o app não usa R8/ofuscação.
