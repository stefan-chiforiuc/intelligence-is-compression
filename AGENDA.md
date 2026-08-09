# Choosing a Programming Language — training agenda

**Audience:** juniors and students who can already write code in at least one language.
**Format:** live demos, run from this repo, on the projector. Not slides.
**Promise to the room:** by the end you will be able to defend a language choice
with numbers, and you will know which arguments are real and which are folklore.

---

## The one idea

> There is no fastest language. There are only workloads, and each language is
> a different bet about which resource is scarce.

Everything in this session is evidence for that sentence.

---

## ⚠️ Read this before you plan your slot

The material here now runs to roughly **5 hours** if you demo everything at a
comfortable pace. That is deliberate — it is a **library**, not a script. Pick
a variant:

| Variant | Length | Contents |
| --- | --- | --- |
| **A — Core** | 3:00 | Blocks 0–3, a compressed concurrency block, cold start + carbon merged, framework, close. No databases, no parallelism-cost block. |
| **B — Concurrency-heavy** | 4:00 | A + the full concurrency track (4, 4b) including the 20-user API race. Drops the carbon block to 8 minutes. |
| **C — Full** | 5:00 | Everything, including databases (5b) and the GCP live demo. Needs two breaks and a hard stop. |

**Recommendation:** run **B** over two sessions rather than C in one sitting.
Three hours is already at the limit of what juniors absorb; five is not a
training, it is an endurance test. A natural split is:

- **Session 1 — the language:** Blocks 0, 1, 2, 2b, 3 (types, compilation,
  memory). ~2:15.
- **Session 2 — the system:** Blocks 4, 4b, 5, 5b, 6, 7 (concurrency,
  databases, cloud, the framework, the close). ~2:30.

That split is also pedagogically cleaner: session 1 is "what does this language
do to my code", session 2 is "what happens when many things run at once".

### Variant A — Core (3:00)

| Time | Block | Command |
| --- | --- | --- |
| 0:00–0:15 | 0. Setup + the big table | `make bench` |
| 0:15–0:40 | 1. Types: static/dynamic, strong/weak | `make demo-typing` |
| 0:40–1:05 | 2. Compilation: AOT, JIT, interpreter | `make demo-jit` |
| 1:05–1:15 | 2b. Same JVM, different language: tail calls | `make demo-tailcalls` |
| 1:15–1:25 | **Break** | |
| 1:25–1:55 | 3. Memory: stack, heap, GC | `make demo-memory` `make demo-gc` |
| 1:55–2:25 | 4. Concurrency and parallelism | `make demo-concurrency` |
| 2:25–2:45 | 5. Cold starts, cloud and carbon *(merged)* | `make bench-startup` `make carbon` |
| 2:45–2:52 | 6. The decision framework | `docs/00-how-to-choose.md` |
| 2:52–3:00 | 7. Closing note: robust vs antifragile | `docs/08-robust-vs-antifragile.md` |

### Variant B — Concurrency-heavy (4:00)  ← recommended

| Time | Block | Command |
| --- | --- | --- |
| 0:00–0:20 | 0. Setup + the big table | `make bench` |
| 0:20–0:50 | 1. Types | `make demo-typing` |
| 0:50–1:15 | 2. Compilation: AOT, JIT, interpreter | `make demo-jit` |
| 1:15–1:28 | 2b. Tail calls: Java vs Scala vs Kotlin | `make demo-tailcalls` |
| 1:28–1:43 | **Break** | |
| 1:43–2:15 | 3. Memory: stack, heap, GC | `make demo-memory` `make demo-gc` |
| 2:15–2:45 | 4. Concurrency: cores and races | `make demo-concurrency` |
| 2:45–3:05 | **4b. When NOT to parallelise + virtual threads** | `make demo-parallel-cost` |
| 3:05–3:15 | **Break** | |
| 3:15–3:35 | **4c. 20 users, one shared array** | `make demo-api-race` |
| 3:35–3:47 | 5. Cold starts + cloud | `make bench-startup` |
| 3:47–3:52 | 6. Carbon *(compressed)* | `make carbon` |
| 3:52–3:56 | 7. The decision framework | `docs/00-how-to-choose.md` |
| 3:56–4:00 | 8. Closing note: robust vs antifragile | `docs/08-robust-vs-antifragile.md` |

### Variant C — Full (5:00, or split across two sessions)

