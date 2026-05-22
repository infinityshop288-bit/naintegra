# Deploy NaIntegra Lex → naintegracursos.com.br/lex

Repositório de **produção** (site + Hostinger):  
**https://github.com/infinityshop288-bit/naintegracursos**

O app Lex fica em **`public/lex/`** — o Vite copia para `dist/lex/` no build.

Repositório de **desenvolvimento** (agente + pipeline):  
**https://github.com/infinityshop288-bit/naintegra** (`web/lex/`)

## Fluxo recomendado

1. Desenvolva em `naintegra/web/lex/`
2. Push em `naintegra` → workflow **Sync Lex → naintegracursos** atualiza `public/lex/`
3. Push em `naintegracursos` → Hostinger/Lovable publica o site (inclui `/lex`)

Sync manual local:

```bash
python3 scripts/sync_lex_to_cursos.py --push
```

## Opção A — GitHub Actions (automático a cada push)

1. No **hPanel** → **Sites** → **naintegracursos.com.br** → **Arquivos** → anote **FTP host**, **usuário** e **senha**.
2. Localmente:

```bash
cp .env.deploy.example .env.deploy
# edite .env.deploy com FTP_SERVER, FTP_USERNAME, FTP_PASSWORD

python3 scripts/setup_github_deploy_secrets.py --from-env .env.deploy
```

3. No GitHub: **Actions** → **Deploy Lex (Hostinger)** → **Run workflow** (ou faça push em `main`).
4. Verifique: https://www.naintegracursos.com.br/lex/index.html

### Secrets usados

| Secret | Obrigatório (FTP) | Exemplo |
|--------|-------------------|---------|
| `FTP_SERVER` | sim | `ftp.naintegracursos.com.br` |
| `FTP_USERNAME` | sim | usuário do hPanel |
| `FTP_PASSWORD` | sim | senha FTP |
| `FTP_REMOTE_DIR` | não | `./public_html/lex/` |
| `FTP_PORT` | não | `21` |

Alternativa **SSH** (planos com SSH): `SSH_HOST`, `SSH_USERNAME`, `SSH_PRIVATE_KEY`, `SSH_REMOTE_DIR`.

## Opção B — hPanel Git (recomendado)

1. hPanel → **Websites** → **naintegracursos.com.br** → **Git**
2. Repositório: **`infinityshop288-bit/naintegracursos`**
3. Branch: **`main`**
4. Build (se disponível): `npm ci && npm run build`
5. Diretório de deploy: **`public_html`** (saída `dist/` do Vite inclui `lex/`)
6. Clique **Deploy** e ative **Auto Deployment**

O Lex já está em `public/lex/` no repositório — após o build, fica em `/lex` no site.

## Opção C — FTP direto (só o Lex)

```bash
bash scripts/publish_lex_static.sh
rsync -av lex/ USUARIO@ftp.naintegracursos.com.br:public_html/lex/
```
