#!/usr/bin/env bash
# Runs the whole typing section end to end, in the order it should be presented.
# Pauses between demos so you can talk over each one.
#
#   bash demos/typing/run.sh          # pause between demos
#   bash demos/typing/run.sh --fast   # no pauses
set -uo pipefail
cd "$(dirname "$0")/../.."

PAUSE=1
[[ "${1:-}" == "--fast" ]] && PAUSE=0

hr() { printf '\n\033[1;34m%s\033[0m\n' "────────────────────────────────────────────────────────────"; }
say() { printf '\033[1;36m%s\033[0m\n' "$*"; }
pause() { [[ $PAUSE -eq 1 ]] && { printf '\n\033[2m[enter to continue]\033[0m'; read -r; } || true; }

mkdir -p build/demos

# Resolved ONCE: tsc's own diagnostics are expected output in some demos below
# (var_inference.ts is SUPPOSED to fail), so we can't tell "npx --no-install
# tsc found no local install" apart from "tsc ran and reported an error" by
# exit code alone. Pick the binary up front instead of retrying on failure.
TSC="npx --no-install tsc"
$TSC --version >/dev/null 2>&1 || TSC="npx tsc"

hr; say "1/5  JavaScript - dynamic + WEAK. The bug ships silently."
node demos/typing/weak_typing.js
pause

hr; say "2/5  Python - dynamic + STRONG. The bug crashes loudly, but only at run time."
python3 demos/typing/strong_typing.py
pause

hr; say "3/5  TypeScript - static types, ERASED at run time."
$TSC demos/typing/erasure.ts --outDir build/demos \
  --target es2022 --module nodenext --moduleResolution nodenext \
  --skipLibCheck --types node
node build/demos/erasure.js
echo
say "    The same line of code, before and after compilation:"
printf '    \033[2mTypeScript source :\033[0m %s\n' "$(grep -m1 'const total' demos/typing/erasure.ts | sed 's/^ *//')"
printf '    \033[2mEmitted JavaScript:\033[0m %s\n' "$(grep -m1 'const total' build/demos/erasure.js | sed 's/^ *//')"
echo
printf '    \033[2m`interface Order` in the emitted JS:\033[0m %s\n' \
  "$(grep -c 'interface Order' build/demos/erasure.js) occurrences - the whole interface vanished"
pause

hr; say "4/5  Go - static + strong. The artifact cannot be built."
go build -o /dev/null demos/typing/wont_compile.go 2>&1 | sed 's/^/    /' || true
pause

hr; say "5/5  Java and Rust - same story, different strictness."
javac -d build/demos demos/typing/WontCompile.java 2>&1 \
  | grep -v 'Picked up JAVA_TOOL_OPTIONS' | sed 's/^/    /' || true
echo
rustc --edition 2021 demos/typing/wont_compile.rs -o /dev/null 2>&1 | head -20 | sed 's/^/    /' || true

hr; say "BONUS  var / := / let are not dynamic typing"
echo
say "    Java's var, Go's :=, Rust's let and TypeScript's inferred let all pick"
say "    ONE type at the declaration and keep it forever. Only Python lets a"
say "    name change type mid-life. Watch each one reject a type change:"
echo
say "    Java  -"
javac -d build/demos demos/typing/VarInference.java 2>&1 | grep -v 'Picked up JAVA_TOOL_OPTIONS' | sed 's/^/      /' || true
echo
say "    Go    -"
go build -o /dev/null demos/typing/var_inference.go 2>&1 | sed 's/^/      /' || true
echo
say "    Rust  -"
rustc --edition 2021 demos/typing/var_inference.rs -o /dev/null 2>&1 | head -8 | sed 's/^/      /' || true
echo
say "    TypeScript -"
$TSC demos/typing/var_inference.ts --outDir build/demos \
  --target es2022 --module nodenext --moduleResolution nodenext \
  --skipLibCheck --types node 2>&1 | sed 's/^/      /' || true
echo
say "    Python - the control. Nothing rejects this, because there is nothing to reject:"
python3 demos/typing/var_inference.py | sed 's/^/      /'
pause

hr
say "Summary to put on the board:"
cat <<'EOF'

                    STATIC (checked at compile time)
                                 ^
                                 |
              Java, Go, Rust     |     (nothing useful lives here)
              TypeScript*        |
    STRONG <---------------------+---------------------> WEAK
    (few implicit              |
     conversions)   Python      |     JavaScript
                                 |
                                 v
                    DYNAMIC (checked at run time)

    * TypeScript is static at COMPILE time and fully dynamic+weak at RUN time,
      because the types are erased. It is the only language on this chart that
      moves between quadrants depending on when you look at it.
EOF
