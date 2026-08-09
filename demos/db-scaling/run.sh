#!/usr/bin/env bash
# Databases: connection pools, the connection wall, and transaction anomalies.
#
#   bash demos/db-scaling/run.sh            # real PostgreSQL if reachable
#   bash demos/db-scaling/run.sh --sim      # force the no-infrastructure version
#
# Prefers a REAL PostgreSQL (Docker container, local install, or $TRAINING_DB_URL)
# and falls back to the simulation, saying so loudly. It never silently fakes it.
set -uo pipefail
cd "$(dirname "$0")/../.."

hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn(){ printf '\033[1;33m%s\033[0m\n' "$*"; }

FORCE_SIM=0
[[ "${1:-}" == "--sim" ]] && FORCE_SIM=1

REAL=0
if [[ $FORCE_SIM -eq 0 ]] && python3 -c "
import sys, os
sys.path.insert(0, 'demos/db-scaling')
from _db import resolve_url
sys.exit(0 if resolve_url() else 1)
" 2>/dev/null; then
  REAL=1
fi

if [[ $REAL -eq 1 ]]; then
  say "Using a REAL PostgreSQL."
  bash demos/db-scaling/db.sh status

  hr; say "PART 1 - The connection wall"
  echo
  python3 demos/db-scaling/exhaust_connections.py

  hr; say "PART 2 - Why a bigger connection pool is usually slower"
  echo
  python3 demos/db-scaling/real_pool.py

  hr; say "PART 3 - The same race condition, now in the database"
  echo
  python3 demos/db-scaling/real_transactions.py

  hr; say "For contrast, the SAME demo on SQLite - it fails differently:"
  echo
  python3 demos/db-scaling/transactions.py 2>/dev/null | sed -n '4,12p'
else
  if [[ $FORCE_SIM -eq 1 ]]; then
    say "Simulation mode requested."
  else
    warn "No PostgreSQL reachable - running the SIMULATED versions."
    warn "For the real thing (1 CPU, 512 MB, max_connections=50):"
    warn "    bash demos/db-scaling/db.sh up"
  fi

  hr; say "PART 1 - Why a bigger connection pool is usually slower (simulated)"
  echo
  python3 demos/db-scaling/pool_sizing.py

  hr; say "PART 2 - The same race condition, in the database (SQLite)"
  echo
  python3 demos/db-scaling/transactions.py
fi

hr
cat <<'EOF'
THE THREAD THROUGH THIS WHOLE SESSION

  We have now hit the SAME bug at four different layers:

    Block 1  a type error caught at compile time, or not
    Block 4  counter++ from 8 threads, losing 306,789 increments
    Block 4c 20 users appending to one ArrayList over HTTP, losing 3,874 items
    Block 5b 16 bookers on one database row: 192 confirmed, 13 stored

  It is one bug: READ, MODIFY, WRITE, with a window in the middle. Every layer
  has its own name for the fix, and they are all the same fix:

    language     Mutex, synchronized, atomics, ownership
    collection   ConcurrentLinkedQueue, synchronizedList
    database     SELECT FOR UPDATE, optimistic version, atomic UPDATE,
                 REPEATABLE READ, or a schema where the bad state cannot exist

  And at every layer the best answer has the same shape: make the invalid state
  unrepresentable, so nobody has to remember. A type. A Mutex<T>. A hundred
  seat rows that simply do not have a hundred-and-first.

NEXT: demos/db-scaling/GCP-RUNBOOK.md runs all of this against Cloud SQL.
EOF
