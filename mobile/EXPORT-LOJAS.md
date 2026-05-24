# Exportar NaIntegra Lex para Google Play e App Store

Este diretório gera os projetos nativos **Android** (Android Studio) e **iOS** (Xcode) a partir do app web em `web/lex/`, usando [Capacitor](https://capacitorjs.com/).

| Item | Valor |
|------|--------|
| **App ID (bundle)** | `br.com.naintegracursos.lex` |
| **Nome na loja** | NaIntegra Lex |
| **Conteúdo web** | `web/lex/` → copiado para `mobile/www/` |

---

## 1. Pré-requisitos

### Todos
- **Node.js 20+** e npm
- Conta **Google Play Console** (Android) e/ou **Apple Developer** (iOS)

### Android (Google Play)
- [Android Studio](https://developer.android.com/studio) (Ladybug ou mais recente)
- Android SDK (API 34+ recomendado)
- JDK 17

### iOS (App Store) — somente macOS
- [Xcode](https://developer.apple.com/xcode/) 15+
- Conta Apple Developer Program (US$ 99/ano)
- CocoaPods via Bundler (no diretório `mobile/`):

```bash
cd mobile
bundle install --path vendor/bundle
export RUBYOPT="-rlogger"   # necessário no Ruby 2.6 do macOS
bundle exec pod --version
```

---

## 2. Gerar projetos para exportar

Na raiz do repositório:

```bash
bash mobile/scripts/prepare-native-projects.sh
```

Ou, passo a passo:

```bash
cd mobile
npm install
npm run sync          # web/lex → www
npx cap add android   # primeira vez
npx cap add ios       # primeira vez (macOS)
npx cap sync          # copia www + plugins
```

Isso cria/atualiza:

| Pasta | Abrir em |
|-------|----------|
| `mobile/android/` | **Android Studio** |
| `mobile/ios/` | **Xcode** |

---

## 3. Google Play — via Google AI Studio (recomendado)

Pipeline completo (um comando):

```bash
cd mobile && npm run publish:play
```

Ou passo a passo:
1. **Exportar pacote:** `bash mobile/scripts/export-for-aistudio.sh`
2. Abrir [Google AI Studio → Apps](https://aistudio.google.com/apps?source=start)
3. **Build an Android app** → colar prompt de `mobile/aistudio/PROMPT.md`
4. Testar → conectar **Play Console** → **Internal testing**

Checklist Play Console: `store-assets/play-console-checklist.md`

---

## 3b. Google Play — via Android Studio (alternativa)

```bash
cd mobile
npm run android
```

No Android Studio:

1. **Build → Generate Signed Bundle / APK**
2. Escolha **Android App Bundle (.aab)** — obrigatório para Play Store
3. Crie ou use um **keystore** (guarde backup e senhas)
4. Build variant: **release**
5. O `.aab` fica em `android/app/build/outputs/bundle/release/`

### Play Console
1. [Google Play Console](https://play.google.com/console) → Criar app
2. **Produção** → **Criar nova versão** → enviar o `.aab`
3. Preencha ficha da loja (textos em `store-assets/play-store.md`)
4. Política de privacidade: URL do site (ex.: `https://www.naintegracursos.com.br/lex/#/contato`)
5. Classificação de conteúdo, público-alvo, capturas de tela

### versionCode / versionName
Edite `android/app/build.gradle`:

```gradle
defaultConfig {
    applicationId "br.com.naintegracursos.lex"
    versionCode 1
    versionName "1.0.0"
}
```

Incremente `versionCode` a cada upload na Play Store.

---

## 4. Abrir no Xcode (App Store)

```bash
cd mobile
npm run ios
```

No Xcode:

1. Selecione o target **App**
2. **Signing & Capabilities** → Team (Apple Developer)
3. Bundle Identifier: `br.com.naintegracursos.lex`
4. **Product → Archive**
5. **Distribute App** → **App Store Connect** → Upload

### App Store Connect
1. [App Store Connect](https://appstoreconnect.apple.com/) → Novo app
2. SKU e bundle ID iguais ao configurado
3. Metadados em `store-assets/app-store.md`
4. Capturas: iPhone 6,7" e 6,5" (obrigatório)

### Versão iOS
Em Xcode → General → **Version** (1.0.0) e **Build** (1).

---

## 5. Modo site remoto (opcional)

Para o app carregar sempre a versão online (sem republicar a cada atualização do Lex):

```bash
export LEX_MOBILE_SERVER_URL=https://www.naintegracursos.com.br/lex/
cd mobile && npm run build
```

O `capacitor.config.ts` usa essa URL como `server.url`. Útil para correções rápidas; a loja ainda exige revisão para mudanças nativas.

---

## 6. Login OAuth (Supabase)

O Lex usa OAuth (Google etc.). Para o app nativo:

1. No **Supabase** → Authentication → URL Configuration, adicione:
   - `br.com.naintegracursos.lex://auth-callback`
   - `capacitor://localhost` (modo empacotado)
2. Configure **Deep Links** / **Universal Links** nos projetos nativos (Android intent-filter, iOS Associated Domains) se usar callback customizado.
3. Alternativa simples: use `LEX_MOBILE_SERVER_URL` apontando para o site em produção (OAuth já configurado para `/lex/auth-callback.html`).

Detalhes: `store-assets/oauth-mobile.md`

---

## 7. Atualizar o app após mudanças no Lex

```bash
# Desenvolveu em web/lex
bash mobile/scripts/prepare-native-projects.sh
# ou: cd mobile && npm run build

# Depois gere novo .aab / Archive no Studio ou Xcode
```

---

## 8. Estrutura

```
mobile/
├── android/          → projeto Android Studio (gerado)
├── ios/              → projeto Xcode (gerado)
├── www/              → cópia de web/lex (gerado)
├── capacitor.config.ts
├── package.json
├── scripts/
│   ├── sync-lex-www.sh
│   └── prepare-native-projects.sh
└── store-assets/     → textos e checklist das lojas
```

---

## 9. Solução de problemas

| Problema | Ação |
|----------|------|
| `cap add ios` falha fora do Mac | Gere iOS em macOS ou CI macOS |
| Tela branca no app | Rode `npm run sync && npx cap sync`; confira `www/index.html` |
| CORS / API | Supabase anon key já está em `config.js`; app precisa de internet |
| Play rejeita WebView puro | Descreva funcionalidades (leitura offline parcial via cache, TTS, flashcards) |

Suporte: `contato@naintegracursos.com.br`