Variant B, plus **5b. Databases** (30 min, `make demo-db`) after Block 5, and
optionally the 15-minute GCP live demo from
[`GCP-RUNBOOK.md`](demos/db-scaling/GCP-RUNBOOK.md).

Facilitator timings, what to cut when you overrun, and expected questions:
**[`docs/FACILITATOR-NOTES.md`](docs/FACILITATOR-NOTES.md)**

### The three optional blocks, at a glance

| Block | Doc | The one number |
| --- | --- | --- |
| **4b** When not to parallelise | [`09`](docs/09-when-to-parallelize.md) | `parallelStream` was **16x slower** on 10,000 cheap elements |
| **4b** Virtual threads | [`09`](docs/09-when-to-parallelize.md) | **15.2x faster** on blocking I/O, **1.02x** on CPU work |
| **4c** 20-user API race | [`09`](docs/09-when-to-parallelize.md) | **3,874 of 200,000 items lost**, HTTP 204 every time |
| **5b** Databases | [`10`](docs/10-databases-and-scaling.md) | pool of 200 buys **0.38x throughput for 70x latency**; naive booking **confirmed 400, stored 25** |

---

## Block 0 — Setup and the big table (15–20 min)

**Goal:** get a real measurement on screen in the first ten minutes, before any theory.

1. **(2 min)** Open with the question you are banning:
   *"Which language is fastest?"* — write it on the board, then cross it out.
2. **(3 min)** Kick off `make bench` and leave it running while you talk.
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
4. **(5–10 min)** Read the table together. Ask the room to spot the surprises
   *before* you explain them.

**Reference numbers** (4-core Xeon @ 2.1 GHz — regenerate with `make bench`;
see [`docs/RESULTS.md`](docs/RESULTS.md)):

| | mandelbrot | binarytrees | wordfreq | startup | peak RSS (trees) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rust | 57 ms | 318 ms | **226 ms** | **1.5 ms** | **14 MB** |
| Go | **50 ms** | 464 ms | 299 ms | **1.5 ms** | 14 MB |
| Java | 114 ms | 281 ms | 771 ms | 46 ms | 197 MB |
| TypeScript | 86 ms | **240 ms** | 1290 ms | 29 ms | 98 MB |
| Python | 2300 ms | 4350 ms | 895 ms | 11 ms | 20 MB |

The four surprises that carry the session:

- **Python beats Java and TypeScript at `wordfreq`** — you are benchmarking
  libraries as much as languages.
- **Java allocates faster than Rust** at `binarytrees`, using 14x the memory.
- **Java's cold start is 30x Rust's.**
- **Python's cold start beats Node's.**

> **Facilitator note:** do not let anyone leave this block thinking the table is
> a ranking. It is four rankings that disagree. That disagreement *is* the
> curriculum.

---

## Block 1 — Types (25–30 min)

**Run:** `make demo-typing`

**(8 min) The two axes.** Draw this and keep it on the board all session:

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

**(10 min) The same bug in five languages.** Payload has `subtotal` as `"100"`:

| Language | What happens | When you find out |
| --- | --- | --- |
| JavaScript | `"1005"`, free shipping wrongly applied | in a billing report, next quarter |
| Python | `TypeError` | at run time, at the right line |
| TypeScript | `"1005"` — *identical to JavaScript* | at run time, despite the types |
| Go / Java / Rust | will not compile | before it exists |

**(7 min) The erasure moment — the highest-value five minutes of the session.**

```ts
const total: number = order.subtotal + order.shipping;   // TypeScript
```
```js
const total = order.subtotal + order.shipping;           // emitted JavaScript
```

`interface Order` appears **zero** times in the output. Then state the rule:

> Types protect the **inside** of your program. At every boundary — HTTP, JSON,
> env vars, the database, message queues — you must **validate**, not annotate.

Deep dive: [`docs/01-typing.md`](docs/01-typing.md)

---

## Block 2 — Compilation: AOT, JIT, interpreter (25–30 min)

**Run:** `make demo-jit`

**(8 min) The three strategies:** interpreter (CPython), JIT (HotSpot, V8),
AOT (Rust, Go). Cover tiered compilation and deoptimisation.

**(12 min) Watch the JIT work.** Measured on this machine:

