# Guia tela a tela — Google AI Studio → Google Play

Siga na ordem. Arquivos prontos para copiar estão em `mobile/aistudio/`.

**Link:** https://aistudio.google.com/apps?source=start

---

## Tela 1 — Login Google

1. Abra o link acima no Chrome.
2. Entre com a **conta Google** que tem (ou terá) acesso ao **Play Console**.
3. Aceite os termos se aparecerem.

---

## Tela 2 — Apps / Build

1. Na barra lateral ou página inicial, clique em **Apps** (ou **Build**).
2. Clique em **Build an Android app** (ou **Create Android app** / **Build an Android app**).
3. Se pedir tipo de projeto, escolha **Android nativo** (Kotlin / Jetpack Compose).

---

## Tela 3 — Prompt inicial (campo de texto)

1. Clique no campo de prompt / descrição do app.
2. Abra o arquivo **`PROMPT-COPIAR.txt`** (mesma pasta deste guia).
3. Selecione **todo** o texto (Cmd+A) e copie (Cmd+C).
4. Cole no AI Studio (Cmd+V).
5. **Não envie ainda** — anexe o ícone primeiro (próxima tela).

> Atalho no Mac:
> ```bash
> open /Users/luizcarlos/Documents/GitHub/naintegra/mobile/aistudio/PROMPT-COPIAR.txt
> ```

---

## Tela 4 — Anexar ícone

1. Procure botão **Attach**, **Upload**, **+** ou ícone de clipe/imagem.
2. Anexe o arquivo:
   - `web/lex/icons/icon-512.png`
   - ou `mobile/dist/.../assets/icon-512.png` (dentro do ZIP exportado)
3. Confirme que a imagem apareceu no chat/anexo.

---

## Tela 5 — Gerar o app

1. Clique em **Generate**, **Build**, **Run** ou **Send** (seta).
2. Aguarde a geração (pode levar alguns minutos).
3. Não interrompa — o AI Studio cria o projeto Kotlin + Compose.

---

## Tela 6 — Preview / Emulador

1. Abra **Preview**, **Emulator** ou **Run on device**.
2. Verifique se o app abre em **https://www.naintegracursos.com.br/lex/**
3. Teste esta checklist:

| Teste | O que fazer | OK? |
|-------|-------------|-----|
| Início | Página Lex carrega com logo e menu | ☐ |
| Lei Seca | Toque no menu → abre leis | ☐ |
| Flashcards | Abre seção flashcards | ☐ |
| Login | Entrar → Google → volta logado | ☐ |
| Offline | Modo avião → tela "Sem conexão" | ☐ |

Se algo falhar, vá para **Tela 7**.

---

## Tela 7 — Refinar (chat de follow-up)

Copie **apenas** o bloco relevante de **`REFINAMENTOS-COPIAR.txt`** e envie no chat:

| Problema | Arquivo / bloco |
|----------|-----------------|
| Login quebrado | "Se login Google/Apple não voltar..." |
| Link abre Chrome | "Se links abrirem no Chrome..." |
| TTS não funciona | "Se TTS / Ouvir não funcionar..." |
| Tela branca | "Se tela branca..." |

Repita **Preview** após cada correção.

---

## Tela 8 — Conectar Play Console

1. Menu **Publish**, **Deploy** ou **Google Play**.
2. Clique em **Connect Google Play Console** / **Link Play Developer account**.
3. Autorize com a conta **Google Play Developer** (taxa US$ 25 se for primeira vez).
4. Confirme package name: **`br.com.naintegracursos.lex`**
   - Se já existir outro app com esse ID, o AI Studio avisará — use o ID só para o Lex.

---

## Tela 9 — Metadados da loja

Se o AI Studio pedir textos da ficha, abra **`PLAY-STORE-COPIAR.txt`** e cole:

| Campo | Valor |
|-------|--------|
| Título | NaIntegra Lex |
| Descrição curta | Lei seca, jurisprudência e flashcards... |
| Descrição completa | (texto longo no arquivo) |
| E-mail | contato@naintegracursos.com.br |
| Privacidade | https://www.naintegracursos.com.br/lex/#/contato |
| Categoria | Educação |

---

## Tela 10 — Internal Test Track

1. Escolha **Internal testing** (teste interno).
2. Clique em **Publish**, **Upload to Play** ou **Deploy to Internal track**.
3. Aguarde o upload do `.aab`.
4. No [Play Console](https://play.google.com/console):
   - **Testing → Internal testing**
   - Adicione e-mails dos testadores
   - Copie o **link opt-in** e envie para quem vai testar

---

## Tela 11 — Instalar no celular

1. Testador abre o link opt-in no Android.
2. Aceita ser testador.
3. Instala pela Play Store (versão internal).
4. Abra **NaIntegra Lex** e repita a checklist da Tela 6.

**Deep link (opcional):** com app instalado, teste abrir:
```
https://www.naintegracursos.com.br/lex/#/lei-seca
```
Deve abrir no app (asset links já configurados no site).

---

## Tela 12 — Após primeiro upload (Play App Signing)

Google pode usar certificado **diferente** do keystore local. Então:

1. Play Console → **Configuração** → **Integridade do app**
2. Copie **SHA-256** do **Certificado de assinatura do app**
3. No terminal (repo naintegra):

```bash
python3 mobile/scripts/update-assetlinks.py --add "COLE_SHA256_AQUI"
python3 scripts/sync_site_root_to_cursos.py --push
```

4. Reinstale o app e teste deep link de novo.

---

## Tela 13 — Produção

Quando Internal testing estiver OK:

1. Play Console → promover para **Produção** (ou Closed → Open → Production)
2. Preencha classificação de conteúdo e público-alvo
3. Envie capturas de tela (1080×1920, mín. 2)
4. Aguarde revisão Google (1–7 dias)

Checklist completa: `mobile/store-assets/play-console-checklist.md`

---

## Arquivos de apoio

| Arquivo | Uso |
|---------|-----|
| `PROMPT-COPIAR.txt` | Colar na Tela 3 |
| `PLAY-STORE-COPIAR.txt` | Colar na Tela 9 |
| `REFINAMENTOS-COPIAR.txt` | Colar na Tela 7 |
| `app-spec.json` | Referência técnica |
| `../dist/naintegra-lex-aistudio.zip` | Pacote completo |

## Comando para abrir tudo no Mac

```bash
open "https://aistudio.google.com/apps?source=start"
open mobile/aistudio/PROMPT-COPIAR.txt
open mobile/aistudio/PLAY-STORE-COPIAR.txt
open web/lex/icons/icon-512.png
```

---

**Package:** `br.com.naintegracursos.lex`  
**URL do app:** https://www.naintegracursos.com.br/lex/  
**Asset links:** https://www.naintegracursos.com.br/.well-known/assetlinks.json
