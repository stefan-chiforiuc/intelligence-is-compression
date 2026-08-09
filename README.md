# Choosing a Programming Language — a 3–4 hour training

Teaching materials and a **runnable benchmark suite** for a session on how to
choose a programming language for a solution.

The same four programs are implemented in **Python, Go, Rust, TypeScript and
Java** (plus **Scala** and **Kotlin** for the tail-call block), measured on your
own hardware, and used to argue one point:

> There is no fastest language. There are only workloads, and each language is
> a different bet about which resource is scarce.

---

## Start here

| You want to | Read |
| --- | --- |
| Run the session | **[AGENDA.md](AGENDA.md)** — block-by-block plan, in a 3:00 and a 4:00 variant |
| Prepare to teach it | [docs/FACILITATOR-NOTES.md](docs/FACILITATOR-NOTES.md) |
| Just the takeaway | [docs/00-how-to-choose.md](docs/00-how-to-choose.md) |
| See the numbers | [docs/RESULTS.md](docs/RESULTS.md) |

---

## Quick start

```bash
make doctor      # check Python, Go, Rust, Node and Java are installed
make setup       # install deps, generate the benchmark corpus  (~2 min)
make jvm-langs   # fetch standalone Scala + Kotlin compilers    (~110 MB, once)
make bench       # run the suite, write docs/RESULTS.md         (~2 min)
make verify      # smoke-test all nine demos end to end         (~8 min)
```

Then run any block on its own:

```bash
make demo-typing      # static/dynamic, strong/weak, and type erasure
make demo-jit         # AOT vs JIT warm-up curves
make demo-tailcalls   # Java vs Scala vs Kotlin: tail-call optimisation
make demo-memory      # stack vs heap, and what an object really costs
make demo-gc          # garbage collectors compared by tail latency
make demo-concurrency # parallel scaling + data races in all five languages
make demo-parallel-cost # when NOT to parallelise; virtual threads
make demo-api-race    # 20 users, one shared array, over real HTTP
make demo-db          # connection pools + the same race inside a database
make bench-startup    # cold starts only
make carbon           # energy and CO2e estimate
```

**Requirements:** Python 3.11+, Go 1.21+, Rust 1.70+, Node 20+, JDK 17+.
Everything else is stdlib. Two steps need the network, both one-off and both
with fallbacks: `npm install` for TypeScript, and `make jvm-langs`, which pulls
the Scala and Kotlin compilers straight from Maven Central as plain jars — no
SDKMAN, no Gradle, no coursier.

---

## What gets measured

Four workloads, chosen because they **disagree with each other**:

| Workload | Stresses | The lesson |
| --- | --- | --- |
| `mandelbrot` | tight float loops, zero allocation | raw compiler/interpreter quality |
| `binarytrees` | millions of tiny objects | allocator and garbage collector |
| `wordfreq` | file I/O, strings, hash map, sort | what business code actually does |
| `startup` | process spawn + runtime boot | serverless and CLI cold starts |

Per language the harness records **wall time, CPU time and peak RSS**, takes the
median of N repetitions, and **verifies that every language produced
byte-identical output**. A benchmark you have not verified is a rumour.

### Headline results

From a 4-core Xeon @ 2.1 GHz — regenerate with `make bench`:

| | mandelbrot | binarytrees | wordfreq | startup | peak RSS (trees) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rust | 57 ms | 318 ms | **226 ms** | **1.5 ms** | **14 MB** |
| Go | **50 ms** | 464 ms | 299 ms | **1.5 ms** | 14 MB |
| Java | 114 ms | 281 ms | 771 ms | 46 ms | 197 MB |
| TypeScript | 86 ms | **240 ms** | 1290 ms | 29 ms | 98 MB |
| Python | 2300 ms | 4350 ms | 895 ms | 11 ms | 20 MB |

Six results that break the usual folklore:

- **Python beats Java and TypeScript at `wordfreq`** — the most realistic
  workload — because `str.split` and `Counter` are C. You are benchmarking
  libraries as much as languages.
- **Java allocates faster than Rust** at `binarytrees`, using 14x the memory to
  do it. Speed and footprint are different axes.
- **Java's *steady state* beats Rust's** in the JIT demo (2.9 ms vs 3.1 ms). A
  JIT knows things an AOT compiler cannot. Its problem is time-to-peak, not peak.