```
Rust      (AOT)  first batch  3.6 ms → steady  3.1 ms    flat  (1.2x)
Go        (AOT)  first batch  3.6 ms → steady  3.2 ms    flat  (1.1x)
Java      (JIT)  first batch  8.5 ms → steady  2.9 ms    2.9x faster as you watch
TypeScript(JIT)  first batch  8.4 ms → steady  3.8 ms    2.3x faster as you watch
Java -Xint       ─────────────  steady 47.7 ms           16x slower, JIT disabled
Python    (int)  ─────────────  steady 101.9 ms          35x slower, no JIT at all
```

Two things to land hard:

1. **Java's steady state (2.9 ms) beats Rust's (3.1 ms).** "Compiled is faster
   than JIT" is folklore. The JIT's problem is time-to-peak, not peak.
2. **`java -Xint` is 16x slower than `java`.** That gap is what the JIT is
   worth — and it is roughly the Python gap, for the same reason.

**(7 min) The consequence.** Warm-up as a fraction of process life decides
everything: Lambda and CLI tools want AOT; a 30-day service does not care.

Deep dive: [`docs/02-compilation.md`](docs/02-compilation.md)

---

## Block 2b — Same runtime, different language: tail calls (10–15 min)

**Run:** `make demo-tailcalls`
**Setup once (needs network):** `bash tools/get_jvm_langs.sh`

**Goal:** break the belief that "we're a JVM shop" settles anything.

The same function, recursive call in tail position, `sumTail(10_000_000)`:

| Language | Result | Bytecode emitted |
| --- | --- | --- |
| Java | **`StackOverflowError`** at ~14,119 frames | `invokestatic sumTail` |
| Scala (`@tailrec`) | `50000005000000` | **`goto 0`** |
| Kotlin (`tailrec`) | `50000005000000` | **`goto 0`** |

The demo prints that bytecode live with `javap -c`. Same JVM, same JIT, same
GC, same bytecode format — the **compiler** is what changed.

**Three beats:**

1. **TCO is a narrow rewrite of a narrow shape.** Scala's `factorial` still
   overflows, because the multiply happens *after* the call returns. Not magic.
2. **`@tailrec` is enforcement, not optimisation.** scalac would optimise
   anyway; the annotation makes it *mandatory*. Adding `+ 0` after the call
   fails the build:
   ```
   error: could not optimize @tailrec annotated method sumBroken:
          it contains a recursive call not in tail position
   ```
   A silent stack-overflow cliff became a compile error. **That is the same
   move as Block 1 and Block 4** — point at it explicitly.
3. **Why not Java?** Tail calls are not a JVM instruction; the verifier and
   stack-walking model assume frames exist. Scala and Kotlin do not ask the JVM
   for anything — they compile the recursion into a loop themselves.

**Do not oversell it.** For most teams **Kotlin's null safety** (`String?` vs
`String` as distinct types) is a far bigger practical win than TCO. Say so.

Deep dive: [`docs/07-jvm-languages-tail-calls.md`](docs/07-jvm-languages-tail-calls.md)

---

## Break (10–15 min)

---

## Block 3 — Memory: stack, heap, garbage collection (30–35 min)

**Run:** `make demo-memory` then `make demo-gc`

**(8 min) Stack vs heap, shown by the compiler.** Go's escape analysis:

```
go build -gcflags='-m' demos/stack-heap/escape.go
  escape.go:40:7: &Point{...} escapes to heap
```
```
stack-allocated :   13.1 ms
heap-allocated  :  321.1 ms      24.4x slower, plus 20M objects for the GC
```

**(7 min) What one object costs.** 1,000,000 live nodes, two references each —
the *data* is 16 bytes in every language:

| Language | bytes/node | Why |
| --- | ---: | --- |
| Go | **16.0** | two pointers, no header at all |
| Java | 24.8 | 12-byte header + 2 compressed refs + padding |
| Rust | 32.1 | 16 B data, rounded to the allocator's 32-byte class |
| Python (`__slots__`) | 48.4 | PyObject header + two pointers |
| Node | 80.0 | hidden-class ptr + properties + elements |
| Python (plain class) | **94.6** | the per-instance `__dict__` |

**(12 min) Collectors, judged by tail latency.** Point at `max`, not `mean`:

| Collector | mean | p99 | max |
| --- | ---: | ---: | ---: |
| SerialGC | 1.5 µs | 5.3 µs | **12111 µs** |
| ParallelGC | 1.5 µs | 4.2 µs | 11865 µs |
| G1GC (default) | 4.8 µs | 37.8 µs | 6972 µs |
| ZGC | 7.3 µs | 52.0 µs | **1222 µs** |
| Go GOGC=100 | 5.6 µs | 32.4 µs | 1611 µs |
| Go GOGC=400 | 4.7 µs | 16.8 µs | 856 µs |
| Go GOGC=off | **25.9 µs** | 116 µs | 5451 µs |

