# Block 2 — Compilation: AOT, JIT, and interpreters

**Run:** `make demo-jit`

---

## Three strategies for turning source into behaviour

### Interpreter (CPython)

Parse to bytecode once, then a loop reads each instruction and does what it
says. **No machine code is ever produced for your code.**

Every `a + b` goes through: fetch opcode → dispatch → unbox two `PyObject*` →
look up `__add__` → allocate a result object → push it. That is dozens of
machine instructions for one addition. This is why Python is ~35–46x slower on
tight loops, and no amount of clever coding closes that gap — you have to leave
the interpreter (NumPy, Polars, a C extension).

CPython 3.11+ has a *specialising adaptive interpreter* (PEP 659) that rewrites
hot bytecodes into type-specialised versions. It is a real 10–25% win, but it
is not a compiler. CPython 3.13+ ships an experimental JIT.

### JIT (JVM HotSpot, V8)

Start by interpreting. Count how often each method runs and each loop
back-edges. When something is hot, **compile it to machine code while the
program runs**, using information only available at run time:

- which types actually flow through this call site
- which branches are actually taken
- which virtual calls are actually monomorphic (so they can be inlined)

Both use **tiered compilation**:

| | JVM | V8 |
| --- | --- | --- |
| Tier 0 | bytecode interpreter | Ignition (interpreter) |
| Tier 1 | C1 (fast, lightly optimised) | Sparkplug (baseline) |
| Tier 2 | — | Maglev (mid-tier) |
| Tier 3 | C2 (slow, aggressive) | TurboFan (aggressive) |

The aggressive tier makes **speculative** optimisations: "this variable has
always been an integer, so I will compile assuming it always is." If that ever
turns out false, the code **deoptimises** — it bails back to the interpreter and
recompiles. That is what a mid-run spike in the demo usually is.

### AOT (Rust, Go)

Compile everything to machine code before shipping. What you run is what you
built. No warm-up, no deopt, no compiler in the process.

The compiler cannot know run-time facts, so it must be conservative: it cannot
prove that a virtual call is monomorphic, so it may not inline it. This is
exactly the information a JIT has and an AOT compiler does not.

---

## What the demo shows

Same function, run in batches, timed per batch inside one process (so process
startup is excluded and only warm-up is visible):

```
Rust      (AOT)  first batch  3.6 ms → steady  3.1 ms    flat  (1.2x)
Go        (AOT)  first batch  3.6 ms → steady  3.2 ms    flat  (1.1x)
Java      (JIT)  first batch  8.5 ms → steady  2.9 ms    2.9x faster as you watch
TypeScript(JIT)  first batch  8.4 ms → steady  3.8 ms    2.3x faster as you watch
Java -Xint       ────────────── steady 47.7 ms           16x slower (JIT disabled)
Python    (int)  ────────────── steady 101.9 ms          35x slower (no JIT at all)
```

### Three conclusions, in order of how surprising they are

**1. Java's steady state beat Rust's.** 2.9 ms vs 3.1 ms. This kills the
folklore that "compiled is faster than JIT". A JIT has *more* information than
an AOT compiler, and on a hot monomorphic loop it can use it. The JIT's problem
is not its ceiling — it is **how long it takes to get there**.

> Caveat to state honestly: this is one microbenchmark on one kernel. Across
> the whole benchmark suite Rust and Go generally win, and Rust wins decisively
> on memory. But "JIT can match or beat AOT in steady state" is true and worth
> knowing.

**2. `java -Xint` is 16x slower than `java`.** That gap *is* the JIT. Then point
out: 16x is about the same as the Python gap — because it is the same gap, for
the same reason. Python is roughly "Java with the JIT permanently off".

**3. The AOT lines are flat, but not perfectly flat.** Rust and Go show ~1.1–1.2x
on the first batch. That is not compilation — it is page faults, cold caches,
and CPU frequency ramping. Worth naming: **not every improvement over time is a
JIT.** It is also a nice lesson in benchmark scepticism.

---

## Why this drives architecture

The cost you care about is not "is the JIT good" — it is **how much of your
process's life is spent warming up.**

| Execution shape | Warm-up as % of life | Verdict |
| --- | --- | --- |
| Lambda, 100 ms invocation | ~50%+ | AOT. The JVM never gets to be fast. |
| CLI tool, 200 ms | ~100% | AOT. You only ever pay the bad part. |
| CI step, 5 s | ~10% | Either. |
| HTTP service, 30 days uptime | ~0% | JIT is fine, and often better. |

