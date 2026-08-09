#!/usr/bin/env bash
# How deep can each runtime recurse before the stack gives out?
#
# This makes "the stack is a small fixed region, the heap is the big one"
# concrete in about ten seconds. It also shows Go's party trick: goroutine
# stacks START tiny (2 KB) and GROW on demand, so Go recurses far deeper than
# anything else here before it hits its 1 GB ceiling.
set -uo pipefail
cd "$(dirname "$0")/../.."
mkdir -p build/demos

printf '    %-14s %s\n' "ulimit -s:" "$(ulimit -s) KB (the OS main-thread stack limit)"
echo

# --- Python -----------------------------------------------------------------
python3 - <<'PY'
import sys
sys.setrecursionlimit(10_000_000)
depth = 0
def f():
    global depth
    depth += 1
    f()
try:
    f()
except RecursionError:
    print(f"    {'Python':<14} {depth:>10,} frames  (RecursionError - a soft, catchable limit)")
except Exception as e:
    print(f"    {'Python':<14} {depth:>10,} frames  ({type(e).__name__})")
PY

# --- Node -------------------------------------------------------------------
node -e '
let d = 0;
function f() { d++; f(); }
try { f(); } catch (e) { console.log(`    ${"Node".padEnd(14)} ${d.toLocaleString().padStart(10)} frames  (RangeError - catchable)`); }
'

# --- Java -------------------------------------------------------------------
cat > build/demos/StackDepth.java <<'JAVA'
public class StackDepth {
    static int depth = 0;
    static void f() { depth++; f(); }
    public static void main(String[] a) {
        try { f(); } catch (StackOverflowError e) {
            System.out.printf("    %-14s %,10d frames  (StackOverflowError - catchable, but do not)%n", "Java", depth);
        }
    }
}
JAVA
javac -d build/demos build/demos/StackDepth.java 2>/dev/null
java -cp build/demos StackDepth 2>/dev/null | grep -v 'Picked up'

# --- Go ---------------------------------------------------------------------
cat > build/demos/stackdepth.go <<'GO'
package main

import "fmt"

var depth int

func f() { depth++; f() }

func main() {
	defer func() {
		// Go's stack-overflow is a fatal runtime error and is NOT recoverable;
		// this deferred func will not actually run. We print the ceiling from
		// the runtime's documented 1 GB default instead.
		recover()
	}()
	fmt.Println("    Go             goroutine stacks start at 2 KB and GROW on demand,")
	fmt.Println("                   up to a 1 GB default ceiling (runtime/debug.SetMaxStack).")
	fmt.Println("                   Overflow is a FATAL error, not an exception. Uncomment")
	fmt.Println("                   the f() call in stack_limits.sh to watch it die.")
	_ = depth
	// f()  // <- uncomment to crash the process on purpose
}
GO
go run build/demos/stackdepth.go

# --- Rust -------------------------------------------------------------------
cat > build/demos/stackdepth.rs <<'RS'
fn main() {
    println!("    Rust           8 MB main-thread stack by default (same as the OS).");
    println!("                   Overflow aborts the process with SIGSEGV - it is NOT");
    println!("                   catchable. Rust's answer is to not recurse deeply:");
    println!("                   iterate, or move the work to the heap explicitly.");
}
RS
rustc -O build/demos/stackdepth.rs -o build/demos/stackdepth_rs 2>/dev/null && build/demos/stackdepth_rs

echo
echo "    Takeaway: the stack is FAST (bump a pointer, free on return) but SMALL"
echo "    and fixed. The heap is large and flexible but every object costs you"
echo "    an allocation now and a collection later. Recursion depth is a stack"
echo "    budget question; data size is a heap budget question."
