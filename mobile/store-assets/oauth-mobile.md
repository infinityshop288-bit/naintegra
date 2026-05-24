# OAuth no app móvel (Supabase)

O Lex web usa redirect para `https://www.naintegracursos.com.br/lex/auth-callback.html`.

## Opção A — App carrega site em produção (recomendado para v1)

Configure no build:

```bash
export LEX_MOBILE_SERVER_URL=https://www.naintegracursos.com.br/lex/
cd mobile && npm run build
```

O login usa as mesmas URLs já cadastradas no Supabase. Nenhuma alteração extra no OAuth.

## Opção B — App empacotado (www local)

1. Supabase → **Authentication** → **URL Configuration**
2. Adicione em **Redirect URLs**:
   - `https://localhost/auth-callback`
   - `capacitor://localhost/auth-callback`
   - `br.com.naintegracursos.lex://auth-callback`
3. Ajuste `web/lex/js/config.js` (ou variável de build) para `oauthCallbackUrl` compatível com o scheme do app.
4. Android: `AndroidManifest.xml` — intent-filter para o scheme customizado.
5. iOS: URL Types no Xcode com scheme `br.com.naintegracursos.lex`.

Para produção na loja, a **Opção A** reduz risco de rejeição por fluxo de login quebrado.
