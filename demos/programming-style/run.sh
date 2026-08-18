#!/usr/bin/env bash
# Programming style: fold vs reduce, pure functions vs OOP mutation, and why
# a constructor-injected Spring bean with no other state IS a pure function.
#
#   bash demos/programming-style/run.sh
#
# Kotlin/Scala need the standalone compilers: bash tools/get_jvm_langs.sh
set -uo pipefail
cd "$(dirname "$0")/../.."

hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
nojava() { grep -Ev 'Picked up JAVA_TOOL_OPTIONS|^WARNING:' || true; }

if [[ ! -f build/jvm-langs/env.sh ]]; then
  echo "Scala/Kotlin compilers not present. Fetching them (~110 MB, once) ..."
  bash tools/get_jvm_langs.sh || { echo "Could not download the compilers. This demo needs network access once."; exit 1; }
fi
# shellcheck disable=SC1091
source build/jvm-langs/env.sh

OUT=build/demos/style
mkdir -p "$OUT"
D=demos/programming-style

hr; say "1/4  fold vs reduce — Java"
javac -d "$OUT" "$D/Fold.java" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT" Fold 2>&1 | nojava | sed 's/^/    /'

hr; say "2/4  fold vs reduce — Kotlin and Scala, for contrast"
kotlinc_ "$D/Fold.kt" -d "$OUT" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT:$KOTLIN_LIB" FoldKt 2>&1 | nojava | sed 's/^/    /'
echo
scalac_ -d "$OUT" "$D/Fold.scala" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT:$SCALA_LIB" FoldScala 2>&1 | nojava | sed 's/^/    /'

hr; say "3/4  The same Spring-wired service, OOP body vs FP body"
javac -d "$OUT" "$D/OrderPricingStyles.java" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT" OrderPricingStyles 2>&1 | nojava | sed 's/^/    /'

hr; say "4/4  Why a constructor-injected Spring bean is a pure function"
javac -d "$OUT" "$D/SpringBeanStyle.java" 2>&1 | nojava | sed 's/^/    /'
java -cp "$OUT" SpringBeanStyle 2>&1 | nojava | sed 's/^/    /'

hr
say "Summary to put on the board:"
cat <<'EOF'

    A fold is: seed + combining function + direction. Java's reduce() adds a
    fourth, hidden requirement - an associative combiner - because it was
    built to survive .parallel() (Block 4b). Kotlin and Scala can offer a
    real fold/foldRight because their collections never silently go parallel.

    "Pure" is not a keyword, it is a PROPERTY: no field read besides your
    arguments, no field write, no I/O. You get it for free from a class with
    only `final` fields set in the constructor and no other mutation - which
    is exactly what a default-scope Spring @Service with constructor
    injection looks like. That is not a coincidence about Spring; it is a
    coincidence about "final fields, no setters, no in-place mutation" being
    the general definition of a pure object, in any framework.

    The instant a bean gets ONE mutable field, the container still shares ONE
    instance across every concurrent request thread - now racing on it, with
    nothing in the stack trace ever mentioning "thread". Same bug as the
    ArrayList in docs/09-when-to-parallelize.md, wearing a @Service costume.
EOF
