# Upload via AI Studio — faça em 2 minutos

**Eu não consigo clicar no AI Studio pela sua conta Google.**  
Só você pode autorizar o login e o botão Publish. Siga exatamente:

---

## Passo 1 — Abrir (já preparado)

```bash
cd mobile && npm run aistudio:go
```

Isso copia o **prompt** (Cmd+V) e abre o AI Studio.

Link direto: https://aistudio.google.com/apps?source=start

---

## Passo 2 — Gerar o app (1 min)

| # | Clique / ação |
|---|----------------|
| 1 | Login Google (conta do **Play Console**) |
| 2 | **Apps** ou aba **Build** |
| 3 | **Build an Android app** |
| 4 | Campo de texto → **Cmd+V** (prompt já no clipboard) |
| 5 | **Anexar** → escolher `web/lex/icons/icon-512.png` |
| 6 | **Generate** / **Build** / enviar (seta) |
| 7 | Aguardar terminar (2–5 min) |

---

## Passo 3 — Testar (30 s)

| # | Ação |
|---|------|
| 1 | **Preview** ou **Emulator** |
| 2 | Confirmar que abre `naintegracursos.com.br/lex` |

Se der erro → cole no chat um bloco de `REFINAMENTOS-COPIAR.txt`.

---

## Passo 4 — Upload Internal Test (1 min)

| # | Clique / ação |
|---|----------------|
| 1 | **Publish** ou **Deploy** (menu lateral ou topo) |
| 2 | **Connect Google Play Console** → autorizar conta developer |
| 3 | Confirmar package: `br.com.naintegracursos.lex` |
| 4 | Escolher **Internal testing** |
| 5 | **Publish to Play** / **Upload** / **Deploy** (botão principal) |
| 6 | Aguardar “Upload complete” |

---

## Passo 5 — Depois do upload

Play Console → **Integridade do app** → copie **SHA-256** do certificado de assinatura:

```bash
bash mobile/scripts/add-play-sha256.sh "SEU_SHA256"
```

---

## Por que não dá para eu fazer sozinho?

- AI Studio exige **login Google OAuth** no navegador
- Não existe API pública para “Build + Publish” em nome do usuário
- Tentamos gerar `.aab` localmente, mas falta **Android SDK** (só AI Studio ou Android Studio instalam)

---

## Alternativa sem AI Studio

1. Instalar [Android Studio](https://developer.android.com/studio)
2. `cd mobile && npm run build:aab`
3. Play Console → **Internal testing** → upload manual do `.aab`

---

**Package:** `br.com.naintegracursos.lex`  
**Prompt:** `mobile/aistudio/PROMPT-COPIAR.txt`  
**Capturas/banner:** `mobile/store-assets/generated/`
