#!/usr/bin/env bash
# Adiciona URLs do NaIntegra Lex/Cursos ao Supabase Auth (projeto compartilhado com VoltGo).
#
# Sem isso, OAuth Google/Apple cai no Site URL do VoltGo quando redirectTo não está na allow list.
#
# Uso:
#   export SUPABASE_ACCESS_TOKEN="..."   # https://supabase.com/dashboard/account/tokens
#   bash scripts/configure_supabase_auth_urls.sh
#
# Opcional: manter Site URL do VoltGo (padrão) e só ampliar Redirect URLs.

set -euo pipefail

PROJECT_REF="${SUPABASE_PROJECT_REF:-voybsggeedpwcfdadnzt}"
API="https://api.supabase.com/v1/projects/${PROJECT_REF}/config/auth"

NAINTEGRA_REDIRECTS=(
  "https://www.naintegracursos.com.br/lex/auth-callback.html"
  "https://naintegracursos.com.br/lex/auth-callback.html"
  "https://www.naintegracursos.com.br/lex/**"
  "https://naintegracursos.com.br/lex/**"
  "https://www.naintegracursos.com.br/delegado/auth-callback.html"
  "https://naintegracursos.com.br/delegado/auth-callback.html"
  "https://www.naintegracursos.com.br/delegado/**"
  "https://naintegracursos.com.br/delegado/**"
  "https://www.naintegracursos.com.br/auth"
  "https://www.naintegracursos.com.br/reset-password"
  "https://www.naintegracursos.com.br/**"
)

if [[ -z "${SUPABASE_ACCESS_TOKEN:-}" ]]; then
  echo "Defina SUPABASE_ACCESS_TOKEN (Dashboard → Account → Access Tokens)." >&2
  exit 1
fi

echo "→ Lendo config auth atual…"
current_json="$(curl -fsS "$API" -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}")"
current_list="$(echo "$current_json" | jq -r '.uri_allow_list // ""')"

merge_list() {
  python3 - "$current_list" "${NAINTEGRA_REDIRECTS[@]}" <<'PY'
import sys
existing = [x.strip() for x in sys.argv[1].split(",") if x.strip()]
required = [x.strip() for x in sys.argv[2:] if x.strip()]
seen = set()
merged = []
for item in existing + required:
    if item not in seen:
        seen.add(item)
        merged.append(item)
print(",".join(merged))
PY
}

new_list="$(merge_list)"
if [[ "$new_list" == "$current_list" ]]; then
  echo "Redirect URLs do NaIntegra já presentes. Nada a alterar."
  exit 0
fi

payload="$(jq -n --arg list "$new_list" '{ uri_allow_list: $list }')"

echo "→ Atualizando uri_allow_list…"
curl -fsS -X PATCH "$API" \
  -H "Authorization: Bearer ${SUPABASE_ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$payload" >/dev/null

echo "OK. Redirect URLs atualizadas (VoltGo preservado)."
echo "Teste login Google em https://www.naintegracursos.com.br/lex/#/auth/login"
