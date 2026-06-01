# Dashboard @delegadoluizcarlos — Meta / Instagram

Gestão automatizada de conteúdo, publicação e monitoramento para **@delegadoluizcarlos**, com acesso restrito a `infinity.shop288@gmail.com`.

## Componentes

| Camada | Caminho | Função |
|--------|---------|--------|
| Frontend | `web/delegado/` | Dashboard (7 abas), auth Supabase |
| API | `src/naintegra_meta/` | FastAPI + Graph API + Claude |
| Banco | `sql/delegado_social_dashboard.sql` | Fila, automações, snapshots (schema `delegado`) |

## Abas do dashboard

1. **Visão Geral** — KPIs (seguidores, engajamento, alcance, leads) + posicionamento no nicho
2. **Conteúdo (IA)** — Claude gera 3 ideias (gancho, legenda, hashtags, CTA)
3. **Publicação** — fila/calendário + publicação direta via Graph API
4. **Anúncios** — campanhas Meta Ads (gasto, CTR, impressões)
5. **Monitoramento** — gráfico de métricas + comentários por post
6. **Concorrentes** — benchmark do nicho (dados maio/2026)
7. **Automações** — 12 hipóteses de marketing automatizado (ativar/pausar)

## Setup local

```bash
# Dependências Python
pip install -e ".[meta]"

# Variáveis (.env na raiz do repo)
META_ACCESS_TOKEN=...        # Page Access Token long-lived (IG/FB)
META_AD_ACCOUNT_ID=act_...   # Conta de anúncios
IG_USER_ID=...               # Instagram Business ID
FB_PAGE_ID=...               # Página Facebook vinculada
ANTHROPIC_API_KEY=...        # Geração de ideias
SUPABASE_URL=https://voybsggeedpwcfdadnzt.supabase.co
SUPABASE_ANON_KEY=...
DELEGADO_ALLOWED_EMAILS=infinity.shop288@gmail.com

# API (porta 8787)
naintegra-delegado-api

# Frontend estático (porta 8765)
python preview/serve_preview.py --open none
# Abrir http://127.0.0.1:8765/web/delegado/
```

## Supabase

1. Executar `sql/delegado_social_dashboard.sql` no SQL Editor
2. **Settings → API → Exposed schemas** → adicionar `delegado`
3. Criar usuário `infinity.shop288@gmail.com` em Authentication (senha forte)
4. Adicionar redirect URLs:
   - `https://www.naintegracursos.com.br/delegado/auth-callback.html`
   - `http://127.0.0.1:8765/web/delegado/auth-callback.html`

## Railway (produção)

- Serviço 1: `naintegra-delegado-api` com variáveis Meta + Supabase + Anthropic
- Serviço 2 ou Hostinger: servir `web/delegado/` em `/delegado/`
- Atualizar `apiBaseUrl` em `web/delegado/js/config.js` para URL da API no Railway

## Segurança — token Meta

Se um token foi exposto em chat, **revogue e regenere** em [developers.facebook.com](https://developers.facebook.com). Rode `debug_token` na aba Visão Geral após configurar.

## n8n (opcional)

Fluxos complementares já previstos nas automações: webhooks de comentários, RSS jurídico, crosspost YouTube, Evolution API (WhatsApp). Conecte os nós HTTP à API FastAPI ou diretamente à Graph API.

## Métricas Meta (jun/2026)

A Meta migra `reach`/`impressions` → `views`/`viewers`. O cliente já consulta `views` como fallback; confira `API_VERSION` em `meta_client.py` (atual: v23.0).
