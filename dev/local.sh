#!/usr/bin/env bash
# The whole backend on this machine, for testing the dashboard and the Clep plugin end to end:
#   the Worker API (wrangler dev, :8799, Neon dev branch) + a render worker running reels, motion and clep jobs.
#
#   bash dev/local.sh            # first run sets up dev/venv (Python + Chromium), then starts both
#
# The renderer runs here, so the app you clip can be on localhost. Engine keys come from vm/.env. Ctrl-C stops both.
# Never touches production: the database is api/.dev.vars' Neon dev branch, video storage is wrangler's local R2,
# and the worker takes jobs from the local API only (JOB_SOURCE=api), never from the Cloudflare queue.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/dev/venv"
PORT="${PORT:-8799}"
var() { grep "^$1=" "$ROOT/api/.dev.vars" | head -1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }

[ -f "$ROOT/api/.dev.vars" ] || { echo "api/.dev.vars is missing (ADMIN_KEY, INTERNAL_KEY, DATABASE_URL of the dev branch)"; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is needed: brew install ffmpeg"; exit 1; }

if [ ! -x "$VENV/bin/python" ]; then
  echo "· setting up dev/venv (once)"
  PY="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$PY" -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/playwright" install chromium
fi
"$VENV/bin/pip" install -q -r "$ROOT/engines/reels/requirements.txt" -r "$ROOT/engines/motion/requirements.txt" \
  -r "$ROOT/engines/clep/requirements.txt" -r "$ROOT/vm/requirements.txt"

if [[ "$(var DATABASE_URL)" == *@db.localtest.me* ]]; then
  echo "· database: local Postgres in Docker"
  docker compose -f "$ROOT/dev/docker-compose.yml" up -d --wait
fi

echo "· database: applying migrations"
(cd "$ROOT/api" && DATABASE_URL="$(var DATABASE_URL)" DATABASE_URL_UNPOOLED= node scripts/migrate.mjs)

echo "· API: wrangler dev on :$PORT"
(cd "$ROOT/api" && exec npx wrangler dev --port "$PORT" --ip 127.0.0.1 --var "API_URL:http://127.0.0.1:$PORT" >"$ROOT/dev/wrangler.log" 2>&1) &
API_PID=$!
trap 'kill $API_PID 2>/dev/null; wait $API_PID 2>/dev/null' EXIT
for _ in $(seq 60); do
  curl -sf "http://127.0.0.1:$PORT/health" >/dev/null && break
  kill -0 $API_PID 2>/dev/null || { echo "wrangler dev exited — see dev/wrangler.log"; exit 1; }
  sleep 1
done
curl -sf "http://127.0.0.1:$PORT/health" >/dev/null || { echo "API did not come up — see dev/wrangler.log"; exit 1; }

cat <<EOF

  Backend is up: http://127.0.0.1:$PORT   (API log: dev/wrangler.log)

  An access code to sign in (once):  node api/scripts/dev-signin.mjs you@example.com
  Dashboard:  cd ~/clep && npm run dev:local   → sign in, then API Keys → Create key

  Point your agent at it:  export CLEP_API_URL=http://127.0.0.1:$PORT CLEP_API_KEY=<the key you created>

  Render worker log follows. Ctrl-C stops everything.

EOF

cd "$ROOT/vm"
JOB_SOURCE=api API_URL="http://127.0.0.1:$PORT" INTERNAL_KEY="$(var INTERNAL_KEY)" \
REELS_PYTHON="$VENV/bin/python" MOTION_PYTHON="$VENV/bin/python" CLEP_PYTHON="$VENV/bin/python" RENDER_WORKERS="${RENDER_WORKERS:-2}" IDLE_EXIT_MINUTES=0 \
  "$VENV/bin/python" main.py