This is *the* reason the JVM dominates long-lived backend services and is
painful in serverless — and why Go took over cloud tooling, which is almost
entirely short-lived processes.

---

## Closing the gap in both directions

### Making AOT smarter — profile-guided optimisation (PGO)

Run the binary, record a profile, recompile using it. This gives the AOT
compiler the run-time facts it was missing.

```bash
go build -pgo=default.pgo ./...     # Go 1.21+, typically 2-7%
```
Rust supports PGO via `-Cprofile-generate` / `-Cprofile-use`.

### Making JIT start faster

| Technique | Effect | Cost |
| --- | --- | --- |
| **CDS** (Java) | already on by default; worth ~31% of startup — see below | none, it is the default |
| **AppCDS** (Java) | extends CDS to *your* classes; scales with class count | small build step; needs a JAR |
| **GraalVM native-image** | ~46 ms → ~5 ms; AOT-compiles the JVM app | slow builds, reflection config, lower peak throughput |
| **CRaC / checkpoint-restore** | restore a warmed-up JVM from a snapshot | infrastructure complexity |
| **Bundling** (Node) | often the biggest single Node win | trivial; do it always |
| **Keep it warm** | eliminates the problem entirely | you pay for idle capacity |

### Class Data Sharing, demonstrated honestly

Modern JDKs ship a **default CDS archive**: the JDK's own core classes,
pre-parsed into a memory-mappable image. It is already enabled — that is what
`sharing` means in `java -version` output. The clean way to show what it is
worth is to turn it **off**:

```bash
java              -cp build/java Hello 1     # 45.7 ms  (CDS on, the default)
java -Xshare:off  -cp build/java Hello 1     # 66.2 ms  (CDS off)
#                                            # => CDS is already saving ~31%
```

**AppCDS** is the same trick applied to *your* application's classes. Two
caveats that matter if you demo it:

1. It needs a **JAR**; `-cp <directory>` fails with
   `Cannot have non-empty directory in paths`.
2. Its benefit scales with **how many application classes you load**. On our
   one-class `Hello` it measures as **zero**, because there is nothing to
   share beyond the JDK classes CDS already covers. On a Spring Boot service
   loading thousands of classes it is a genuine 20–40% win.

```bash
jar --create --file hello.jar --main-class Hello -C build/java Hello.class
java -XX:ArchiveClassesAtExit=app.jsa -jar hello.jar 1     # record
java -XX:SharedArchiveFile=app.jsa    -jar hello.jar 1     # replay
```

That "zero on a trivial app, large on a real one" result is worth showing
rather than hiding: it is a clean example of an optimisation whose value is
entirely a function of your workload's shape.

**Note the convergence:** AOT languages are adding profile feedback (PGO), and
JIT languages are adding ahead-of-time compilation (Graal, CRaC). The two camps
are meeting in the middle, which is a good sign that neither strategy is simply
"right".

---

## Build time is a real cost too

Nobody puts this on the slide, but it dominates your day:

| | Clean build of the benchmark programs |
| --- | --- |
| Go | very fast — designed around compilation speed |
| Java | fast (`javac` does little optimisation; the JIT does it later) |
| TypeScript | fast, and skippable — Node 22 strips types natively |
| Rust | **slowest by a wide margin** — LLVM does at build time what a JIT does at run time |
| Python | none |

Rust's slow builds and fast binaries are the same fact viewed from two angles:
**AOT moves work from every run to one build.** If you build once and run a
billion times, that is a spectacular trade. If you are iterating every 30
seconds, it is painful — and that pain is a legitimate input to a language
decision, not a detail.

---

## Discussion prompts

1. Your Lambda has a p50 of 40 ms and a p99 of 900 ms. What is your first
   hypothesis, and how would you test it?
2. Why might a JIT beat an AOT compiler on a virtual-call-heavy workload?
   *(It can observe that the call is monomorphic in practice and inline it.)*
3. You inherit a Java batch job that runs for 12 hours. Is startup worth
   optimising? *(No. Optimise the collector and throughput instead.)*
4. When would you accept GraalVM's build complexity? *(Serverless, CLI tools,
   scale-to-zero — anywhere cold start is in the user's critical path.)*