1. **The mean barely moves** — best argument for percentile monitoring you'll get.
2. **`GOGC=off` is *slower*.** The heap sprawls out of cache. "Less GC" ≠ "faster".
3. **Rust is absent** because it has no collector — its cost is in the mean, never a pause.

**(5 min) The container rule.** `-XX:MaxRAMPercentage=75`, `GOMEMLIMIT`.
Size limits from **RSS**, never from heap.

Deep dive: [`docs/03-memory.md`](docs/03-memory.md)

---

## Block 4 — Concurrency and parallelism (30–40 min)

**Run:** `make demo-concurrency`

**(5 min) The distinction.** Write it on the board:

> **Concurrency** is *dealing with* many things at once — a program structure.
> **Parallelism** is *doing* many things at once — a hardware property.

Then the question that settles most design arguments: **are you waiting, or are
you computing?** Waiting → concurrency (async, virtual threads). Computing →
parallelism (real threads on real cores). `async` gives CPU work exactly 0x.

**(12 min) Part 1 — can you use all your cores?** Same Mandelbrot kernel as
Block 0, `n=2000`, 4-core machine:

| Language | 1 worker | 2 workers | 4 workers | scaling |
| --- | ---: | ---: | ---: | ---: |
| Rust | 234 ms | 117 ms | 87 ms | **2.69x** |
| Go | 245 ms | 126 ms | 113 ms | 2.18x |
| Java | 308 ms | 167 ms | 150 ms | 2.05x |
| TypeScript (workers) | 261 ms | 202 ms | 177 ms | 1.47x |
| **Python (threads)** | 8718 ms | 9183 ms | 9307 ms | **0.94x** |
| **Python (processes)** | 8840 ms | 4489 ms | 3353 ms | 2.64x |

- **The flat Python threads row is the GIL** — eight threads take turns. This is
  the single most surprising fact for most juniors in the room.
- **Processes scale** (0.94x → 2.64x) at the cost of spawn + pickling.
- **Nobody hits 4.00x.** Amdahl's law is not a suggestion.

**(13 min) Part 2 — what happens when you share state?** Eight threads,
100,000 increments each, expected 800,000:

| Language | Result | When you find out |
| --- | --- | --- |
| Go | 493,211 — **lost 306,789** | run time, only with `-race` |
| Java (plain) | 231,766 | run time, never automatically |
| Java (**`volatile`**) | 282,105 — **still broken** | run time |
| Node (SharedArrayBuffer) | 509,242 | run time |
| **Rust** | **does not compile** | **compile time** |

Three beats:

1. **`counter++` is never one operation** — load, add, store.
2. **The `volatile` trap.** It buys *visibility*, not *atomicity*. Juniors
   reach for it constantly; the demo shows it losing 517,895 increments.
3. **Rust is the concurrency twin of Block 1.** `error[E0499]`. Same shape as
   the typing demo: four languages compile the broken program, one refuses.
   Then show the fix — the strategy goes *in the type*: `Mutex<u64>`, `AtomicU64`.

**The Python GIL question, answered honestly.** The demo runs two experiments:

```
EXPERIMENT 1 - tight CPU loop:  racy += lost 0     -> looks correct
EXPERIMENT 2 - check-then-act with I/O in between:
    seat limit 100, 320 attempts, racy sold 20, locked sold 100
```

Experiment 1 usually passes because a thread that never blocks holds the GIL
for its whole loop. **A race that does not reproduce is still a race.**
Experiment 2 fails every time — and it is the realistic one, because the GIL is
released on every socket read and database call.

> Python's races do not hide in tight loops. They hide exactly where all real
> Python code lives.

**Honest caveat to state:** Rust prevents *data races*, not *race conditions*.
Deadlocks, lost wakeups and check-then-act across an `await` are still yours.

Deep dive: [`docs/06-concurrency.md`](docs/06-concurrency.md) — includes a
per-chapter table of how concurrency changes the conclusions of Blocks 1–5.

---

## Block 4b — When *should* you parallelise? (20 min)

**Run:** `make demo-parallel-cost`
Deep dive: [`docs/09-when-to-parallelize.md`](docs/09-when-to-parallelize.md)

