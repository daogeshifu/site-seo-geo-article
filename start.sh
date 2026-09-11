#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-${PROJECT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
REQUIREMENTS_FILE="${PROJECT_DIR}/requirements.txt"
REQUIREMENTS_STAMP="${VENV_DIR}/.requirements.sha256"

cd "${PROJECT_DIR}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo ">>> Error: ${PYTHON_BIN} was not found. Install Python 3.10+ first." >&2
  exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo ">>> Error: Python 3.10 or newer is required." >&2
  exit 1
fi

if [ ! -x "${VENV_DIR}/bin/python" ]; then
  echo ">>> Creating virtual environment: ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

REQUIREMENTS_HASH="$(python -c 'import hashlib, pathlib, sys; print(hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes()).hexdigest())' "${REQUIREMENTS_FILE}")"
INSTALLED_HASH="$(cat "${REQUIREMENTS_STAMP}" 2>/dev/null || true)"
if [ "${REQUIREMENTS_HASH}" != "${INSTALLED_HASH}" ] || ! python -m pip check >/dev/null 2>&1; then
  echo ">>> Installing Python dependencies..."
  python -m pip install -r "${REQUIREMENTS_FILE}"
  printf '%s\n' "${REQUIREMENTS_HASH}" > "${REQUIREMENTS_STAMP}"
else
  echo ">>> Python dependencies are up to date."
fi

if [ -f "${ENV_FILE}" ]; then
  echo ">>> Loading ${ENV_FILE}"
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
else
  echo ">>> .env not found; using development defaults."
  echo ">>> Tip: cp .env.example .env"
fi

HOST="${FLASK_HOST:-0.0.0.0}"
PORT="${FLASK_PORT:-8028}"
DEBUG_FLAG="${FLASK_DEBUG:-true}"

if ! [[ "${PORT}" =~ ^[0-9]+$ ]] || [ "${PORT}" -lt 1 ] || [ "${PORT}" -gt 65535 ]; then
  echo ">>> Error: FLASK_PORT must be an integer between 1 and 65535." >&2
  exit 1
fi

if ! python - "${HOST}" "${PORT}" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    try:
        sock.bind((sys.argv[1], int(sys.argv[2])))
    except OSError:
        raise SystemExit(1)
PY
then
  echo ">>> Error: port ${PORT} is already in use." >&2
  echo ">>> Stop the existing process or set another port in .env, for example FLASK_PORT=8029." >&2
  exit 1
fi

UVICORN_ARGS=(app.main:app --host "${HOST}" --port "${PORT}")
if [[ "${DEBUG_FLAG}" =~ ^([Tt][Rr][Uu][Ee]|1|[Yy][Ee][Ss])$ ]]; then
  UVICORN_ARGS+=(--reload)
  RUN_MODE="development (auto-reload)"
else
  RUN_MODE="local (no auto-reload)"
fi

echo
echo "=========================================="
echo "  SEO / GEO Article Writer"
echo "  Home: http://127.0.0.1:${PORT}/"
echo "  API:  http://127.0.0.1:${PORT}/docs"
echo "  Mode: ${RUN_MODE}"
echo "  Stop: Ctrl+C"
echo "=========================================="
echo

exec python -m uvicorn "${UVICORN_ARGS[@]}"
