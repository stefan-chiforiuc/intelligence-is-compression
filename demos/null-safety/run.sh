#!/usr/bin/env bash
# Null safety: the same bug in five languages, and why Kotlin's answer is a
# type-system feature, not a linter warning.
#
#   bash demos/null-safety/run.sh
#
# Kotlin needs the standalone compiler: bash tools/get_jvm_langs.sh
set -uo pipefail
cd "$(dirname "$0")/../.."

hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
# Strips the JAVA_TOOL_OPTIONS banner some environments inject, plus the
# restricted-native-access / sun.misc.Unsafe deprecation warnings the
# embeddable Kotlin compiler prints on JDK 24+ - both are noise, not signal.
nojava() { grep -Ev 'Picked up JAVA_TOOL_OPTIONS|^WARNING:' || true; }

OUT=build/demos/nullsafety
mkdir -p "$OUT"
D=demos/null-safety

# Resolved ONCE: the --strictNullChecks run below is SUPPOSED to fail, so we
# can't tell "no local tsc" apart from "tsc ran and reported the error we
# wanted" by exit code. Pick the binary before we start relying on tsc's exit
# code to mean something.
TSC="npx --no-install tsc"
$TSC --version >/dev/null 2>&1 || TSC="npx tsc"

hr; say "1/5  Java - compiles clean, explodes at run time"
# -g: keeps local variable names, so the helpful-NPE message (JEP 358) names
# "missing" instead of a debug-stripped "<local3>".
javac -g -d "$OUT" "$D/NullSafety.java" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT" NullSafety 2>&1 | nojava | sed 's/^/    /' || true

hr; say "2/5  Python - same bug, different exception"
python3 "$D/null_safety.py" 2>&1 | sed 's/^/    /' || true

hr; say "3/5  TypeScript - real at compile time IF you opt in, erased either way"
say "    Without --strictNullChecks (accepted, then crashes at run time):"
$TSC "$D/null_safety.ts" --outDir "$OUT" \
  --target es2022 --module nodenext --moduleResolution nodenext --skipLibCheck 2>&1 \
  | sed 's/^/      /'
node "$OUT/null_safety.js" 2>&1 | sed 's/^/      /' || true
echo
say "    With --strictNullChecks (rejected before it ever runs):"
$TSC "$D/null_safety.ts" --noEmit \
  --target es2022 --module nodenext --moduleResolution nodenext --skipLibCheck \
  --strictNullChecks 2>&1 | sed 's/^/      /' || true

hr; say "4/5  Rust - no null. Option<T> and the compiler blocks the call outright."
rustc --edition 2021 "$D/null_safety.rs" -o "$OUT/null_safety_rs" 2>&1 | sed 's/^/    /'
"$OUT/null_safety_rs" 2>&1 | sed 's/^/    /'

hr; say "5/5  Kotlin - String? vs String are different types"
if [[ ! -f build/jvm-langs/env.sh ]]; then
  echo "Scala/Kotlin compilers not present. Fetching them (~110 MB, once) ..."
  bash tools/get_jvm_langs.sh || { echo "Could not download the compilers. This demo needs network access once."; exit 1; }
fi
# shellcheck disable=SC1091
source build/jvm-langs/env.sh
kotlinc_ "$D/NullSafety.kt" -d "$OUT" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT:$KOTLIN_LIB" NullSafetyKt 2>&1 | nojava | sed 's/^/    /'

hr
say "Summary to put on the board:"
cat <<'EOF'

    Language     Absence is...                       Caught...
    Java         any reference, silently              at run time, anywhere
    Python       None, silently                       at run time, anywhere
    TypeScript   string|undefined, OPT-IN, ERASED      compile time IF you ask, else run time
    Rust         Option<T> - not the same type as T    at compile time, always
    Kotlin       String? vs String - distinct types    at compile time, always

    Same shape as the erasure demo (Block 1) and Mutex<T> (Block 4): put the
    strategy IN THE TYPE and the invalid state becomes impossible to write
    down, not just unlikely to trigger.
EOF