**Goal:** Block 4 asked whether you *can* use your cores. This asks whether you
*should* — because `.parallelStream()` is one word longer than `.stream()`, so
the cost is invisible at the call site.

**(10 min) The crossover.** Measured, 4 cores:

| elements | cheap op (multiply-add) | expensive op (~50 float iters) |
| ---: | --- | --- |
| 1,000 | 0.35x — **loses** | 0.25x — **loses** |
| 10,000 | **0.06x — 16x SLOWER** | 1.95x — crossover |
| 100,000 | 0.57x — loses | 3.47x — wins |
| 1,000,000 | 1.18x — crossover | 3.68x — wins |

> The crossover is not at a fixed element count. It is at a fixed amount of
> **total work**. Cheap work crosses at ~1,000,000 elements; expensive work at
> ~10,000. A **100x difference**, from cost-per-element alone.
>
> **Rule:** `N x cost-per-element` must be **>> ~100 µs** of setup.

Name the `parallelStream()` traps: it uses the **shared**
`ForkJoinPool.commonPool()`, so one blocking parallel stream stalls every other
one in the JVM. Never do I/O in one.

**(10 min) Virtual threads.** The one sentence they should leave reciting:

> **Virtual threads make BLOCKING cheap. They do not make COMPUTING faster.**

| Experiment | Platform threads | Virtual threads | |
| --- | ---: | ---: | --- |
| 8 CPU-bound tasks | 30.8 ms | 31.3 ms | **1.02x — no gain** |
| 10,000 blocking I/O tasks | 2604.8 ms (200-thread pool) | 171.8 ms | **15.2x faster** |
| Creating 100,000 threads | ~28 s, ~100 GB stack (would not fit) | **69 ms, +43 MB** | |

Then the three traps, the third of which sets up the database block:
1. `parallelStream` does not use virtual threads — the common-pool trap remains.
2. **Virtual threads do not increase your database's capacity.** 10,000 virtual
   threads reaching for a 10-connection pool *moves* the queue, and lets you
   overwhelm the DB far more easily than a 200-thread pool ever could.
3. **JDK 21 pins** virtual threads that block inside `synchronized`. Use
   `ReentrantLock`. Fixed in **JDK 24+** (JEP 491); structured concurrency is
   final in **25**. Virtual threads themselves are final in **21**, which is
   what these demos run on.

---

## Block 4c — 20 users, one shared array (20 min)

**Run:** `make demo-api-race`

**Goal:** the concurrency bug as it actually appears in production. It looks
like this, and it passes code review:

```java
private final List<String> items = new ArrayList<>();   // a controller field
items.add(payload);                                     // in a request handler
```

**(10 min) The measured result** — a real HTTP server, 20 concurrent users,
200,000 appends:

| Implementation | actual / 200,000 | ms | verdict |
| --- | ---: | ---: | --- |
| `ArrayList` (no sync) | 196,126 | 572 | **LOST 3,874 items** |
| `ArrayList` + `synchronized` | 200,000 | 332 | correct |
| `Collections.synchronizedList` | 200,000 | 288 | correct |
| `CopyOnWriteArrayList` | 200,000 | **16,080** | correct, **112x slower** |
| `ConcurrentLinkedQueue` | 200,000 | **143** | correct, fastest |

Nothing crashed. The API returned **204 to every caller**. All 20 users believe
their items were saved.

**"Thread-safe" is not one property.** `CopyOnWriteArrayList` copies the whole
backing array on every write — O(n²) to fill. Correct for listener lists,
catastrophic for a write-heavy endpoint. And compound operations still race:
`if (!list.contains(x)) list.add(x)` is two safe calls and one bug.

**(10 min) Rust — why the bug is unreachable.**

```
error[E0382]: use of moved value: `items`
```

Show both doors: **with `move`** the Vec is moved into the first handler;
**without `move`** the closure may outlive the borrow (E0373). Neither compiles.
The fix puts the strategy in the type — `Arc<Mutex<Vec<String>>>` — and you can
forget neither to lock (data is inside the mutex) nor to unlock (guard drops on
scope exit, even on panic). Measured: **110 ms**, faster than Java's
`synchronized` at 332 ms.

**State the limits:** Rust prevents *data* races, not deadlocks or logic races;
the demo uses one global lock, which is the worst design for throughput; and
Java's `ConcurrentLinkedQueue` was both correct *and* fastest. **The difference
is the default** — Java's default is a structure that quietly breaks.

