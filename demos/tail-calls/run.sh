#!/usr/bin/env bash
# Tail-call optimisation: Java vs Scala vs Kotlin, on the same JVM.
#
#   bash demos/tail-calls/run.sh
#
# Needs the standalone compilers: bash tools/get_jvm_langs.sh
set -uo pipefail
cd "$(dirname "$0")/../.."

hr()  { printf '\n\033[1;34m%s\033[0m\n' "───────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }

# Strips the JAVA_TOOL_OPTIONS banner some environments inject, plus the
# restricted-native-access / sun.misc.Unsafe deprecation warnings the
# embeddable Kotlin compiler prints on JDK 24+ - both are noise, not signal.
nojava() { grep -Ev 'Picked up JAVA_TOOL_OPTIONS|^WARNING:' || true; }

if [[ ! -f build/jvm-langs/env.sh ]]; then
  echo "Scala/Kotlin compilers not present. Fetching them (~110 MB, once) ..."
  bash tools/get_jvm_langs.sh || {
    echo "Could not download the compilers. This demo needs network access once."
    exit 1
  }
fi
# shellcheck disable=SC1091
source build/jvm-langs/env.sh

OUT=build/demos/tailcalls
mkdir -p "$OUT"
D=demos/tail-calls

echo "Compiling (Java, Scala, Kotlin) ..."
javac -d "$OUT" $D/Recursion.java 2>&1 | nojava
scalac_ -d "$OUT" $D/Recursion.scala 2>&1 | nojava
kotlinc_ $D/Recursion.kt -d "$OUT" 2>&1 | nojava

hr; say "1/4  Same function, three languages, one JVM"
echo
java -cp "$OUT" Recursion 10000000 2>&1 | nojava | sed 's/^/    /'
echo
java -cp "$OUT:$SCALA_LIB" RecursionScala 10000000 2>&1 | nojava | sed 's/^/    /'
echo
java -cp "$OUT:$KOTLIN_LIB" RecursionKt 10000000 2>&1 | nojava | sed 's/^/    /'

hr; say "2/4  Proof: look at the bytecode, not the source"

# Print the body of exactly one method: the two-argument `sumTail`. Without
# pinning the signature we also pick up the compiler-generated default-argument
# wrappers, which DO contain a normal call and muddy the point.
body() { # class, exact signature substring
  javap -c -p -cp "$OUT" "$1" 2>/dev/null \
    | awk -v sig="$2" 'index($0, sig) { grab=1; next } grab && /^$/ { exit } grab'
}

echo
say "    Java sumTail — a recursive call to itself:"
body Recursion 'long sumTail(long, long)' | grep -E 'invokestatic|goto' | sed 's/^/      /'
echo
say "    Scala sumTail — a jump. There is no call at all:"
body 'RecursionScala$' 'long sumTail(long, long)' | grep -E 'invokestatic|goto' | sed 's/^/      /'
echo
say "    Kotlin sumTail — also a jump:"
body RecursionKt 'long sumTail(long, long)' | grep -E 'invokestatic|goto' | sed 's/^/      /'
echo
say "    'goto' means the compiler turned recursion into iteration."
say "    'invokestatic <the same method>' means it did not."

hr; say "3/4  @tailrec is enforcement, not optimisation"
echo
say "    This file has a recursive call NOT in tail position, marked @tailrec:"
scalac_ -d "$OUT" $D/NotTailRec.scala 2>&1 | nojava | head -6 | sed 's/^/      /'
echo
say "    The build fails. In Java the equivalent mistake is silent until"
say "    production, because there is nothing to annotate."

hr; say "4/4  Why can't the JVM just do this for everyone?"
cat <<'EOF'

    Tail calls are not a JVM instruction. The JVM's verifier and its stack-walking
    security/observability model (stack traces, and historically the security
    manager's caller inspection) assume frames are really there. A general
    tail-call instruction has been discussed for the JVM for two decades and has
    repeatedly lost to those constraints. Project Loom's continuations have
    reopened the machinery, but there is still no general TCO for Java.

    So Scala and Kotlin do not ask the JVM for anything. They rewrite the code
    themselves, at compile time, into a loop — which is why the bytecode above
    contains a `goto`.

    THE TRANSFERABLE LESSON
    "The platform" is not one thing. Java, Scala and Kotlin share a bytecode
    format, a JIT, a GC and a standard library, and still disagree about which
    programs are valid. When someone says "we're a JVM shop", they have chosen a
    runtime, not a language — and the language still decides what you can express.
EOF
