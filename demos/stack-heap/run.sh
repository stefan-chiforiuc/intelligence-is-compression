#!/usr/bin/env bash
# Stack vs heap, in three acts.
#   bash demos/stack-heap/run.sh
set -uo pipefail
cd "$(dirname "$0")/../.."

hr() { printf '\n\033[1;34m%s\033[0m\n' "────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }

mkdir -p build/demos

hr; say "ACT 1 - Ask the compiler where it put things (Go escape analysis)"
echo
go build -gcflags='-m' -o /dev/null demos/stack-heap/escape.go 2>&1 \
  | grep -E 'escapes to heap|does not escape|moved to heap' \
  | sed 's/^/    /'
echo
say "    Every 'escapes to heap' line is an allocation. Every 'does not escape'"
say "    is a free object that dies with the stack frame."

hr; say "ACT 2 - What that costs at run time"
echo
go run demos/stack-heap/escape.go | sed 's/^/    /'

hr; say "ACT 3 - How many bytes is 'an object with two pointers'? (measured)"
echo
bash demos/stack-heap/objsize/run.sh

hr; say "Bonus: how deep can each language recurse before the stack runs out?"
echo
bash demos/stack-heap/stack_limits.sh
