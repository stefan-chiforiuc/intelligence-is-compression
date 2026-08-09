#!/usr/bin/env bash
# Databases: connection pools and transactions.
#
#   bash demos/db-scaling/run.sh
#
# Both demos run locally with zero infrastructure. To show the same results
# against real Cloud SQL, see demos/db-scaling/GCP-RUNBOOK.md.
set -uo pipefail
cd "$(dirname "$0")/../.."

hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }

hr; say "PART 1 — Why a bigger connection pool is usually slower"
echo
python3 demos/db-scaling/pool_sizing.py

hr; say "PART 2 — The same race condition, now in the database"
echo
python3 demos/db-scaling/transactions.py

hr
cat <<'EOF'
THE THREAD THROUGH THIS WHOLE SESSION

  We have now hit the SAME bug at four different layers:

    Block 1  a type error caught at compile time, or not
    Block 4  counter++ from 8 threads, losing 306,789 increments
    Block 4b 20 users appending to one ArrayList over HTTP, losing 2,343 items
    Block 5  16 bookers on one database row, confirming 400 and storing 25

  It is one bug: READ, MODIFY, WRITE, with a window in the middle. Every layer
  has its own name for the fix, and they are all the same fix:

    language     Mutex, synchronized, atomics, ownership
    collection   ConcurrentLinkedQueue, synchronizedList
    database     SELECT FOR UPDATE, optimistic version, atomic UPDATE, CHECK

  And at every layer, the best answer is the same in shape: make the invalid
  state unrepresentable, so nobody has to remember. A type. A Mutex<T>. A
  CHECK constraint.

NEXT: bash demos/db-scaling/GCP-RUNBOOK.md's walkthrough to show this on a
real Cloud SQL instance. The two-session lost-update demo in section 4 is the
one worth doing live even if everything else stays simulated.
EOF
