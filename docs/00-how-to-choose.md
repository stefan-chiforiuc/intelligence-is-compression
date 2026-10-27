# How to choose a programming language

The one-page version. Print this; it is the actual deliverable of the session.

---

## Ask the questions in this order

Performance is question **five**. Teams that ask it first usually pick wrong.

### 1. What does the team already know?

A language your team is fluent in beats a faster one they are learning — almost
always, and by a wider margin than any benchmark in this repo.

A rewrite in a "faster" language that the team cannot debug at 3am is a
downgrade. Fluency shows up as fewer bugs, faster reviews, better libraries
chosen, and correct use of the concurrency model. None of that appears in a
benchmark table, and all of it dominates.

**Override this only when** the requirement is genuinely unreachable in the
current stack (hard real-time, a 10 MB memory ceiling, a browser target).

### 2. What does the ecosystem force?

This decides more projects than speed does, and it is usually not negotiable:

| Domain | The answer is basically decided |
| --- | --- |
| Machine learning / data science | Python |
| Browser front end | JavaScript / TypeScript |
| Kubernetes / cloud infrastructure tooling | Go |
| Android | Kotlin (Java) |
| iOS | Swift |
| Enterprise back office, big-bank backends | Java / C# |
| Embedded, OS, browser engines | Rust / C / C++ |
| Game engines | C++ / C# |

Fighting the ecosystem means writing bindings, reimplementing libraries, and
hiring against a smaller pool. That cost is real and recurring.

### 3. What does failure cost?

| Failure cost | Implication |
| --- | --- |
| Someone loses money, data, or their life | Buy every compile-time guarantee available. Rust's strictness is a bargain. |
| A page renders wrong until the next deploy | Optimise for iteration speed. Python/TS. |
| A batch job reruns tomorrow | Correctness matters, latency does not. |

Static typing is insurance. Insurance is worth it in proportion to the loss.

### 4. What is the execution shape?

This is where the AOT/JIT material pays off:

| Shape | Implication | Good fits |
| --- | --- | --- |
| Short-lived: CLI, Lambda, CI step, cron | Cold start dominates. AOT. | Rust, C++, Go, (Python for scripts) |
| Long-lived: HTTP service, consumer, daemon | Warm-up amortises to zero. JIT is fine and often *better*. | Java, C#, Node, Go |
| Scale-to-zero / spiky traffic | Cold start is your latency SLO. | Rust, C++, Go |
| Huge heap, latency-critical | You are choosing a **collector**, not a language. | Java + ZGC, Go, Rust, C++ |
| Memory-constrained (edge, sidecar, 400 replicas) | Footprint per instance × replicas. | Rust, C++, Go |

### 5. *Only now:* is it actually CPU-bound?

Most services are **I/O-bound**. They spend their lives waiting on a database,
an HTTP call, or a queue. For those, language execution speed is close to
irrelevant — a 40x faster language makes a 2 ms difference in a 200 ms request.

**Evidence from this repo:** in `wordfreq`, the workload closest to real
business code, Python (1184 ms) lands right next to Java (1354 ms) and clearly
beats TypeScript (1738 ms) — despite being ~40x slower than Rust at raw loops.
Because the hot path is `str.split` and `Counter`, which are C. (The Python/Java
order is not stable between runs, which is itself the point: they are the same
speed for practical purposes.)

So the real question is: **which 5% of my code is hot, and can I make just that
part fast?** Very often you can, without changing language:
NumPy / Polars / DuckDB (Python), a native module (Node), a rewritten inner
loop (anything).

---

## The trade-off cheat sheet

