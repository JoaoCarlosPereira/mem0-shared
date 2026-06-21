#!/bin/sh
set -e

cd /app

# Replace NEXT_PUBLIC_* placeholders baked at build time (see .env.example).
# Use ${line#*=} so values may contain "="; skip empty values (keep /api-proxy default).
printenv | grep '^NEXT_PUBLIC_' | while IFS= read -r line; do
  key="${line%%=*}"
  value="${line#*=}"
  if [ -n "$value" ] && [ "$value" != "$key" ]; then
    find .next/ -type f -exec sed -i "s|${key}|${value}|g" {} +
  fi
done
echo "Done replacing env variables NEXT_PUBLIC_ with real values"

exec "$@"
