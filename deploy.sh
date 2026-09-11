#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env.docker}"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.yml"
ACTION="${1:-deploy}"

usage() {
  cat <<'EOF'
Usage: ./deploy.sh [command]

Commands:
  deploy   Validate config, build images, and start services (default)
  status   Show service status
  logs     Follow application logs
  restart  Restart the application container
  stop     Stop and remove containers (persistent data is kept)
  help     Show this help

Environment:
  ENV_FILE=/path/to/.env.docker  Use another Docker environment file
EOF
}

if [ "${ACTION}" = "help" ] || [ "${ACTION}" = "--help" ] || [ "${ACTION}" = "-h" ]; then
  usage
  exit 0
fi

case "${ACTION}" in
  deploy|status|logs|restart|stop) ;;
  *)
    echo ">>> Error: unknown command '${ACTION}'." >&2
    usage >&2
    exit 2
    ;;
esac

if ! command -v docker >/dev/null 2>&1; then
  echo ">>> Error: Docker was not found. Install Docker Engine with Compose v2 first." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo ">>> Error: Docker Compose v2 is unavailable. Check with: docker compose version" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo ">>> Error: cannot connect to the Docker daemon. Start Docker and check the current user's permissions." >&2
  exit 1
fi

if [ ! -f "${ENV_FILE}" ]; then
  if [ "${ACTION}" = "deploy" ] && [ "${ENV_FILE}" = "${PROJECT_DIR}/.env.docker" ]; then
    cp "${PROJECT_DIR}/.env.docker.example" "${ENV_FILE}"
    chmod 600 "${ENV_FILE}"
    echo ">>> Created ${ENV_FILE} from .env.docker.example."
    echo ">>> Fill in production secrets, then run ./deploy.sh again."
  else
    echo ">>> Error: environment file not found: ${ENV_FILE}" >&2
  fi
  exit 1
fi

export APP_ENV_FILE="${ENV_FILE}"
COMPOSE=(docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}")

read_env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -n 1
}

validate_production_env() {
  local key value invalid=0
  local required_keys=(
    MYSQL_ROOT_PASSWORD
    MYSQL_PASSWORD
    TOKEN_SIGNING_SECRET
    NORMAL_ACCESS_KEY
    VIP_ACCESS_KEY
  )

  for key in "${required_keys[@]}"; do
    value="$(read_env_value "${key}")"
    case "${value}" in
      ""|change-this-*|replace-with-*|demo-*)
        echo ">>> Error: ${key} is empty or still uses an example value." >&2
        invalid=1
        ;;
    esac
  done

  if [ "${invalid}" -ne 0 ]; then
    echo ">>> Update ${ENV_FILE}; deployment was not started." >&2
    return 1
  fi
}

cd "${PROJECT_DIR}"

case "${ACTION}" in
  deploy)
    validate_production_env
    mkdir -p "${PROJECT_DIR}/data"
    "${COMPOSE[@]}" config --quiet
    echo ">>> Building images and starting production services..."
    "${COMPOSE[@]}" up -d --build --remove-orphans --wait --wait-timeout "${DEPLOY_TIMEOUT:-120}"
    "${COMPOSE[@]}" ps
    APP_ADDRESS="$("${COMPOSE[@]}" port app 8028 2>/dev/null | head -n 1 || true)"
    echo ">>> Deployment completed successfully."
    if [ -n "${APP_ADDRESS}" ]; then
      echo ">>> Application endpoint: http://${APP_ADDRESS}"
    fi
    ;;
  status)
    "${COMPOSE[@]}" ps
    ;;
  logs)
    "${COMPOSE[@]}" logs --tail 200 -f app
    ;;
  restart)
    "${COMPOSE[@]}" restart app
    "${COMPOSE[@]}" ps app
    ;;
  stop)
    "${COMPOSE[@]}" down
    echo ">>> Services stopped. MySQL volume and ./data were kept."
    ;;
esac