---

## Block 5 — Cold starts, cloud and carbon (20 min merged / 30 min split)

**Run:** `make bench-startup` then `make carbon`

**(8 min) The cold-start table**, doing nothing at all:

| Language | cold start | baseline RSS | image (typical) |
| --- | ---: | ---: | ---: |
| Rust | **1.5 ms** | 14 MB | 5–10 MB |
| Go | **1.5 ms** | 14 MB | 10–20 MB |
| Python | 11 ms | 14 MB | 50–120 MB |
| Node | 29 ms | 44 MB | 60–150 MB |
| Java | 46 ms | 40 MB | 180–400 MB |

Work the multipliers: serverless pays it per scale-out; autoscaling speed *is*
cold start; deploy time = cold start × pods; and **baseline RSS decides bin
packing**, which is most of your bill (100 replicas: 1 node for Go, 10 for Java).

Mitigations so nobody leaves thinking "never use Java": CDS is already on and
worth ~31% (`-Xshare:off` to prove it), GraalVM native-image → ~5 ms, or just
**keep the JVM warm**.

**(8 min) Carbon.** `wordfreq` at 50M executions/month:

```
rust        225 ms CPU     3.93 kg CO2e/month
typescript 1504 ms CPU    26.23 kg CO2e/month
→ switching saves ~22 kg/month = 0.27 t/year
```

Then puncture it, in order:
1. **0.27 t/year is less than one transatlantic flight.** At low volume,
   language choice is climate noise.
2. **Region beats language by ~17x.** Run `--region eu-north-1` live: 26.23 kg
   → 1.50 kg with zero code change.
3. **The real argument is density**, not CPU — 1/10th the memory is 1/10th the
   machines, and the embodied carbon you never bought.
4. **A carbon number without its assumptions is a vibe.**

Deep dives: [`docs/04-cold-start-cloud.md`](docs/04-cold-start-cloud.md),
[`docs/05-carbon.md`](docs/05-carbon.md)

---

## Block 5b — Databases: pools, connections, transactions (30 min)

**Run:** `make demo-db`
Deep dive: [`docs/10-databases-and-scaling.md`](docs/10-databases-and-scaling.md)
Live on GCP: [`demos/db-scaling/GCP-RUNBOOK.md`](demos/db-scaling/GCP-RUNBOOK.md)

**Goal:** almost every service in the room's future is I/O-bound on a database,
which is where the language matters least and the architecture matters most.

**(5 min) A connection is not a cheap object.** In PostgreSQL it is a whole OS
**process** (~5–10 MB). `max_connections` on a small managed instance is ~100 —
so 10 pods x a pool of 20 = 200 connections against a limit of 100, and the
service does not degrade, it **fails to connect**.

**(10 min) Why a bigger pool is slower.** Simulated DB with real parallelism 8,
200 concurrent users:

| pool | throughput | p50 |
| ---: | ---: | ---: |
| **8** | **1883 q/s** | **4.2 ms** |
| 32 | 1595 q/s | 20.0 ms |
| 128 | 1009 q/s | 140.9 ms |
| 200 | 723 q/s | 289.7 ms |

> **Pool 200 buys 0.38x the throughput for 70x the p50 latency.**

The queue does not vanish when you enlarge the pool — it **moves**, out of your
app where it is visible and sheddable, into the database where it is not.
Formula: `connections = (cores * 2) + spindles` → ~17 for an 8-core DB, not 200.

**(12 min) The same race, one layer down.** 16 bookers, seat limit 100:

| strategy | confirmed | stored | verdict |
| --- | ---: | ---: | --- |
| read-then-write, no txn | **400** | **25** | told 400 users yes, stored 25 |
| `BEGIN` (deferred) txn | 34 | 34 | a transaction alone is not the fix |
| `FOR UPDATE` / `BEGIN IMMEDIATE` | 100 | 100 | pessimistic |
| optimistic (version column) | 100 | 100 | detect + retry |
| single atomic `UPDATE` | 100 | 100 | **fastest, and the right answer** |

Be precise about strategy 2: SQLite **undersells** (write conflicts), PostgreSQL
under READ COMMITTED **oversells** (lost update). Different anomaly, same cause.

**(3 min) Land the through-line.** We have now hit the *same* bug at four
layers — a type error, `counter++`, an `ArrayList` in a handler, a database row.
It is always READ, MODIFY, WRITE with a window in the middle. And the best fix
is always the same shape: **make the invalid state unrepresentable** — a type,
a `Mutex<T>`, a `CHECK` constraint. That is the fourth time this session.

