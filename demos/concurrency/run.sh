#!/usr/bin/env bash
# Block 4 — concurrency, both halves.
#
#   bash demos/concurrency/run.sh            # scaling, then races
#   bash demos/concurrency/run.sh --races    # races only
#   bash demos/concurrency/run.sh --parallel # scaling only
set -uo pipefail
cd "$(dirname "$0")/../.."

MODE="${1:-all}"

banner() {
  printf '\n\033[1;35m%s\033[0m\n' "═══════════════════════════════════════════════════════════════"
  printf '\033[1;35m%s\033[0m\n'   "$1"
  printf '\033[1;35m%s\033[0m\n'   "═══════════════════════════════════════════════════════════════"
}

if [[ "$MODE" == "all" || "$MODE" == "--parallel" ]]; then
  banner "PART 1 — Can you use all your cores?"
  python3 demos/concurrency/parallel/run.py
fi

if [[ "$MODE" == "all" || "$MODE" == "--races" ]]; then
  banner "PART 2 — What happens when you share state?"
  bash demos/concurrency/races/run.sh
fi
