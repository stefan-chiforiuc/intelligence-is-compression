#!/usr/bin/env bash
# 20 users, one shared array, a real HTTP API.
#
#   bash demos/api-race/run.sh
#
# Takes ~30 s. Most of that is CopyOnWriteArrayList, deliberately — its cost is
# one of the lessons.
set -uo pipefail
cd "$(dirname "$0")/../.."

OUT=build/demos/apirace
mkdir -p "$OUT"
hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
nojava() { grep -v 'Picked up JAVA_TOOL_OPTIONS' || true; }

echo "Building ..."
javac -d "$OUT" demos/api-race/ApiRace.java 2>&1 | nojava
rustc -O --edition 2021 demos/api-race/api_race.rs -o "$OUT/api_race_rs" 2>&1 | head -5

hr; say "JAVA — five ways to share one list between 20 concurrent users"
echo
java -cp "$OUT" ApiRace "$@" 2>&1 | nojava

hr; say "RUST — the same API. First, the version everyone writes in Java:"
echo
rustc --edition 2021 demos/api-race/api_race_wont_compile.rs -o /dev/null 2>&1 \
  | head -8 | sed 's/^/    /'
echo
say "    It does not build. There is no way to hand 20 handler threads one"
say "    plain Vec. You must name the synchronisation strategy."
echo
"$OUT/api_race_rs" 2>&1

hr
cat <<'EOF'
THE COMPARISON TO PUT ON THE BOARD

  Java    the unsynchronised version is ORDINARY-LOOKING CODE.
          It compiles, it reviews fine, it passes a single-threaded test,
          it returns 204 to every caller, and it loses data under load.
          Correctness depends on a human remembering.

  Rust    the unsynchronised version DOES NOT EXIST.
          `Vec<String>` is Send but not Sync, so a shared reference cannot
          cross a thread boundary. To share it you write
          `Arc<Mutex<Vec<String>>>`, and then you cannot forget to lock
          (the data is inside the Mutex) or to unlock (the guard drops).

  This is the same shape as the typing block: the bug is not prevented by
  being careful, it is prevented by being unrepresentable.

  AND THE HONEST LIMITS - say all three:
   * Rust prevents DATA races, not deadlocks, not check-then-act logic bugs,
     and not two services disagreeing over who owns a row.
   * The Rust demo uses ONE global lock, which is the worst design for
     throughput. Safe is not the same as scalable.
   * Java has good answers here too. ConcurrentLinkedQueue was both correct
     and the fastest option in the table. The difference is the DEFAULT:
     Java's default is a data structure that quietly breaks.
EOF
