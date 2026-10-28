# Block 2 — Compilation: AOT, JIT, and interpreters

**Run:** `make demo-jit`

---

## Three strategies for turning source into behaviour

### Interpreter (CPython)

Parse to bytecode once, then a loop reads each instruction and does what it
says. **No machine code is ever produced for your code.**

Every `a + b` goes through: fetch opcode → dispatch → unbox two `PyObject*` →
look up `__add__` → allocate a result object → push it. That is dozens of
machine instructions for one addition. This is why Python is ~40x slower on
tight loops, and no amount of clever coding closes that gap — you have to leave
the interpreter (NumPy, Polars, a C extension).

CPython 3.11+ has a *specialising adaptive interpreter* (PEP 659) that rewrites
hot bytecodes into type-specialised versions. It is a real 10–25% win, but it
is not a compiler. CPython 3.13+ ships an experimental JIT.

### JIT (JVM HotSpot, .NET RyuJIT, V8)

Start by interpreting. Count how often each method runs and each loop
back-edges. When something is hot, **compile it to machine code while the
program runs**, using information only available at run time:

- which types actually flow through this call site
- which branches are actually taken
- which virtual calls are actually monomorphic (so they can be inlined)

All three use **tiered compilation**:

| | JVM | .NET | V8 |
| --- | --- | --- | --- |
| Tier 0 | bytecode interpreter | quick, unoptimised JIT (no interpreter) | Ignition (interpreter) |
| Tier 1 | C1 (fast, lightly optimised) | — | Sparkplug (baseline) |
| Tier 2 | — | — | Maglev (mid-tier) |
| Tier 3 | C2 (slow, aggressive) | tier-1 JIT, fed by dynamic PGO | TurboFan (aggressive) |

(.NET differs in one way worth naming: it never interprets. The first call of
a method goes through a fast, unoptimised JIT; hot methods are re-JITted with
profile data. Hot loops are promoted mid-flight via on-stack replacement.)

The aggressive tier makes **speculative** optimisations: "this variable has
always been an integer, so I will compile assuming it always is." If that ever
turns out false, the code **deoptimises** — it bails back to the interpreter and
recompiles. That is what a mid-run spike in the demo usually is.

### AOT (Rust, C++, Go)

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
Rust      (AOT)  first batch  4.6 ms → steady  4.6 ms    flat  (1.0x)
C++       (AOT)  first batch  4.9 ms → steady  4.8 ms    flat  (1.0x)
Go        (AOT)  first batch  5.1 ms → steady  5.1 ms    flat  (1.0x)
C#        (JIT)  first batch  7.0 ms → steady  4.6 ms    1.5x faster as you watch
Java      (JIT)  first batch 11.6 ms → steady  5.3 ms    2.2x faster as you watch
TypeScript(JIT)  first batch 12.8 ms → steady  5.4 ms    2.4x faster as you watch
Java -Xint       ────────────── steady 49.5 ms            9x slower than Java (JIT disabled)
Python    (int)  ────────────── steady 181.0 ms          34x slower than Java (no JIT at all)
```

(`docs/sample-output/jit-warmup.txt` has the full chart. "Steady" is the best
of the last five batches.)

### Three conclusions, in order of how surprising they are

**1. The JIT languages end up where the AOT languages start.** C# reaches
4.6 ms — a tie with Rust — and Java 5.3 ms, within 15%. A JIT has *more*
information than an AOT compiler, and on a hot monomorphic loop it can use it.
This kills the folklore that "compiled is faster than JIT" at steady state. The
JIT's problem is not its ceiling — it is **how long it takes to get there**
(C# needed 1.5x its first batch to settle, Java 2.2x).

> Caveat to state honestly: this is one microbenchmark on one kernel, and it
> does not reproduce the strongest version of the claim. On our original
> reference machine Java's steady state *beat* Rust's (2.9 ms vs 3.1 ms); on
> this one, three repeat runs put Rust at 4.5–4.7 ms and Java at 5.3–5.5 ms. A
> 7% gap flipped sign when the hardware changed, so do not build an argument on
> it. What survives is "within ~15%". Across the whole benchmark suite, Rust and
> C++ generally win, and Rust wins decisively on memory.

**2. `java -Xint` is 9x slower than `java`.** That gap *is* the JIT. Python's
gap to Java (34x) is larger, but it is the same kind of gap: Python is roughly
"a slower interpreter with no JIT at all".

**3. The AOT lines are flat, but not perfectly flat.** Rust, C++ and Go show up
to ~1.05x on the first batch. That is not compilation — it is page faults, cold
caches, and CPU frequency ramping. Worth naming: **not every improvement over
time is a JIT.** It is also a nice lesson in benchmark scepticism.

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
| **CDS** (Java) | already on by default; worth ~37% of startup — see below | none, it is the default |
| **AppCDS** (Java) | extends CDS to *your* classes; scales with class count | small build step; needs a JAR |
| **GraalVM native-image** | ~69 ms → ~5 ms; AOT-compiles the JVM app | slow builds, reflection config, lower peak throughput |
| **ReadyToRun / Native AOT** (.NET) | ReadyToRun precompiles IL to cut JIT time; Native AOT removes the JIT and most of the runtime boot (~44 ms here) | larger binaries, restricted reflection (AOT) |
| **CRaC / checkpoint-restore** | restore a warmed-up JVM from a snapshot | infrastructure complexity |
| **Bundling** (Node) | often the biggest single Node win | trivial; do it always |
| **Keep it warm** | eliminates the problem entirely | you pay for idle capacity |

### Class Data Sharing, demonstrated honestly

Modern JDKs ship a **default CDS archive**: the JDK's own core classes,
pre-parsed into a memory-mappable image. It is already enabled — that is what
`sharing` means in `java -version` output. The clean way to show what it is
worth is to turn it **off**:

```bash
java              -cp build/java Hello 1     # 75.4 ms  (CDS on, the default)
java -Xshare:off  -cp build/java Hello 1     # 119.7 ms (CDS off)
#                                            # => CDS is already saving ~37%
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

Measured on the 60-line `binarytrees` program, one source file, no dependencies
(median of 3 builds):

| | Build of one benchmark program | Note |
| --- | ---: | --- |
| Go | 0.07 s | warm build cache; **5.9 s** with `-a`, rebuilding the standard library |
| Rust | 0.26 s | `rustc -O` |
| Java | 0.74 s | `javac` does little optimisation; the JIT does it later |
| C++ | 1.45 s | `g++ -O2 -std=c++20`; most of it is parsing standard headers |
| TypeScript | 1.59 s | `tsc` over the whole project; skippable, Node 22 strips types natively |
| C# | 2.57 s | `dotnet build`; mostly MSBuild and restore, not the compiler |
| Python | none | |

**Do not read a ranking into this.** A single file with no dependencies tells
you almost nothing about a real project, and it does *not* support the common
claim that Rust builds are slow: `rustc -O` was the second-fastest here. That
folklore is about large codebases — hundreds of crates, generics instantiated
across them, LTO — which this repo does not contain, so we did not measure it.
C++ has the same reputation for the same reason (headers and templates scale
badly). The honest conclusion is "measure your own build", and the useful
number is your **incremental** build, not a clean build of a toy.

The trade underneath is real, though. Slow builds and fast binaries are the
same fact viewed from two angles: **AOT moves work from every run to one
build.** If you build once and run a billion times, that is a spectacular
trade. If you are iterating every 30 seconds, it is painful — and that pain is
a legitimate input to a language decision, not a detail.

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
