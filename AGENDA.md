# Choosing a Programming Language — 3-hour training

**Audience:** juniors and students who can already write code in at least one language.
**Format:** live demos, run from this repo, on the projector. Not slides.
**Promise to the room:** by the end you will be able to defend a language choice
with numbers, and you will know which arguments are real and which are folklore.

---

## The one idea

> There is no fastest language. There are only workloads, and each language is
> a different bet about which resource is scarce.

Everything in these three hours is evidence for that sentence.

---

## Timing at a glance

| Time | Block | Key artefact |
| --- | --- | --- |
| 0:00–0:20 | 0. Setup + the big table | `make bench` |
| 0:20–0:50 | 1. Types: static/dynamic, strong/weak | `make demo-typing` |
| 0:50–1:20 | 2. Compilation: AOT, JIT, interpreter | `make demo-jit` |
| 1:20–1:35 | **Break** | |
| 1:35–2:10 | 3. Memory: stack, heap, GC | `make demo-memory` `make demo-gc` |
| 2:10–2:35 | 4. Cold starts and cloud deployment | `make bench-startup` |
| 2:35–2:50 | 5. Energy and carbon | `make carbon` |
| 2:50–3:00 | 6. The decision framework | `docs/00-how-to-choose.md` |

Detailed facilitator timings, scripts and expected questions:
**[`docs/FACILITATOR-NOTES.md`](docs/FACILITATOR-NOTES.md)**

---

## Block 0 — Setup and the big table (0:00–0:20)

**Goal:** get a real measurement on screen in the first ten minutes, before any theory.

1. **(2 min)** Open with the question you are banning:
   *"Which language is fastest?"* — write it on the board, then cross it out.
2. **(3 min)** Kick off `make bench` and leave it running while you talk.
   It takes about two minutes and prints as it goes.
3. **(5 min)** While it runs, explain the four workloads and why there are four:

   | Workload | What it stresses | Why it is here |
   | --- | --- | --- |
   | `mandelbrot` | tight float loops, zero allocation | raw compiler/interpreter quality |
   | `binarytrees` | millions of tiny objects | allocator and garbage collector |
   | `wordfreq` | file I/O, strings, hash map, sort | what business code actually does |
   | `startup` | process spawn + runtime boot | serverless and CLI cold starts |

   All five languages implement the *same algorithm* and the harness verifies
   their output is byte-identical. Say that out loud — it is the difference
   between a benchmark and a rumour.
4. **(10 min)** Read the table together. Ask the room to spot the surprises
   *before* you explain them. There are four, and they carry the whole session:

   - **Python beats Java and TypeScript at `wordfreq`.** The 40x-slower
     language wins a realistic workload, because `str.split` and `Counter` are
     C code. *Lesson: you are benchmarking libraries as much as languages.*
   - **Java allocates faster than Rust** at `binarytrees` — and uses **14x the
     memory** to do it. *Lesson: speed and footprint are different axes.*
   - **Java's cold start is 30x Rust's.** *Lesson: the same runtime that wins
     on throughput loses on startup.*
   - **Python's cold start beats Node's.** *Lesson: nothing here is a single
     ranking.*

**Reference numbers** (this machine, 4-core Xeon 2.1 GHz — regenerate with
`make bench`; see [`docs/RESULTS.md`](docs/RESULTS.md)):

| | mandelbrot | binarytrees | wordfreq | startup | peak RSS (trees) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rust | 57 ms | 318 ms | **226 ms** | **1.5 ms** | **14 MB** |
| Go | **50 ms** | 464 ms | 299 ms | **1.5 ms** | 14 MB |
| Java | 114 ms | 281 ms | 771 ms | 46 ms | 197 MB |
| TypeScript | 86 ms | **240 ms** | 1290 ms | 29 ms | 98 MB |
| Python | 2300 ms | 4350 ms | 895 ms | 11 ms | 20 MB |

> **Facilitator note:** do not let anyone leave this block thinking the table is
> a ranking. It is four different rankings that disagree with each other. That
> disagreement *is* the curriculum.

---

## Block 1 — Types (0:20–0:50)

**Goal:** replace "typed vs untyped" with a two-axis model, and kill the belief
that TypeScript types exist at run time.

Run: `make demo-typing`

**(10 min) The two axes.** Draw this and keep it on the board all session:

