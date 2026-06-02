#!/usr/bin/env bash
# Expõe schema delegado na Data API do Supabase (PostgREST).
#
# Uso (Management API — preferido):
#   export SUPABASE_ACCESS_TOKEN="..."  # https://supabase.com/dashboard/account/tokens
#   bash scripts/configure_delegado_supabase.sh
#
# Alternativa: migration SQL já aplica ALTER ROLE authenticator (feito via MCP).

set -euo pipefail

PROJECT_REF="${SUPABASE_PROJECT_REF:-voybsggeedpwcfdadnzt}"
API="https://api.supabase.com/v1/projects/${PROJECT_REF}/postgrest"

if [[ -n "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  echo "→ Lendo config PostgREST atual…"
  current="$(curl -fsS "$API" -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}")"
  current_schema="$(echo "$current" | python3 -c "import sys,json; print(json.load(sys.stdin).get('db_schema',''))")"
  echo "   db_schema atual: $current_schema"

  merge_schemas() {
    python3 - "$current_schema" delegado <<'PY'
import sys
existing = [x.strip() for x in sys.argv[1].split(",") if x.strip()]
required = [x.strip() for x in sys.argv[2:] if x.strip()]
seen = set()
merged = []
for item in existing + required:
    if item not in seen:
        seen.add(item)
        merged.append(item)
print(", ".join(merged))
PY
  }

  new_schema="$(merge_schemas)"
  if [[ "$new_schema" == "$current_schema" ]]; then
    echo "Schema delegado já exposto via Management API."
    exit 0
  fi

  payload="$(python3 -c "import json; print(json.dumps({'db_schema': '''$new_schema'''}))")"
  echo "→ Atualizando db_schema → $new_schema"
  curl -fsS -X PATCH "$API" \
    -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$payload"
  echo ""
  echo "✓ PostgREST atualizado."
else
  echo "SUPABASE_ACCESS_TOKEN não definido."
  echo "Schema delegado pode ser exposto via SQL (ALTER ROLE authenticator) — veja sql/delegado_social_dashboard.sql"
  echo "Ou defina o token e rode este script novamente."
fi