| | Rust | C++ | Go | C# | Java | TypeScript | Python |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Typing | static, strong, strictest | static, but C-style casts and undefined behaviour | static, strong | static, strong (null checks opt-in) | static, strong | static → **erased at run time** | dynamic, strong |
| Compilation | AOT (slow builds at scale) | AOT (slow builds, headers) | AOT (very fast builds) | JIT (+ ReadyToRun / Native AOT) | JIT (+AOT via Graal) | JIT (V8) | interpreted |
| Memory management | ownership, no GC | RAII / manual, no GC | concurrent GC, pause-optimised | generational GC, tunable | many GCs, tunable | generational GC (V8) | refcount + cycle GC |
| Cold start | ~1.9 ms | ~1.5 ms | ~2.0 ms | ~44 ms | ~69 ms | ~34 ms | ~18.5 ms |
| Baseline RSS | ~15 MB | ~15 MB | ~15 MB | ~23 MB | ~40 MB | ~43 MB | ~15 MB |
| Bytes per small object | 32 | 32 | 16 | 32 | 25 | 80 | 48 (`__slots__`) / 95 |
| Raw loop speed (warm) | 1.0x | 1.0x | 1.1x | 1.0x | 1.2x | 1.2x | ~40x slower |
| Concurrency | threads + async, compiler-checked | threads + async, **you** check | goroutines + channels | threads, `Task`/`async`, thread pool | threads, virtual threads (21+) | single-threaded + event loop | GIL (threads ≠ parallel) |
| Best at | correctness under constraint | squeezing the hardware; huge existing codebases | networked services, tooling | large long-lived systems, games (Unity) | large long-lived systems | anything with a browser | glue, data, ML, scripts |
| Worst at | iteration speed, hiring | memory-safety footguns; build and dependency tooling | expressiveness, generics-heavy code | cold start without AOT | cold start, footprint | CPU-bound work | CPU-bound work |
| Learning curve | steep | steep | gentle | moderate | moderate | moderate | gentle |

*(Numbers measured on the reference machine; see [RESULTS.md](RESULTS.md).)*

---

## Arguments that are real vs folklore

| Claim | Verdict |
| --- | --- |
| "Compiled languages are faster than JIT languages" | **Folklore, at steady state.** In our warm-up demo C# (JIT) tied Rust (4.6 ms each) and Java was within 15% (5.3 ms). The JIT's problem is time-to-peak, not peak. |
| "C++ is the fastest, full stop" | **Depends on the library.** At `wordfreq` C++ (726 ms) was slower than Go (577 ms) and nearly 2x Rust (394 ms): `std::unordered_map` is a general-purpose, node-based table. |
| "Python is slow" | **Depends.** ~40x slower at raw loops; competitive at real workloads where the hot path is C. |
| "Static types prevent bugs" | **Real, but bounded.** They protect the inside of your program. At the boundary (JSON/HTTP/DB) they do nothing unless you validate. |
| "TypeScript makes JavaScript type-safe at run time" | **False.** Types are erased. Our demo proves it in one line. |
| "Rust (or C++) is always the memory-efficient choice" | **Mostly.** But Go used *less* per object (16 B vs 32 B) because of allocator size classes. |
| "Garbage collection makes a language slow" | **Folklore.** Java (359 ms) and C# (488 ms) *allocated faster than Rust and C++* (520 ms) in `binarytrees`. GC costs you memory (174 MB vs 15 MB) and tail latency, not throughput. |
| "Turning the GC off makes it faster" | **False.** `GOGC=off` was 1.9x *slower* — the heap sprawls out of cache. |
| "Rewriting in a faster language is good for the planet" | **Usually noise.** Changing cloud region beat changing language by ~17x in our estimate. |
| "Use the right tool for the job" | **True but useless** unless you can name the job's shape. That is what questions 1–5 are for. |

---

## Red flags in a language-choice discussion

- Nobody has named the workload shape (CPU-bound? I/O-bound? short-lived?).
- The benchmark cited is someone else's, on someone else's hardware, on a
  workload that is not yours.
- Only the mean is quoted. Ask for p99 and max.
- Only speed is quoted. Ask for memory, cold start, and build time.
- The proposal is a rewrite and the current bottleneck has never been profiled.
- "Everyone is using X now."

---

## The one sentence

> Measure your workload, on your hardware, with your data — then choose.
> Everything else is folklore.
