#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo ">>> No virtualenv found, creating .venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo ">>> Installing dependencies..."
python -m pip install -q -r requirements.txt

if [ -f ".env" ]; then
  echo ">>> Loading .env ..."
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

HOST="${FLASK_HOST:-0.0.0.0}"
PORT="${FLASK_PORT:-8028}"
DEBUG_FLAG="${FLASK_DEBUG:-true}"
IS_PROD="${IS_PROD:-N}"
AUTO_KILL_PORT="${AUTO_KILL_PORT:-N}"

find_free_port() {
  local port="$1"
  while lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; do
    port=$((port + 1))
  done
  echo "$port"
}

CURRENT_PIDS="$(lsof -ti :"${PORT}" 2>/dev/null || true)"
if [ -n "${CURRENT_PIDS:-}" ]; then
  if [ -t 0 ]; then
    echo ">>> Port ${PORT} is already in use by PID(s): ${CURRENT_PIDS}"
    read -r -p ">>> Close the existing process and keep using port ${PORT}? [y/N] " CLOSE_PORT || true
  else
    CLOSE_PORT="${AUTO_KILL_PORT:-N}"
    echo ">>> Port ${PORT} is already in use by PID(s): ${CURRENT_PIDS}"
    echo ">>> Non-interactive shell detected, using AUTO_KILL_PORT=${CLOSE_PORT}"
  fi

  if [[ "${CLOSE_PORT:-N}" =~ ^[Yy]$ ]]; then
    echo ">>> Killing processes using port ${PORT}: ${CURRENT_PIDS}"
    echo "${CURRENT_PIDS}" | xargs kill -9
    sleep 1
  else
    NEXT_PORT="$(find_free_port "$PORT")"
    echo ">>> Switching to available port ${NEXT_PORT} instead."
    PORT="${NEXT_PORT}"
  fi
fi

if [ -t 0 ]; then
  read -r -p ">>> Start in background mode? [y/N] " IS_PROD_INPUT || true
  if [[ "${IS_PROD_INPUT:-N}" =~ ^[Yy]$ ]]; then
    IS_PROD="Y"
  else
    IS_PROD="N"
  fi
else
  echo ">>> Non-interactive shell detected, using IS_PROD=${IS_PROD}"
fi

echo ""
echo "=========================================="
echo "  SEO / GEO Article Writer starting..."
echo "  URL:        http://127.0.0.1:${PORT}"
echo "  Demo:       http://127.0.0.1:${PORT}/"
echo "  Docs:       http://127.0.0.1:${PORT}/docs"
echo "  Mode:       $( [ "${DEBUG_FLAG}" = "true" ] && echo "debug" || echo "normal" )"
echo "  LLM mode:   $( [ -n "${OPENAI_API_KEY:-}" ] && [ "${LLM_MOCK_MODE:-true}" != "true" ] && echo "live" || echo "mock" )"
if [[ "${IS_PROD}" =~ ^[Yy]$ ]]; then
  echo "  Runtime:    background"
  echo "  Stop:       kill \$(cat server.pid)"
else
  echo "  Runtime:    foreground"
fi
echo "=========================================="
echo ""

if [[ "${IS_PROD}" =~ ^[Yy]$ ]]; then
  nohup python -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" > nohup.out 2>&1 &
  echo $! > server.pid
  echo ">>> Server started in background, PID: $(cat server.pid)"
else
  if [ "${DEBUG_FLAG}" = "true" ]; then
    exec python -m uvicorn app.main:app --reload --host "${HOST}" --port "${PORT}"
  else
    exec python -m uvicorn app.main:app --host "${HOST}" --port "${PORT}"
  fi
fi
