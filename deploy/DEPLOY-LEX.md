# Deploy NaIntegra Lex → naintegracursos.com.br/lex

Hospedagem: **Hostinger** (`platform: hostinger`).

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

## Opção B — hPanel Git (sem Actions)

1. hPanel → **Websites** → **Git** → conectar `infinityshop288-bit/naintegra`.
2. Branch: `main`.
3. Comando de build: `bash scripts/publish_lex_static.sh`
4. Diretório de saída / deploy: conteúdo de `lex/` → `public_html/lex/`

## Deploy manual (uma vez)

```bash
bash scripts/publish_lex_static.sh
rsync -av lex/ USUARIO@ftp.naintegracursos.com.br:public_html/lex/
```
