#!/usr/bin/env bash
# Manage the training database, wherever it happens to live.
#
#   bash demos/db-scaling/db.sh up       start the container (or find a local PG)
#   bash demos/db-scaling/db.sh status   what are we connected to, and how big is it
#   bash demos/db-scaling/db.sh psql     open a shell on it
#   bash demos/db-scaling/db.sh down     stop and remove
#   bash demos/db-scaling/db.sh env      print the connection env vars
#
# Resolution order, so this works on a laptop with Docker, a laptop without it,
# and a CI box:
#   1. $TRAINING_DB_URL, if you set it (Cloud SQL, a shared instance, anything)
#   2. the Docker container from docker-compose.yml
#   3. a PostgreSQL already listening on localhost:5432
# If none are available, the Python demos fall back to the pure simulation and
# say so loudly.
set -uo pipefail
cd "$(dirname "$0")/../.."

COMPOSE_FILE=demos/db-scaling/docker-compose.yml
CONTAINER=lang-training-db

have_docker() { command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; }

compose() {
  if docker compose version >/dev/null 2>&1; then docker compose "$@";
  elif command -v docker-compose >/dev/null 2>&1; then docker-compose "$@";
  else return 1; fi
}

# Print a libpq URL for whichever database we can reach, or nothing.
resolve_url() {
  if [[ -n "${TRAINING_DB_URL:-}" ]]; then
    echo "$TRAINING_DB_URL"; return 0
  fi
  if have_docker && docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "postgresql://training:training@127.0.0.1:55432/training"; return 0
  fi
  if command -v pg_isready >/dev/null 2>&1 && pg_isready -h 127.0.0.1 -p 5432 -q 2>/dev/null; then
    echo "postgresql://training:training@127.0.0.1:5432/training"; return 0
  fi
  return 1
}

case "${1:-status}" in

  up)
    if ! have_docker; then
      echo "No Docker daemon available."
      if resolve_url >/dev/null; then
        echo "Found a PostgreSQL already running: $(resolve_url)"
        exit 0
      fi
      cat <<'EOF'

You have three options, in order of realism:

  1. Start Docker and re-run this. Best: you get real resource limits.
  2. Point at any PostgreSQL you already have:
       export TRAINING_DB_URL=postgresql://user:pass@host:5432/dbname
  3. Do nothing. The demos fall back to a pure simulation and say so.

For a local install without Docker (Debian/Ubuntu):
  apt-get install -y postgresql
  pg_ctlcluster 16 main start
  su postgres -c "psql -c \"CREATE USER training PASSWORD 'training' SUPERUSER;\""
  su postgres -c "psql -c 'CREATE DATABASE training OWNER training;'"
EOF
      exit 1
    fi
    echo "Starting $CONTAINER (postgres:16-alpine, 1 CPU, 512 MB, max_connections=50) ..."
    compose -f "$COMPOSE_FILE" up -d || { echo "compose failed"; exit 1; }
    printf "waiting for health "
    for _ in $(seq 1 60); do
      if docker exec "$CONTAINER" pg_isready -U training -d training -q 2>/dev/null; then
        echo " ready"; break
      fi
      printf "."; sleep 1
    done
    "$0" status
    ;;

  down)
    if have_docker; then
      compose -f "$COMPOSE_FILE" down -v 2>/dev/null || docker rm -f "$CONTAINER" 2>/dev/null
      echo "Removed $CONTAINER."
    else
      echo "No Docker daemon; nothing to remove."
    fi
    ;;

  env)
    url=$(resolve_url) || { echo "no database reachable" >&2; exit 1; }
    echo "export TRAINING_DB_URL='$url'"
    ;;

  psql)
    url=$(resolve_url) || { echo "no database reachable; run: bash $0 up" >&2; exit 1; }
    shift || true
    psql "$url" "$@"
    ;;

  status)
    url=$(resolve_url) || {
      echo "No training database reachable."
      echo "Run:  bash demos/db-scaling/db.sh up"
      echo "The Python demos will fall back to simulation until then."
      exit 1
    }
    echo "Connected to: $url"
    psql "$url" -tAF' ' -c "
      SELECT 'server        ' , version();
      SELECT 'max_connections', setting FROM pg_settings WHERE name='max_connections';
      SELECT 'shared_buffers ', setting || ' x 8kB' FROM pg_settings WHERE name='shared_buffers';
      SELECT 'in use now     ', count(*)::text FROM pg_stat_activity;
    " 2>/dev/null | sed 's/^/  /'
    if have_docker && docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
      echo "  container limits:"
      docker stats --no-stream --format '    CPU {{.CPUPerc}}  MEM {{.MemUsage}} ({{.MemPerc}})' "$CONTAINER"
    fi
    ;;

  *)
    echo "usage: $0 {up|down|status|psql|env}"
    exit 1
    ;;
esac
