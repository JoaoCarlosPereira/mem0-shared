#!/bin/sh
set -e

cd /app

# Replace NEXT_PUBLIC_* placeholders baked at build time (see .env.example).
# Use ${line#*=} so values may contain "="; skip empty values (keep /api-proxy default).
#
# NEVER sed bare identifiers into .js — e.g. s|NEXT_PUBLIC_AUTH_UI_REQUIRED|0|
# turns `process.env.NEXT_PUBLIC_AUTH_UI_REQUIRED` into invalid syntax `process.env.0`
# and the App Router returns 500 on every page. Only rewrite quoted string literals.
#
# NEVER sed URL values as bare keys either (NEXT_PUBLIC_API_URL / MCP_URL): those
# are resolved at runtime via api-url.ts (/api-proxy + /discovery).
printenv | grep '^NEXT_PUBLIC_' | while IFS= read -r line; do
  key="${line%%=*}"
  value="${line#*=}"
  case "$key" in
    NEXT_PUBLIC_API_URL|NEXT_PUBLIC_MCP_URL) continue ;;
  esac
  if [ -z "$value" ] || [ "$value" = "$key" ]; then
    continue
  fi
  case "$value" in
    *://*)
      echo "WARN: skip sed for ${key} (URL values break server bundles)"
      continue
      ;;
  esac
  # Escape sed replacement metacharacters (& \ | and newlines).
  esc=$(printf '%s' "$value" | sed -e 's/[&\\|]/\\&/g' -e 's|/|\\/|g')
  find .next/ -type f \( -name '*.js' -o -name '*.json' \) -exec \
    sed -i \
      -e "s|\"${key}\"|\"${esc}\"|g" \
      -e "s|'${key}'|'${esc}'|g" \
    {} +
done
echo "Done replacing env variables NEXT_PUBLIC_ with real values"

exec "$@"
