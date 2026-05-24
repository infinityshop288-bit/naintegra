# Prompt — Google AI Studio (Build an Android app)

**URL:** [aistudio.google.com/apps](https://aistudio.google.com/apps?source=start) → **Build an Android app**

Anexe também: `assets/icon-512.png` (do ZIP `npm run export:aistudio`)

---

## Prompt principal (copiar tudo)

```
Build a production-ready Android app in Kotlin + Jetpack Compose for "NaIntegra Lex" — a legal study companion for Brazilian public security exam candidates.

APP IDENTITY
- app name: NaIntegra Lex
- applicationId: br.com.naintegracursos.lex
- versionName: 1.0.0
- versionCode: 1
- minSdk: 24, targetSdk: 34, compileSdk: 34
- language: Portuguese (Brazil) for all user-facing strings

ARCHITECTURE
Single-activity app with one full-screen WebView as the main UI. The app is a trusted shell around the production web app — do NOT rebuild the legal content UI natively.

START URL (always use this in release):
https://www.naintegracursos.com.br/lex/

WEBVIEW REQUIREMENTS
- Enable JavaScript, DOM storage, database storage, cache mode LOAD_DEFAULT
- Accept third-party cookies if needed for Supabase auth
- Keep navigation inside WebView for:
  - same host www.naintegracursos.com.br
  - hash routes (#/, #/lei-seca, #/flashcards, #/jurisprudencia, #/questoes, #/contato, #/auth)
- Open in external browser: mailto:, tel:, whatsapp:, and any other domain
- Handle onReceivedError / onReceivedHttpError with retry
- Pull-to-refresh on the WebView
- Preserve WebView state on rotation (or lock portrait if simpler)
- setSupportMultipleWindows(false) unless OAuth popup requires a WebViewClient popup handler

SPLASH & THEME
- windowBackground / splash: #faf8f4
- primary brand color: #9a6e00
- Show centered app icon on splash for 1.5s then fade to WebView
- Light status bar icons on #faf8f4 background (dark icons)

OFFLINE
If no network on launch or after error:
- Show Compose screen in Portuguese:
  Title: "Sem conexão"
  Body: "Conecte-se à internet para usar o NaIntegra Lex."
  Button: "Tentar novamente" → reload WebView

DEEP LINKS — implement exactly:

1) Android App Links (autoVerify=true):
   https://www.naintegracursos.com.br/lex
   https://www.naintegracursos.com.br/lex/
   https://www.naintegracursos.com.br/lex/*
   → open MainActivity and load the full URL in WebView

2) Custom scheme:
   br.com.naintegracursos.lex://
   → same behavior

Manifest intent-filters example host/path:
  android:scheme="https"
  android:host="www.naintegracursos.com.br"
  android:pathPrefix="/lex"

OAUTH (do not break)
Login uses production Supabase OAuth on the website. Do NOT implement custom native OAuth.
Callback URL already works on web:
https://www.naintegracursos.com.br/lex/auth-callback.html
Ensure WebView allows redirect flow back into the app.

PERMISSIONS (only these)
- android.permission.INTERNET
- android.permission.ACCESS_NETWORK_STATE

SECURITY
- usesCleartextTraffic=false
- no unnecessary permissions (camera, location, etc.)

PLAY STORE METADATA (for auto app record creation)
- category: Education
- contact email: contato@naintegracursos.com.br
- privacy policy: https://www.naintegracursos.com.br/lex/#/contato

Short description (80 chars max):
Lei seca, jurisprudência e flashcards para concursos de segurança pública.

Full description:
NaIntegra Lex é o companion oficial para estudo de legislação e jurisprudência focado em concursos de segurança pública.

• Lei seca — leitura artigo por artigo, com progresso e busca por tema
• Jurisprudência — súmulas, temas e julgados dos principais tribunais
• Flashcards — revisão espaçada
• Questões — banco integrado ao NaIntegra Cursos
• Ouvir — narração por voz dos dispositivos legais
• Anotações e grifos — salvas no dispositivo

Requer assinatura NaIntegra Lex para acesso ao acervo completo.
Desenvolvido por NaIntegra Cursos.

DELIVERABLES
- Complete Android Studio project structure
- Signed-ready release build.gradle
- Android App Bundle (.aab) configuration
- README with Play Internal Test Track publish steps
```

---

## Prompts de refinamento (se algo falhar nos testes)

**Login OAuth não volta ao app:**
```
Fix OAuth redirect handling in WebView. Allow navigation to auth-callback.html on www.naintegracursos.com.br and preserve session cookies after Google sign-in.
```

**Links abrem no Chrome em vez do app:**
```
Ensure intent-filter android:autoVerify="true" for https://www.naintegracursos.com.br/lex with pathPrefix /lex. MainActivity launchMode singleTask.
```

**TTS / áudio não funciona:**
```
Ensure WebView JavaScript enabled and no media playback restriction. Do not block speechSynthesis API.
```

**Pull-to-refresh:**
```
Add SwipeRefreshLayout wrapping WebView (or Compose equivalent). Only enable when WebView scrollY == 0.
```

---

## Após publicar no Internal Test Track

1. Play Console → **Integridade do app** → copie **SHA-256** do certificado de assinatura
2. No repo:
   ```bash
   python3 mobile/scripts/update-assetlinks.py --add "SEU_SHA256"
   python3 scripts/sync_site_root_to_cursos.py --push
   ```
3. Confirme: https://www.naintegracursos.com.br/.well-known/assetlinks.json
4. Teste deep link: `adb shell am start -a android.intent.action.VIEW -d "https://www.naintegracursos.com.br/lex/#/lei-seca"`

---

## Export alternativo (Capacitor)

```bash
bash mobile/scripts/export-for-aistudio.sh
```