- **`GOGC=off` is 4.6x slower**, not faster. "Less GC" ≠ "faster" — a compacting
  collector also buys you cache locality.
- **Python threads scale to 0.94x on 4 cores** while Python *processes* reach
  2.64x. That flat row is the GIL, and it is the single most surprising result
  in the concurrency block.
- **The same function overflows the stack in Java and returns instantly in
  Scala and Kotlin** — same JVM, same bytecode format. `javap -c` shows why:
  `invokestatic` versus `goto`.
- **`parallelStream()` was 16x SLOWER** on 10,000 cheap elements. Parallelism
  has a fixed cost, and below the crossover you only pay it.
- **Virtual threads: 15.2x faster on blocking I/O, 1.02x on CPU work.** They
  make blocking cheap; they do not make computing faster.
- **A 20-user API lost 3,874 of 200,000 items** into an `ArrayList` and returned
  HTTP 204 every time. The Rust equivalent does not compile.
- **A connection pool of 200 gave 0.38x the throughput of a pool of 8, for 70x
  the latency.** Bigger pools move the queue; they do not remove it.

---

## Repository layout

```
AGENDA.md                  the session plan (3:00 core / 4:00 extended)
Makefile                   every command you need

benchmarks/                the same 4 programs in 5 languages
  mandelbrot/              CPU-bound float math
  binarytrees/             allocation + GC pressure
  wordfreq/                file I/O, strings, hash maps, sorting
  startup/                 cold start

demos/
  typing/                  strong/weak x static/dynamic, and type erasure
  jit-warmup/              per-batch timing inside one process
  tail-calls/              Java vs Scala vs Kotlin, proved with javap
  stack-heap/              Go escape analysis, stack limits
    objsize/               measured bytes-per-object in all 5 languages
  gc/                      collectors compared by tail latency
  concurrency/
    parallel/              same Mandelbrot kernel fanned out across cores
    races/                 the same shared counter, five ways to get it wrong
  java-parallel-cost/      the crossover point, and virtual threads
  api-race/                20 users + one ArrayList over real HTTP; Rust twin
  db-scaling/              pool sizing, transaction anomalies, GCP runbook

docs/
  00-how-to-choose.md      the decision framework (the handout)
  01-typing.md             type systems
  02-compilation.md        AOT, JIT, interpreters
  03-memory.md             stack, heap, garbage collection
  04-cold-start-cloud.md   cold starts, containers, Kubernetes
  05-carbon.md             energy and CO2e, and how to be sceptical of it
  06-concurrency.md        concurrency vs parallelism, GIL, races
  07-jvm-languages-tail-calls.md   same runtime, different language
  08-robust-vs-antifragile.md      closing philosophy note
  09-when-to-parallelize.md        parallelism cost, virtual threads, API race
  10-databases-and-scaling.md      pools, connections, transactions
  RESULTS.md               generated by `make bench`
  FACILITATOR-NOTES.md     prep, timing, expected questions

tools/
  bench.py                 the measurement harness
  carbon.py                energy/CO2e estimator with visible assumptions
  gen_words.py             deterministic corpus generator
  get_jvm_langs.sh         fetches Scala + Kotlin compilers from Maven Central
```

---

## Notes on methodology

Worth reading before you quote any of these numbers, and worth telling the room:

- **Median of N runs**, with warm-up runs discarded. Configurable via `--reps`.
- **Peak RSS via `os.wait4`**, so it is the child process's own `ru_maxrss`, not
  a process-wide running maximum.
- **Output is cross-checked** across all five languages for every workload.
- **Each language is written idiomatically and reasonably optimised.** Python
  uses `__slots__` and `Counter`; Rust borrows `&str` keys instead of allocating
  `String`s. Benchmarking a strawman version of a language teaches nothing.
- **Absolute numbers are machine-specific.** The ratios and the shape of the
  disagreement between workloads are the point.
- **This is not a language shootout.** Every workload here is deliberately small
  enough to read in full, which also means none of them is your application.

---

## Licence

Use freely for teaching. The benchmark shapes (`mandelbrot`, `binarytrees`) are
long-standing community benchmarks reimplemented here from scratch for clarity
rather than for maximum score.