---

## Block 6 — The decision framework (7–10 min)

Display / hand out [`docs/00-how-to-choose.md`](docs/00-how-to-choose.md).

**Ask the questions in this order** — performance is question five:

1. **What does the team already know?**
2. **What does the ecosystem force?** (ML → Python; browser → TS; k8s → Go)
3. **What does failure cost?** (payments justify Rust's strictness; a dashboard doesn't)
4. **What is the execution shape?** (short-lived → AOT; long-lived → JIT is fine)
5. **Only now: is it actually CPU-bound?** Most services are I/O-bound —
   `wordfreq` is your evidence.

**Closing exercise (5 min)** if time allows:

- *A CLI tool run 500 times a day.* → cold start dominates; Go or Rust.
- *A REST API doing 3 DB queries per request.* → I/O-bound; pick for team and
  ecosystem; concurrency model matters more than raw speed.
- *A nightly job over 2 TB.* → throughput and memory; JVM/Go/Rust, or Python
  **only** if the heavy lifting is in NumPy/Polars.

---

## Block 7 — Closing note: robust vs antifragile (8–10 min)

**No demo. No benchmark.** Leave them with a question that outlives the numbers.
Full text: [`docs/08-robust-vs-antifragile.md`](docs/08-robust-vs-antifragile.md)

**(3 min) Taleb's three responses to stress:**

| | Under stress | Software example |
| --- | --- | --- |
| **Fragile** | breaks | one server, no backups |
| **Robust** | resists, unchanged | replicas, retries, circuit breakers |
| **Antifragile** | **gets stronger** | *…we do not know how to build this* |

**(4 min) The thought experiment.** Put it to the room:

> Imagine a service measurably *more secure after an attack than before* — not
> because a human read the logs and patched it, but because the system itself
> metabolised the attack.

Let them work out what that needs. They will land on: detect without labels,
judge hostile vs merely novel, change itself, know whether the change helped,
and do it **without opening a new hole**. That last one is fatal — a system that
rewrites its own defences has handed the attacker a new input channel. We
already have a name for that: **data poisoning**.

Then the honest survey: chaos engineering, fuzzing, WAFs, autoscaling,
canary+rollback. Every one converts disorder into improvement **through
something outside the running system** — a human, a retro, an offline training
run. The system is a conduit for learning, not the learner.

**(3 min) The bridge — and this is why it is in a *programming* session.**
To get stronger from disorder, a system must keep the *pattern* behind ten
thousand attacks instead of the ten thousand records. **That is compression.**

3Blue1Brown's series **"Compression is Intelligence"**
([Part 1](https://www.youtube.com/watch?v=l6DKRf-fAAM),
[Part 2](https://www.youtube.com/watch?v=GlYgs6v2YfU), June 2026) lays out the
information theory: from Shannon, **prediction and compression are
mathematically two sides of the same coin** — a good model *is* a good
compressor. So:

```
antifragile ⇒ improves from disorder ⇒ extracts structure from experience
            ⇒ predicts the next attack better ⇒ compresses its history into a model
            ⇒ ...which is exactly what we mean by "learns"
```

**Antifragility is a learning problem wearing an engineering costume.**

**Land the plane by relabelling the whole session:** static types, `@tailrec`,
the borrow checker, `GOMEMLIMIT`, cold-start budgets — every single choice today
was a *fragility* decision. They all **move failure earlier or make it smaller**.
Not one makes the software better *because* it failed. Our entire toolkit is a
toolkit for row two.

> The antifragile component in your architecture today is **the team**.

That is not a defeat, and juniors should hear it explicitly — it tells them
where their own value sits.

**Last slide, one sentence:**

> Measure your workload, on your hardware, with your data — then choose.
> Everything else is folklore.

---

## Preparation checklist

Run this **the day before**, on the machine you will present from:

```bash
make doctor      # every toolchain present?
make setup       # deps + generate the corpus
make jvm-langs   # Scala + Kotlin compilers (needs network, once)
make bench       # regenerates docs/RESULTS.md with YOUR numbers
make verify      # runs all nine demos end to end
```

The numbers quoted above are from a 4-core Xeon @ 2.1 GHz. Yours will differ —
the *ratios* and the *shape* are what the session is about, and those hold up.