```
                    STATIC (checked at compile time)
                                 ^
              Java, Go, Rust     |     (essentially empty)
              TypeScript*        |
    STRONG <---------------------+---------------------> WEAK
                     Python      |     JavaScript
                                 v
                    DYNAMIC (checked at run time)
```

- **static vs dynamic** = *when* are types checked
- **strong vs weak** = *how much* implicit coercion happens

These are independent. Most juniors have them fused into one axis.

**(12 min) The same bug in five languages.** The demo walks a payload where
`subtotal` arrived as `"100"` instead of `100`:

| Language | What happens | When you find out |
| --- | --- | --- |
| JavaScript | `"1005"`, free shipping wrongly applied | in a billing report, next quarter |
| Python | `TypeError` | at run time, at the right line |
| TypeScript | `"1005"` — *identical to JavaScript* | at run time, despite the types |
| Go / Java / Rust | will not compile | before it exists |

**(8 min) The erasure moment — the highest-value five minutes of the session.**
The demo prints the same line before and after `tsc`:

```ts
const total: number = order.subtotal + order.shipping;   // TypeScript
```
```js
const total = order.subtotal + order.shipping;           // emitted JavaScript
```

`interface Order` appears **zero** times in the output. Then say the rule:

> Types protect the **inside** of your program. At every boundary — HTTP, JSON,
> env vars, the database, message queues — you must **validate**, not annotate.

**Discussion prompt:** *"Given that, is TypeScript worth it?"*
Steer toward: yes, overwhelmingly — most bugs are internal refactoring bugs,
and that is exactly what it catches. But it buys you nothing at the boundary,
which is where the scary bugs live.

Deep dive: [`docs/01-typing.md`](docs/01-typing.md)

---

## Block 2 — Compilation: AOT, JIT, interpreter (0:50–1:20)

**Goal:** explain *why* Java is slow to start and fast in steady state, and why
that single fact drives most real architecture decisions.

Run: `make demo-jit`

**(8 min) The three strategies.** Build the vocabulary first:

- **Interpreter** (CPython): read bytecode, do what it says. No machine code.
- **JIT** (JVM HotSpot, V8): start interpreting, watch which code is hot,
  compile *that* to machine code while running, using facts only knowable at
  run time. Can **deoptimise** if an assumption breaks.
- **AOT** (Rust, Go): compile everything to machine code before shipping.
  What you run is what you built.

**(15 min) Watch the JIT work.** The demo runs the same function in batches and
charts per-batch time. Measured on this machine:

```
Rust      (AOT)  first batch  3.6 ms → steady  3.1 ms    flat  (1.2x)
Go        (AOT)  first batch  3.6 ms → steady  3.2 ms    flat  (1.1x)
Java      (JIT)  first batch  8.5 ms → steady  2.9 ms    2.9x faster as you watch
TypeScript(JIT)  first batch  8.4 ms → steady  3.8 ms    2.3x faster as you watch
Java -Xint       ─────────────  steady 47.7 ms           16x slower, JIT disabled
Python    (int)  ─────────────  steady 101.9 ms          35x slower, no JIT at all
```

Two things to land hard:

1. **Java's steady state (2.9 ms) beats Rust's (3.1 ms).** A JIT knows things
   an AOT compiler cannot — actual branch frequencies, actual types, which
   virtual calls are really monomorphic. "Compiled is faster than JIT" is
   folklore. *The JIT's problem is not its ceiling, it is how long it takes to
   get there.*
2. **`java -Xint` is 16x slower than `java`.** That gap is what the JIT is
   worth. Then note: that 16x is roughly the gap between Python and the
   compiled languages — because it is the same gap, for the same reason.

**(7 min) The consequence.** Ask: *"Where does a warm-up cost hurt most?"*
Lead the room to: anything short-lived. Lambda functions, CLI tools, batch
jobs, scale-to-zero pods, CI steps. And anything long-lived is fine — which is
why the JVM dominates in long-running backend services and is painful in
serverless.

Deep dive: [`docs/02-compilation.md`](docs/02-compilation.md)

---

## Break (1:20–1:35)

---

## Block 3 — Memory: stack, heap, garbage collection (1:35–2:10)

Run: `make demo-memory` then `make demo-gc`

**(10 min) Stack vs heap, shown by the compiler.** Go's escape analysis makes
this observable rather than theoretical:

```
go build -gcflags='-m' demos/stack-heap/escape.go
  demos/stack-heap/escape.go:40:7: &Point{...} escapes to heap
```

Same struct, same fields, same arithmetic — the only difference is whether a
pointer escaped the function:

```
stack-allocated :   13.1 ms
heap-allocated  :  321.1 ms      24.4x slower, plus 20M objects for the GC
```

Rules to state plainly:
- **Stack:** bump a pointer, freed automatically on return, ~free, but small
  and fixed (8 MB typical). Depth is a budget.
- **Heap:** large and flexible, but every object costs an allocation now and a
  collection later.

**(8 min) What one object actually costs.** Measured directly, 1,000,000 live
nodes each holding two references:

| Language | bytes/node | Why |
| --- | ---: | --- |
| Go | **16.0** | two pointers, no header at all |
| Java | 24.8 | 12-byte header + 2 compressed refs + padding |
| Rust | 32.1 | 16 bytes of data, rounded to the allocator's 32-byte class |
| Python (`__slots__`) | 48.4 | PyObject header + two pointers |
| Node | 80.0 | hidden-class ptr + properties + elements stores |
| Python (plain class) | **94.6** | the per-instance `__dict__` |

The Python row is the actionable one: **adding `__slots__` halves it.**

**(12 min) Garbage collectors, judged by tail latency.** Same code, same heap,
different collector. Point at `max`, not `mean`:

| Collector | mean | p99 | max | character |
| --- | ---: | ---: | ---: | --- |
| SerialGC | 1.5 µs | 5.3 µs | **12111 µs** | lowest overhead, worst pauses |
| ParallelGC | 1.5 µs | 4.2 µs | 11865 µs | throughput king, stops the world |
| G1GC (default) | 4.8 µs | 37.8 µs | 6972 µs | balanced, region-based |
| ZGC | 7.3 µs | 52.0 µs | **1222 µs** | concurrent, 10x better worst case |
| Go (GOGC=100) | 5.6 µs | 32.4 µs | 1611 µs | tuned for pauses over throughput |
| Go (GOGC=400) | 4.7 µs | 16.8 µs | 856 µs | collect less often |
| Go (GOGC=off) | **25.9 µs** | 116 µs | 5451 µs | *slower* — see below |

Three things to say:
1. **The mean barely moves.** If you only look at averages you will conclude GC
   choice does not matter. It matters enormously — just not in the mean.
2. **`GOGC=off` is slower, not faster.** Turning the collector off lets the live
   heap sprawl out of cache. "Less GC" ≠ "faster"; a compacting collector also
   buys you locality. Great moment to puncture a common intuition.
3. **Rust is absent from this table** because it has no collector. Its cost is
   spread evenly across every `drop`, so it shows up in the mean, never as a
   pause. That is the real reason Rust attracts latency-critical work.

**(5 min) The container rule.** The single most common JVM production incident:
a JVM that does not know it is in a container sizes its heap from the *host's*
memory and gets OOM-killed. Fix: `-XX:MaxRAMPercentage=75` (Java),
`GOMEMLIMIT` (Go). Size limits from **RSS**, never from heap.

Deep dive: [`docs/03-memory.md`](docs/03-memory.md)

---

## Block 4 — Cold starts and cloud deployment (2:10–2:35)

Run: `make bench-startup`

**(8 min) The cold-start table.** Measured, doing nothing at all:

| Language | cold start | baseline RSS | container image (typical) |
| --- | ---: | ---: | ---: |
| Rust | **1.5 ms** | 14 MB | 5–10 MB (scratch/distroless) |
| Go | **1.5 ms** | 14 MB | 10–20 MB (scratch/distroless) |
| Python | 11 ms | 14 MB | 50–120 MB (slim) |
| Node | 29 ms | 44 MB | 60–150 MB (slim/alpine) |
| Java | 46 ms | 40 MB | 180–400 MB (JRE base) |

**(10 min) Why this is the most decision-relevant table in the session.**
Work through the multipliers:
- **Serverless:** you pay cold start on *every* scale-out event. A 46 ms JVM
  boot on a 100 ms function is a 46% tax.
- **Autoscaling:** cold start is how fast you can absorb a traffic spike.
- **Rolling deploys:** cold start × number of pods = deploy duration.
- **Bin packing:** baseline RSS decides how many replicas fit per node, which
  decides your node count, which is most of your bill.

