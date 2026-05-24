# Google Play via Google AI Studio

Publicação do **NaIntegra Lex** na Google Play usando [Google AI Studio → Apps](https://aistudio.google.com/apps?source=start) (recurso anunciado no Google I/O 2026: build Android nativo + emulador no browser + upload para **Internal Test Track**).

| Campo | Valor |
|-------|--------|
| **AI Studio** | https://aistudio.google.com/apps?source=start |
| **Package** | `br.com.naintegracursos.lex` |
| **URL do app** | `https://www.naintegracursos.com.br/lex/` |
| **Versão** | 1.0.0 (versionCode 1) |

---

## Por que AI Studio para o Lex?

O Lex já é um app web completo (Lei Seca, flashcards, OAuth, TTS). O app Android pode ser um **shell WebView** que carrega a URL de produção — atualizações de conteúdo sem republicar na loja.

O AI Studio permite:
- Gerar o projeto Kotlin/Jetpack Compose a partir de um prompt
- Testar no **emulador no browser** ou no celular via **ADB**
- Conectar a **conta Play Developer** e enviar ao **Internal Test Track** com um clique
- Exportar ZIP para Android Studio se precisar de ajustes manuais

---

## 1. Preparar pacote de exportação

Na raiz do repositório:

```bash
bash mobile/scripts/export-for-aistudio.sh
```

Gera `mobile/dist/naintegra-lex-aistudio.zip` com:
- `PROMPT.md` — prompt pronto para colar
- `app-spec.json` — metadados (package, URLs, Play Store)
- `play-store.md` — textos da ficha
- `icon-512.png` — ícone da loja
- `capacitor-android.zip` — projeto Capacitor alternativo (handoff)

---

## 2. Criar o app no AI Studio

1. Acesse [aistudio.google.com/apps](https://aistudio.google.com/apps?source=start) e faça login.
2. Clique em **Build an Android app** (ou equivalente na aba Build).
3. Cole o prompt de `mobile/aistudio/PROMPT.md` (ou extraia do ZIP).
4. Anexe o ícone `icon-512.png` se a UI permitir.
5. Aguarde a geração do código Kotlin + Compose.

### Refinar (se necessário)

Peça ajustes em linguagem natural, por exemplo:
- “Garanta que o WebView mantém cookies para login Supabase”
- “Adicione pull-to-refresh na WebView”
- “Use minSdk 24 e targetSdk 34”

---

## 3. Testar

| Método | Como |
|--------|------|
| Emulador browser | Botão Preview / Emulator no AI Studio |
| Celular físico | ADB: conectar USB, instalar APK/AAB de debug |
| Checklist funcional | Login Google, Lei Seca, flashcards, TTS, deep link `/lex` |

Smoke test automatizado (web + assets):

```bash
python3 mobile/scripts/smoke-mobile-apps.py
```

---

## 4. Conectar Google Play Console

1. No AI Studio, vá em **Publish** / **Connect Play Console** (nome pode variar).
2. Autorize com a conta **Google Play Developer** (taxa única US$ 25).
3. Confirme package name: `br.com.naintegracursos.lex` (deve ser único na sua conta).

Metadados da ficha (se o AI Studio não preencher tudo):

| Campo | Valor |
|-------|--------|
| Título | NaIntegra Lex |
| Descrição curta | Lei seca, jurisprudência e flashcards… |
| Categoria | Educação |
| E-mail | contato@naintegracursos.com.br |
| Privacidade | https://www.naintegracursos.com.br/lex/#/contato |

Textos completos: `mobile/store-assets/play-store.md`

---

## 5. Publicar no Internal Test Track

1. No AI Studio: **Publish to Internal testing** (ou similar).
2. O AI Studio cria o registro do app, gera o `.aab` e faz upload.
3. No [Play Console](https://play.google.com/console): **Testing → Internal testing** → adicionar testadores (e-mails).
4. Testadores instalam via link opt-in.

Depois de validar:
- **Closed testing** → **Open testing** → **Production**

---

## 6. App Links (deep links HTTPS)

Para links `https://www.naintegracursos.com.br/lex/...` abrirem o app:

1. Play Console → **App integrity** → copie SHA-256 do certificado de assinatura.
2. Publique em `https://www.naintegracursos.com.br/.well-known/assetlinks.json` (já no ar; falta só o SHA-256):

```bash
python3 mobile/scripts/update-assetlinks.py --add "SEU_SHA256_PLAY_CONSOLE"
python3 scripts/sync_site_root_to_cursos.py --push
```

3. Confirme `android:autoVerify="true"` no intent-filter HTTPS (já configurado no Capacitor; peça ao AI Studio o mesmo).

---

## 7. Alternativa: Capacitor (sem IA)

Se o build do AI Studio não atender, use o projeto Capacitor já no repo:

```bash
bash mobile/scripts/prepare-native-projects.sh
# Instalar Android Studio + JDK 17
cd mobile && npm run android
# Build → Generate Signed Bundle / APK → .aab
```

O ZIP `capacitor-android.zip` do export é o mesmo projeto, para importar no Android Studio.

---

## 7. OAuth

**Recomendado:** app carrega `https://www.naintegracursos.com.br/lex/` — OAuth já funciona no site. Nenhuma alteração no Supabase.

Detalhes: `mobile/store-assets/oauth-mobile.md`

---

## Links

- [Google AI Studio Apps](https://aistudio.google.com/apps?source=start)
- [Google Play Console](https://play.google.com/console)
- [Blog Android — Build apps in AI Studio](https://android-developers.googleblog.com/2026/05/build-android-apps-google-ai-studio.html)
- Export geral: `mobile/EXPORT-LOJAS.md`
