#!/bin/sh
set -e

cd /app

# Replace NEXT_PUBLIC_* placeholders baked at build time (see .env.example).
# Use ${line#*=} so values may contain "="; skip empty values (keep /api-proxy default).
#
# NEVER sed URL values into .js — e.g. s|NEXT_PUBLIC_MCP_URL|http://192.168.x.x:8765|
# turns `process.env.NEXT_PUBLIC_MCP_URL` into invalid syntax `process.env.http://...`
# and the App Router returns 500 on every page.
printenv | grep '^NEXT_PUBLIC_' | while IFS= read -r line; do
  key="${line%%=*}"
  value="${line#*=}"
  # Runtime env is read via process.env in Node; browser API/MCP URLs use api-url.ts
  # (/api-proxy + /discovery). Do not rewrite bundles for these keys.
  case "$key" in
    NEXT_PUBLIC_API_URL|NEXT_PUBLIC_MCP_URL) continue ;;
  esac
  if [ -n "$value" ] && [ "$value" != "$key" ]; then
    case "$value" in
      *://*)
        echo "WARN: skip sed for ${key} (URL values break server bundles)"
        continue
        ;;
    esac
    find .next/ -type f \( -name '*.js' -o -name '*.json' \) -exec sed -i "s|${key}|${value}|g" {} +
  fi
done
echo "Done replacing env variables NEXT_PUBLIC_ with real values"

exec "$@"