Then give the mitigations, so nobody leaves thinking "never use Java":
- Java: **AppCDS** (~30% off), **GraalVM native-image** (~5 ms, at the cost of
  build complexity and reflection config), or simply **keep the JVM warm** —
  a long-lived pod behind a queue makes the whole problem disappear.
- Node: **bundle to a single file.** Module resolution over a deep
  `node_modules` tree often costs more than V8's boot.
- Python: avoid heavy imports at module scope (`import pandas` is ~200 ms).

**(7 min) Deployment checklist.** Walk [`docs/04-cold-start-cloud.md`](docs/04-cold-start-cloud.md):
multi-stage builds, distroless/scratch, pinned base images, health probes
matched to real start-up time, and the memory-limit rules from Block 3.

---

## Block 5 — Energy and carbon (2:35–2:50)

Run: `make carbon`

**(6 min) The model, with its assumptions on screen.** You cannot read joules
from userspace, so this uses the standard published model:

```
energy = CPU-seconds x (TDP / cores) x utilisation x PUE
CO2e   = energy(kWh) x grid intensity (gCO2e/kWh)
```

Every constant is a flag. Say clearly: **absolute values are soft, the ranking
is robust.** 4x the CPU-seconds is 4x the energy under any assumptions.

**(9 min) The honest conclusion.** At 50M executions/month, `wordfreq`:

```
rust        225 ms CPU     3.93 kg CO2e/month
typescript 1504 ms CPU    26.23 kg CO2e/month
→ switching saves ~22 kg/month = 0.27 tonnes/year
```

Now puncture it, in this order:

1. **0.27 t/year is less than one transatlantic flight.** At low volume,
   language choice is climate *noise*. Do not let anyone justify a rewrite on
   carbon grounds at 100 runs/month.
2. **Changing region beats changing language by ~17x.**
   `--region eu-north-1` cuts the same workload's emissions ~17x with **zero
   code change**. Run it live.
3. **The real carbon argument is density, not CPU.** 1/10th the memory means
   1/10th the machines, and you avoid the *embodied* carbon of hardware you
   never bought. That is why the peak-RSS column matters more than it looks.
4. **A carbon number without its assumptions is a vibe, not a measurement.**

Deep dive: [`docs/05-carbon.md`](docs/05-carbon.md)

---

## Block 6 — The decision framework (2:50–3:00)

Hand out / display [`docs/00-how-to-choose.md`](docs/00-how-to-choose.md).

**The order the questions must be asked in** — the point is that performance is
question five, not question one:

1. **What does the team already know?** A language your team is fluent in beats
   a faster one they are learning, almost always.
2. **What is the ecosystem?** ML → Python. Browser → JS/TS. Kubernetes
   tooling → Go. Android → Kotlin. This decides more than speed does.
3. **What is the failure cost?** Payments and medical devices justify Rust's
   strictness. An internal dashboard does not.
4. **What is the execution shape?** Short-lived (CLI, Lambda) → AOT.
   Long-lived (service) → JIT is fine and often better.
5. **Only now: is it actually CPU-bound?** Most services are I/O-bound and
   spend their lives waiting on a database. For those, language speed is nearly
   irrelevant and the `wordfreq` result is your evidence.

**Closing exercise (5 min).** Give the room three scenarios and have them argue:

- *A CLI tool run 500 times a day by developers.* → cold start dominates; Go or
  Rust; Java is the wrong answer for a reason they can now name.
- *A REST API doing 3 database queries per request.* → I/O-bound; pick for
  ecosystem and team; almost any of the five is fine.
- *A nightly job processing 2 TB.* → throughput and memory; JVM or Go or Rust;
  Python only if the heavy lifting is in NumPy/Polars (call back to `wordfreq`).

**Last slide, one sentence:**

> Measure your workload, on your hardware, with your data — then choose.
> Everything else is folklore.

---

## Preparation checklist

Run this **the day before**, on the machine you will present from:

```bash
make setup     # deps + generate the corpus
make bench     # regenerates docs/RESULTS.md with YOUR numbers
make verify    # runs every demo once, end to end
```

The numbers quoted above are from a 4-core Xeon @ 2.1 GHz. Yours will differ —
the *ratios* and the *shape* are what the session is about, and those hold up.
