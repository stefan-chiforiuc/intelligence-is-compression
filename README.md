# intelligence-is-compression

**Choosing a Programming Language** — a 3–5 hour training, with a runnable,
measured benchmark suite behind every claim.

> ### Why this repo is called that
>
> The session ends on Grant Sanderson's argument from 3Blue1Brown's
> [*Compression is Intelligence*](https://www.youtube.com/watch?v=l6DKRf-fAAM):
> from Shannon, **prediction and compression are mathematically two sides of
> the same coin** — a good model *is* a good compressor, and extracting
> structure from experience is what learning *is*.
>
> That idea shows up four times here, which is why it names the repo:
>
> 1. **The corpus.** `wordfreq` counts word frequencies over 3,000,000 words of
>    3Blue1Brown narration. Building a frequency table is literally the front
>    end of every compressor ever written, and where his entropy calculation
>    starts. ([Block 0b](docs/11-the-data-is-the-workload.md))
> 2. **The closing note.** Antifragile software — software that gets *stronger*
>    when attacked — turns out to require keeping the pattern behind ten
>    thousand attacks instead of the ten thousand records. That is compression,
>    which is why we cannot build it yet: it is a learning problem wearing an
>    engineering costume. ([Block 7](docs/08-robust-vs-antifragile.md))
> 3. **The tests.** A test suite is a compression of intent — the shortest
>    artifact the intended behaviour can be recovered from. So if you cannot
>    state the test, you have not compressed the requirement, which means you do
>    not yet understand it. That is why hypothesis-first survives agents writing
>    the code. ([Block 7](docs/08-robust-vs-antifragile.md))
> 4. **The method.** Every table here compresses a pile of measurements into a
>    rule you can carry. That is the only thing a training can actually give you.

Teaching materials and a **runnable benchmark suite** for a session on how to
choose a programming language for a solution.

The same four programs are implemented in **Python, Go, Rust, C++, C#,
TypeScript and Java** (plus **Scala** and **Kotlin** for the tail-call block),
measured on your own hardware, and used to argue one point:

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
| Send something to participants | [docs/compression-thread.html](docs/compression-thread.html) — the 14 ideas, self-contained, opens in any browser |

---

## Quick start

```bash
make doctor      # check Python, Go, Rust, C++, .NET, Node and Java are installed
make setup       # install deps, generate the benchmark corpus  (~2 min)
make jvm-langs   # fetch standalone Scala + Kotlin compilers    (~110 MB, once)
make bench       # run the suite, write docs/RESULTS.md         (~2 min)
make transcript  # real-English corpus: 154 3Blue1Brown transcripts (once)
make verify      # smoke-test all 14 demo checks end to end     (~5 min)
```

Then run any block on its own:

```bash
make bench-corpus     # the same benchmark on two corpora — the data is the workload
make demo-typing      # static/dynamic, strong/weak, and type erasure
make demo-jit         # AOT vs JIT warm-up curves
make demo-tailcalls   # Java vs Scala vs Kotlin: tail-call optimisation
make demo-null-safety # Java NPE vs Kotlin String?, plus Rust/TS/Python
make demo-style       # fold vs reduce, pure functions vs OOP, Spring beans as FP
make demo-memory      # stack vs heap, and what an object really costs
make demo-gc          # garbage collectors compared by tail latency
make demo-concurrency # parallel scaling + data races in all seven languages
make demo-parallel-cost # when NOT to parallelise; virtual threads
make demo-api-race    # 20 users, one shared array, over real HTTP
make demo-spring      # Spring Boot: real cold start + request thread pool
make db-up            # small PostgreSQL container: 1 CPU, 512 MB, 50 connections
make demo-db          # connection pools + the same race inside a database
make db-down          # tear it down
make bench-startup    # cold starts only
make carbon           # energy and CO2e estimate
```

**Requirements:** Python 3.11+, Go 1.21+, Rust 1.70+, a C++20 compiler (g++ 11+ or
clang 14+), .NET SDK 8+, Node 20+, JDK 17+.
The database block additionally wants Docker and `pip install 'psycopg[binary]'`
— without them it falls back to a simulation and says so.
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

From a 4-vCPU cloud container (Xeon @ 2.8 GHz), median of 11 runs — regenerate
with `make bench`:

| | mandelbrot | binarytrees | wordfreq | startup | peak RSS (trees) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rust | **96 ms** | 520 ms | **394 ms** | 1.9 ms | **14.6 MB** |
| C++ | 105 ms | 520 ms | 726 ms | **1.5 ms** | **14.6 MB** |
| Go | 107 ms | 809 ms | 577 ms | 2.0 ms | 14.8 MB |
| C# | 158 ms | 488 ms | 985 ms | 44 ms | 58.5 MB |
| Java | 173 ms | **359 ms** | 1354 ms | 69 ms | 174 MB |
| TypeScript | 145 ms | 456 ms | 1738 ms | 34 ms | 96.4 MB |
| Python | 3855 ms | 6337 ms | 1184 ms | 18.5 ms | 21.1 MB |

Results that break the usual folklore:

- **Python lands next to Java at `wordfreq`** (1184 vs 1354 ms) and beats
  TypeScript (1738 ms) — the most realistic workload — because `str.split` and
  `Counter` are C. You are benchmarking libraries as much as languages. The
  Python/Java order is *not* stable: it flips between passes on the synthetic
  corpus, and Java wins on real English
  ([Block 0b](docs/11-the-data-is-the-workload.md)).
- **C++ is not automatically faster than Go, or than Rust.** At `wordfreq`
  C++ took 726 ms against Go's 577 ms and Rust's 394 ms: `std::unordered_map` is
  a node-based table, and the standard library optimises for generality. Three
  languages compiled straight to machine code, 1.8x apart. The *library* is the
  benchmark.
- **Java allocates faster than Rust and C++** at `binarytrees` (359 vs 520 ms),
  using 12x the memory to do it (174 vs 14.6 MB). C# is also ahead of them
  (488 ms). Speed and footprint are different axes.
- **A JIT's steady state is within 20% of AOT.** In the warm-up demo C# (4.6 ms)
  ties Rust (4.6 ms) and Java is 5.3 ms. (On the original reference machine Java
  edged Rust, 2.9 vs 3.1 ms; a 7% gap did not survive a change of hardware.)
  A JIT's problem is time-to-peak, not peak.
- **`GOGC=off` is 1.9x slower**, not faster. "Less GC" ≠ "faster" — a compacting
  collector also buys you cache locality.
- **Python threads scale to 0.92x on 4 cores** while Python *processes* reach
  2.67x. That flat row is the GIL, and it is the single most surprising result
  in the concurrency block.
- **The same function overflows the stack in Java and returns instantly in
  Scala and Kotlin** — same JVM, same bytecode format. `javap -c` shows why:
  `invokestatic` versus `goto`.
- **`parallelStream()` was ~5x SLOWER** on 10,000 cheap elements (median of 5
  runs; 1.4–6.7x). Parallelism has a fixed cost, and below the crossover you only pay it.
- **Virtual threads: 15.0x faster on blocking I/O, 0.99x on CPU work.** They
  make blocking cheap; they do not make computing faster.
- **A 20-user API lost 4,471 of 200,000 items** into an `ArrayList` and returned
  HTTP 204 every time. The Rust equivalent does not compile.
- **A connection pool of 200 gave 0.39x the throughput of a pool of 8, for 63x
  the latency.** Bigger pools move the queue; they do not remove it.

---

## Repository layout

```
AGENDA.md                  the session plan (3:00 core / 4:00 extended)
Makefile                   every command you need

benchmarks/                the same 4 programs in 7 languages
  mandelbrot/              CPU-bound float math
  binarytrees/             allocation + GC pressure
  wordfreq/                file I/O, strings, hash maps, sorting
  startup/                 cold start

demos/
  typing/                  strong/weak x static/dynamic, and type erasure
  jit-warmup/              per-batch timing inside one process
  tail-calls/              Java vs Scala vs Kotlin, proved with javap
  null-safety/             Java NPE vs Kotlin String? vs Rust Option<T>
  programming-style/       fold vs reduce, pure fns vs OOP, Spring beans as FP
  stack-heap/              Go escape analysis, stack limits
    objsize/               measured bytes-per-object in all 7 languages
  gc/                      collectors compared by tail latency
  concurrency/
    parallel/              same Mandelbrot kernel fanned out across cores
    races/                 the same shared counter, seven ways to get it wrong
  java-parallel-cost/      the crossover point, and virtual threads
  api-race/                20 users + one ArrayList over real HTTP; Rust twin
  spring-boot/             a real framework: cold start and request thread pool
  db-scaling/              pool sizing, transaction anomalies, GCP runbook
    docker-compose.yml     resource-limited PostgreSQL for the live demos

docs/
  00-how-to-choose.md      the decision framework (the handout)
  01-typing.md             type systems
  02-compilation.md        AOT, JIT, interpreters
  03-memory.md             stack, heap, garbage collection
  04-cold-start-cloud.md   cold starts, containers, Kubernetes
  05-carbon.md             energy and CO2e, and how to be sceptical of it
  06-concurrency.md        concurrency vs parallelism, GIL, races
  07-jvm-languages-tail-calls.md   same runtime, different language
  08-robust-vs-antifragile.md      closing note + why hypothesis-first survives agents
  09-when-to-parallelize.md        parallelism cost, virtual threads, API race
  10-databases-and-scaling.md      pools, connections, transactions
  11-the-data-is-the-workload.md   same benchmark, two corpora, different answer
  12-spring-boot-cold-start-and-pools.md  what a framework really costs
  13-programming-style.md  functional vs OOP, fold vs reduce, Spring beans as FP
  compression-thread.html  the 14 binding ideas, as a shareable deck for participants
  RESULTS.md               generated by `make bench`
  FACILITATOR-NOTES.md     prep, timing, expected questions

tools/
  bench.py                 the measurement harness
  carbon.py                energy/CO2e estimator with visible assumptions
  gen_words.py             deterministic synthetic corpus generator
  get_transcript.py        real-English corpus from 3Blue1Brown transcripts
  get_jvm_langs.sh         fetches Scala + Kotlin compilers from Maven Central
```

---

## Notes on methodology

Worth reading before you quote any of these numbers, and worth telling the room:

- **Median of N runs**, with warm-up runs discarded. Configurable via `--reps`.
- **Peak RSS via `os.wait4`**, so it is the child process's own `ru_maxrss`, not
  a process-wide running maximum.
- **Output is cross-checked** across all seven languages for every workload.
- **Each language is written idiomatically and reasonably optimised.** Python
  uses `__slots__` and `Counter`; Rust and C++ borrow `&str` / `string_view` keys
  instead of allocating a `String` per word. Benchmarking a strawman version of a
  language teaches nothing.
- **Absolute numbers are machine-specific.** The ratios and the shape of the
  disagreement between workloads are the point.
- **The corpus is part of the workload.** `wordfreq` ships with two inputs of
  identical size — synthetic and real English — because they give different
  answers. See [docs/11](docs/11-the-data-is-the-workload.md).
- **This is not a language shootout.** Every workload here is deliberately small
  enough to read in full, which also means none of them is your application.

---

## Licence

Use freely for teaching. The benchmark shapes (`mandelbrot`, `binarytrees`) are
long-standing community benchmarks reimplemented here from scratch for clarity
rather than for maximum score.
