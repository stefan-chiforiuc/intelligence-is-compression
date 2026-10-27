# Block 2b — Same runtime, different language: Scala, Kotlin and tail calls

**Run:** `make demo-tailcalls`
**Setup (once, needs network):** `bash tools/get_jvm_langs.sh`

This is a short, sharp addition to the compilation block. It exists to break one
specific belief:

> "We're a JVM shop" names a **runtime**. It does not name a **language**, and
> the language still decides what you can express.

Java, Scala and Kotlin compile to the same bytecode, run on the same JIT, use
the same garbage collector and share a standard library. They still disagree
about whether a given program is *valid*.

---

## The demo in one table

The same function — sum 1..n, written with the recursive call in tail position:

| Language | `sumTail(10_000_000)` | Bytecode emitted |
| --- | --- | --- |
| Java | **`StackOverflowError`** (~14,400 frames deep) | `invokestatic sumTail` |
| Scala (`@tailrec`) | `50000005000000` | **`goto 0`** |
| Kotlin (`tailrec`) | `50000005000000` | **`goto 0`** |

The bytecode line is the whole argument, and the demo prints it live via
`javap -c`. Nothing about the JVM changed. The *compiler* changed.

---

## What tail-call optimisation actually is

A call is in **tail position** if nothing happens after it returns — the
returned value is immediately the caller's returned value.

```scala
def sumTail(n: Long, acc: Long): Long =
  if (n == 0) acc else sumTail(n - 1, acc + n)   // tail position

def factorial(n: Int): Long =
  if (n <= 1) 1 else n * factorial(n - 1)        // NOT tail position: the
                                                 // multiply happens afterwards
```

When a call is in tail position, the current stack frame is dead weight — there
is nothing left to come back to. So the compiler can reuse it: overwrite the
arguments and jump to the top. Recursion becomes iteration, and stack usage
becomes constant.

`factorial` cannot be rewritten this way, because the frame must survive to do
the multiplication. **TCO is not magic; it is one narrow rewrite of one narrow
code shape**, and the demo shows Scala's `factorial` overflowing exactly like
Java's.

---

## The real lesson is enforcement, not optimisation

`@tailrec` does not *enable* the optimisation — scalac would do it anyway. It
makes the optimisation **mandatory**. This file fails to build:

```scala
@tailrec
def sumBroken(n: Long, acc: Long = 0): Long =
  if (n == 0) acc
  else sumBroken(n - 1, acc + n) + 0   // the `+ 0` breaks tail position
```
```
error: could not optimize @tailrec annotated method sumBroken:
       it contains a recursive call not in tail position
```

That is the pattern worth teaching, and it recurs everywhere in this session:

> A silent performance/correctness cliff has been converted into a compile error.

Someone "improving" that function months later cannot quietly reintroduce
unbounded stack growth. In Java there is nothing to annotate, so the equivalent
mistake is invisible until a large input arrives in production.

Kotlin's `tailrec` modifier works the same way and warns when it cannot apply.
Showing both matters: it stops the class from filing this under "exotic
functional-language feature". Kotlin is a mainstream, pragmatic, Java-adjacent
language, and it does exactly the same rewrite.

---

## Why can't the JVM just do this for everyone?

Tail calls are not a JVM instruction. The verifier and the platform's
stack-walking model — stack traces, and historically the security manager's
caller inspection — assume frames are really there. A general tail-call
instruction has been proposed for the JVM for two decades and has repeatedly
lost to those constraints. Project Loom's continuations reopened some of the
machinery, but there is still no general TCO for Java.

So Scala and Kotlin do not ask the JVM for anything. **They rewrite the code
themselves, at compile time, into a loop.** That is why the bytecode shows a
`goto`.

### What Scala does when the rewrite is impossible

`scalac` only rewrites a method that calls *itself* — it implements TCO as a
jump to the top of the same method, so **mutual recursion is not handled**:

```scala
def isEven(n: Long): Boolean = if (n == 0) true else isOdd(n - 1)
def isOdd(n: Long): Boolean  = if (n == 0) false else isEven(n - 1)
// StackOverflowError
```

The escape hatch is **trampolining** (`scala.util.control.TailCalls`): instead
of calling, return a *description* of the next call, and let a driver loop
execute descriptions. You have moved the call stack onto the heap by hand.
That is a real technique and a real cost — worth naming so juniors know the
option exists.

---

## Where this fits the decision framework

Recursion depth is a **stack budget** question (Block 3). TCO is one of the
few places where a language feature directly changes which algorithms are
practical:

| If your problem is… | TCO matters? |
| --- | --- |
| Tree/graph traversal, depth ~log n | No — depth is tiny |
| Parsers, interpreters, state machines over long input | **Yes** — depth scales with input |
| Anything naturally expressed as a fold over a huge list | **Yes** |
| Ordinary CRUD business logic | No |

Java's answer is "write a loop", and for most business code that is a perfectly
good answer. The cost is not performance; it is that some algorithms are far
clearer recursively, and Java makes you hand-compile them.

---

## Should the team pick Scala or Kotlin over Java?

Keep this honest — the demo is not an argument for switching.

| | Kotlin | Scala |
| --- | --- | --- |
| Learning curve from Java | gentle | steep |
| Killer features | null safety in the type system, coroutines, data classes, `tailrec` | a genuinely powerful type system, immutability by default, pattern matching, `@tailrec` |
| Hiring pool | large and growing (Android) | small |
| Compile speed | good | **slow** |
| Best fit | Android; teams wanting "Java without the sharp edges" | data engineering (Spark), correctness-heavy domains, teams that want FP |
| Risk | few | complexity ceiling is very high; codebases can become unreadable to newcomers |

**Kotlin's null safety is a bigger practical win than TCO** for most teams —
`String?` versus `String` as distinct types eliminates the single most common
runtime exception in Java. If you take one thing from this section into a real
decision, take that.

---

## Discussion prompts

1. Three languages, one bytecode format — what else might differ that you would
   not see from the outside? *(Null handling, generics/erasure behaviour,
   immutability defaults, operator overloading, coroutines vs threads.)*
2. Is `@tailrec` an optimisation or a type check? *(Closer to a type check: it
   is a compile-time assertion about your code's shape.)*
3. Java rejected TCO for two decades over stack traces and security. Was that
   the right call? *(Genuinely arguable — good discussion. Debuggability is a
   real feature; so is expressiveness.)*
4. Where else in this session did a language turn a runtime failure into a
   compile error? *(Block 1 typing; Block 4 Rust's borrow checker. Same
   pattern three times — that is the through-line.)*
