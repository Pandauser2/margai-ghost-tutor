#!/usr/bin/env bash
# Push env vars from .env to Vercel (production + preview).
# Run from margai-ghost-tutor-pilot: ./scripts/push_env_to_vercel.sh
# Requires: Vercel CLI logged in (npx vercel login).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PILOT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PILOT_ROOT/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing .env at $ENV_FILE. Create it from .env.example and fill in values." >&2
  exit 1
fi

# Vars we push to Vercel (same as RUN.md).
VARS=(SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY PINECONE_API_KEY PINECONE_INDEX_NAME GEMINI_API_KEY TELEGRAM_BOT_TOKEN INSTITUTE_ID_DEFAULT TELEGRAM_WEBHOOK_SECRET)

cd "$PILOT_ROOT"
for name in "${VARS[@]}"; do
  value=$(grep -E "^${name}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")
  if [ -z "$value" ]; then
    echo "Skip $name (empty or not set in .env)"
    continue
  fi
  tmp=$(mktemp)
  printf '%s' "$value" > "$tmp"
  echo "Adding $name to Vercel (production + preview)..."
  vercel env add "$name" production < "$tmp" 2>/dev/null || true
  printf '%s' "$value" > "$tmp"
  vercel env add "$name" preview < "$tmp" 2>/dev/null || true
  rm -f "$tmp"
done
echo "Done. Redeploy so the new env vars are used: npx vercel --prod"
echo "Or in dashboard: Deployments → … → Redeploy."
