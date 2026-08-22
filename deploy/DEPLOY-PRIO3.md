# Deploy do dashboard PRIO3 em /xxx/

URL: **https://www.naintegracursos.com.br/xxx/painel.html**

> O domínio correto é `naintegracursos.com.br` (com “gra”). A hospedagem é a mesma do Lex (`/lex/`).

## O que é publicado

| Página | Arquivo |
|--------|---------|
| Painel PRIO3 | `painel.html` |
| Panorama de Mercado | `mercado.html` |
| Oportunidades de Opções | `opcoes.html` |
| Radar de Trades | `radar.html` |

Na Hostinger (hospedagem compartilhada) o painel roda como **site estático** + snapshots JSON das APIs (`api/live.json`, etc.), atualizados pelo GitHub Actions a cada 15 min ou manualmente.

## Autenticação

Login HTTP Basic (Apache):

- **Usuário:** `infinity.shop288@gmail.com`
- **Senha:** definida em `DASHBOARD_PASSWORD` (nunca commitar)

## GitHub Actions (recomendado)

Fluxo igual ao Lex: push em **naintegra** → workflow **Sync Dashboard PRIO3 → naintegracursos** → push em `public/xxx/` → Hostinger publica em `/xxx/`.

### Secrets (GitHub → naintegra → Settings → Secrets)

| Secret | Obrigatório | Valor |
|--------|-------------|-------|
| `DASHBOARD_USER` | sim | `infinity.shop288@gmail.com` |
| `DASHBOARD_PASSWORD` | sim | senha de acesso ao dashboard |
| `HTPASSWD_ABS_PATH` | não | caminho absoluto do `.htpasswd` no Hostinger |

Configure localmente:

```bash
python3 scripts/setup_github_deploy_secrets.py --from-env .env.deploy
```

Dispare: **Actions** → **Sync Dashboard PRIO3 → naintegracursos** → **Run workflow**.

## Deploy manual (local)

1. Copie credenciais:

   ```bash
   cp .env.deploy.example .env.deploy
   ```

2. Preencha em `.env.deploy`:

   - `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD` (hPanel → FTP)
   - `DASHBOARD_PASSWORD` (senha de acesso ao dashboard)
   - Opcional: `HTPASSWD_ABS_PATH` — caminho absoluto no servidor, ex.  
     `/home/u123456789/domains/naintegracursos.com.br/public_html/xxx/.htpasswd`

3. Build + envio:

   ```bash
   python3 scripts/build_prio3_deploy.py --refresh
   python3 scripts/deploy_prio3_hostinger.py --skip-build
   ```

   Ou em um comando:

   ```bash
   python3 scripts/deploy_prio3_hostinger.py --refresh
   ```

## GitHub Actions

Workflow: `.github/workflows/deploy-prio3-dashboard.yml`

Secrets necessários (além dos FTP já usados pelo Lex):

| Secret | Descrição |
|--------|-----------|
| `DASHBOARD_USER` | `infinity.shop288@gmail.com` |
| `DASHBOARD_PASSWORD` | Senha do dashboard |
| `HTPASSWD_ABS_PATH` | (opcional) caminho absoluto do `.htpasswd` no Hostinger |

## Desenvolvimento local

Com APIs ao vivo:

```bash
cd data/prio3_analysis
.venv/bin/python live_server.py
# http://localhost:8899/painel.html
```

## Limitações na internet

- Cotações “ao vivo” são **snapshots** (atualizados no deploy/cron), não streaming em tempo real.
- Para tempo real contínuo seria necessário VPS com `live_server.py` + nginx.
