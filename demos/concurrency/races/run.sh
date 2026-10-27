#!/usr/bin/env bash
# Data races: the same shared counter in seven languages.
#
#   bash demos/concurrency/races/run.sh
#
# This is the concurrency twin of the typing demo in Block 1. Six languages
# compile the broken program happily and give a different wrong answer every
# run (C++ may even give the right one - it is undefined behaviour). One
# refuses to build it.
set -uo pipefail
cd "$(dirname "$0")/../../.."

OUT=build/demos/concurrency
D=demos/concurrency/races
mkdir -p "$OUT"

hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
nojava() { grep -v 'Picked up JAVA_TOOL_OPTIONS' || true; }

hr; say "1/7  Go — compiles, runs, wrong answer"
echo
go run $D/race.go | sed 's/^/    /'
echo
say "    Now with the race detector (go run -race):"
go run -race $D/race.go 2>&1 | grep -E 'WARNING: DATA RACE|race.go:[0-9]+|Previous write|^  [A-Za-z]' \
  | head -8 | sed 's/^/      /'
say "    ^ it names the file, the line, and both goroutines. Use -race in CI."

hr; say "2/7  Java — same race, plus the volatile trap"
echo
javac -d "$OUT" $D/Race.java 2>&1 | nojava
java -cp "$OUT" Race 2>&1 | nojava | sed 's/^/    /'
say "    ^ note 'volatile' still loses increments. It gives VISIBILITY, not ATOMICITY."

hr; say "3/7  C# — same race, same volatile trap"
echo
dotnet build $D/Race.csproj -c Release -o "$OUT/race_cs" --nologo -v q \
  -p:BaseIntermediateOutputPath="$PWD/build/obj/race/" >/dev/null 2>&1
dotnet "$OUT/race_cs/Race.dll" | sed 's/^/    /'
say "    ^ 'volatile' again: visibility, not atomicity. Fix: lock or Interlocked."

hr; say "4/7  C++ — a data race is undefined behaviour, not just a wrong answer"
echo
g++ -O0 -std=c++20 -pthread $D/race.cpp -o "$OUT/race_cpp_O0"
g++ -O2 -std=c++20 -pthread $D/race.cpp -o "$OUT/race_cpp_O2"
say "    Built with -O0:"
"$OUT/race_cpp_O0" | sed 's/^/      /'
say "    Same source, built with -O2:"
"$OUT/race_cpp_O2" | sed 's/^/      /'
say "    ^ at -O2 the 100,000-iteration loop collapses to ONE 'add 100000' per"
say "      thread, so the race window all but disappears. Still a race, still UB."
say "      A race that does not reproduce is still a race. Same code, new answer."
echo
say "    ThreadSanitizer (g++ -fsanitize=thread) is C++'s answer to 'go -race':"
# TSan exits non-zero when it finds a race (that is its job), so test the BUILD
# separately from the run rather than chaining them with ||.
if g++ -O1 -g -std=c++20 -pthread -fsanitize=thread $D/race.cpp -o "$OUT/race_cpp_tsan" 2>/dev/null; then
  "$OUT/race_cpp_tsan" 2>&1 | grep -E 'WARNING: ThreadSanitizer|race.cpp:[0-9]+' | head -4 | sed 's/^/      /'
else
  say "      (ThreadSanitizer not available in this toolchain)"
fi

hr; say "5/7  Python — does the GIL save you?"
echo
python3 $D/race.py | sed 's/^/    /'

hr; say "6/7  Node — no shared memory, no race... until you ask for shared memory"
echo
npx --no-install tsc $D/race.mts --outDir "$OUT" --target es2022 --module nodenext \
  --moduleResolution nodenext --skipLibCheck --types node 2>/dev/null \
  && node "$OUT/race.mjs" 2>&1 | sed 's/^/    /' \
  || node $D/race.mts 2>&1 | sed 's/^/    /'

hr; say "7/7  Rust — the broken version does not compile"
echo
rustc --edition 2021 $D/race_wont_compile.rs -o /dev/null 2>&1 | head -16 | sed 's/^/    /'
echo
say "    And the versions that say what they mean:"
rustc --edition 2021 -O $D/race_fixed.rs -o "$OUT/race_fixed_rs" 2>/dev/null
"$OUT/race_fixed_rs" | sed 's/^/    /'

hr
cat <<'EOF'
WHAT TO TAKE AWAY

  counter++ is never one operation. It is load, add, store. Every language on
  this list has the same hardware underneath and the same hazard.

  What differs is WHEN you find out:

    Rust     compile time    the borrow checker + Send/Sync make it unwritable
    Go       run time, opt-in  -race finds it IF a test exercises the path
    C++      run time, opt-in  -fsanitize=thread, and the bug is undefined
                               behaviour, so it may hide at -O2
    C#       run time, never  Interlocked/lock exist; nothing forces you
    Java     run time, never  tooling exists but nothing is on by default
    Python   run time, rarely the GIL hides it until production load
    Node     n/a by default   no shared memory - until SharedArrayBuffer

  Note the exact parallel with Block 1: the same bug, and the languages differ
  not in whether they have it but in how early they tell you. That is the single
  most transferable idea in this whole session.

  AND THE HONEST CAVEAT: Rust prevents DATA races (unsynchronised access to
  shared memory). It does not prevent RACE CONDITIONS in the logical sense —
  deadlocks, lost wakeups, check-then-act across an await, or two correct
  services disagreeing about who owns a row. No type system saves you there.
EOF
