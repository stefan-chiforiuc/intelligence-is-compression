# Block 4 — Concurrency and parallelism

**Run:** `make demo-concurrency` (or `make demo-parallel` / `make demo-races`)

---

## The distinction to open with

Write these on the board before any code:

> **Concurrency** is *dealing with* many things at once — a structure for your program.
> **Parallelism** is *doing* many things at once — an execution property of the hardware.

You can have concurrency with one core (an event loop juggling 10,000 sockets).
You can have parallelism with no concurrency in your source (a vectorised
matrix multiply). Most confusion in this area — and most of the misuse of
`async` — comes from fusing the two words.

The follow-up question that resolves almost every real design argument:

> **Are you waiting, or are you computing?**

| You are… | You need | Cost of getting it wrong |
| --- | --- | --- |
| waiting on network/disk/DB (**I/O-bound**) | concurrency: async, an event loop, virtual threads | threads sit idle; you buy cores you never use |
| computing (**CPU-bound**) | parallelism: real threads on real cores | `async` gives you exactly 0x |

---

## The seven concurrency models

| | Unit | Scheduler | Shared memory? | CPU parallelism |
| --- | --- | --- | --- | --- |
| **Python** | `threading.Thread` | OS, but gated by the **GIL** | yes | **no** (use `multiprocessing`) |
| **Node/TS** | event loop + `worker_threads` | libuv; workers are OS threads | **no** by default (separate isolates) | only via workers |
| **Go** | goroutine (2 KB, growable) | Go runtime, M:N onto `GOMAXPROCS` | yes | yes |
| **Java** | platform thread (~1 MB) / **virtual thread** (JDK 21) | OS / JVM scheduler | yes | yes |
| **C#** | `Thread`, or a `Task` on the shared thread pool (`async`/`await`) | .NET thread pool (work-stealing, hill-climbing sizer) | yes | yes |
| **C++** | `std::thread` / `std::jthread`; `std::async`; coroutines (C++20) | OS | yes, **unchecked: a race is undefined behaviour** | yes |
| **Rust** | `std::thread`, or async tasks | OS / your chosen executor | yes, **checked by the compiler** | yes |

### What each one is really betting on

- **Python** bet that the interpreter's simplicity was worth more than
  parallelism, and that C extensions would carry the CPU work. Given NumPy,
  PyTorch and Polars, that bet largely paid off.
- **Node** bet that one thread plus non-blocking I/O beats a thread per
  connection. It won that argument decisively for I/O-heavy servers, and lost
  CPU work entirely until `worker_threads`.
- **Go** bet that concurrency should be so cheap you never think about pooling.
  Goroutines cost about a function call, so "one goroutine per request" is
  ordinary style, not extravagance.
- **Java** bet on real OS threads and a rigorously specified memory model
  (JSR-133, 2004). Expensive threads forced the whole reactive/async ecosystem
  — which **virtual threads** (JDK 21) now largely make unnecessary.
- **C#** bet on a runtime-managed thread pool plus `async`/`await` as syntax,
  so that "wait for I/O without holding a thread" reads like straight-line
  code. It is the same bet as Java's virtual threads, made earlier and in the
  compiler rather than the scheduler.
- **C++** bet that the programmer knows best. Threads, atomics and a precise
  memory model (C++11) are all there, and none of it is checked: a data race is
  *undefined behaviour*, so the compiler may assume it never happens.
- **Rust** bet that the compiler should prove your sharing is sound. `Send` and
  `Sync` put "safe to move between threads" and "safe to share between threads"
  into the type system.

---

## Part 1 — Can you use all your cores?

The same Mandelbrot kernel from Block 0, fanned out across workers. Measured on
a 4-vCPU machine, `n=2000`:

| Language | 1 worker | 2 workers | 4 workers | scaling |
| --- | ---: | ---: | ---: | ---: |
| Rust | 377 ms | 191 ms | 139 ms | **2.71x** |
| C++ | 386 ms | 210 ms | 164 ms | 2.35x |
| Go | 411 ms | 211 ms | 152 ms | 2.70x |
| C# | 380 ms | 191 ms | 142 ms | 2.67x |
| Java | 442 ms | 234 ms | 192 ms | 2.31x |
| TypeScript (workers) | 380 ms | 251 ms | 227 ms | 1.67x |
| **Python (threads)** | 15433 ms | 16891 ms | 16703 ms | **0.92x** |
| **Python (processes)** | 15260 ms | 7783 ms | 5709 ms | 2.67x |

(Four runs in total. Scaling stayed between 2.1x and 2.8x for Rust, C++, Go, C#
and Java, and between 1.7x and 1.8x for TypeScript; Python threads sat at
0.86–0.94x. The ordering *among* the first five swaps from run to run — do not
rank them on this table. The gap down to TypeScript and the flat
Python-threads row are stable.)

### The five things to point at

**1. The Python threads row is flat — that is the GIL.** Only one thread may
execute Python bytecode at a time, so eight threads take turns rather than run
at once. Adding threads made it *slightly slower* (contention overhead with no
benefit). This is the single most important fact about Python concurrency and it
surprises nearly every junior.

**2. Python processes DO scale**, 0.92x → 2.67x, because each process has its
own interpreter and its own GIL. The price: process spawn cost, and every
argument and result must be pickled and copied between address spaces. Great for
coarse chunks; terrible for fine-grained work.

**3. Nobody reaches 4.00x on 4 cores.** Here the best is ~2.7x. Memory
bandwidth, the unparallelised setup, thread startup and a shared cloud VM all
take a cut — and this machine is a KVM guest whose four vCPUs are not dedicated
cores, so do not expect a laptop to look the same. **Amdahl's law is
not a suggestion:** if 10% of your program is serial, your ceiling is 10x no
matter how many cores you buy.

**4. Node scales worst of the real-threading options** because each worker boots
an entire V8 isolate (~30 ms, ~40 MB). Worker threads pay off for chunky work,
not per-request fan-out.

**5. `async`/`await` would have scored 0x here.** Say this explicitly. Async is
concurrency for waiting. There is nothing to wait for in a Mandelbrot loop.

> **Python 3.13+** ships an experimental free-threaded build (PEP 703) that
> removes the GIL. It is not the default and single-threaded performance is
> currently lower. Worth knowing; not yet worth planning around.

---

## Part 2 — What happens when you share state?

Eight threads, each incrementing a shared counter 100,000 times. Expected
800,000.

| Language | Result | When you find out |
| --- | --- | --- |
| Go | 379,659 — **lost 420,341** | run time, and only if you run `-race` |
| Java (plain) | 340,369 — lost 459,631 | run time, never automatically |
| Java (**`volatile`**) | 325,259 — **still lost 474,741** | run time |
| C# (plain) | 604,277 — lost 195,723 | run time, never automatically |
| C# (**`volatile`**) | 572,459 — **still lost 227,541** | run time |
| C++ (`-O0`) | 366,562 — lost 433,438 | run time, with `-fsanitize=thread` |
| C++ (`-O2`) | **800,000 — "correct"** | the bug is still there: undefined behaviour |
| Node (SharedArrayBuffer) | 644,448 — lost 155,552 | run time |
| Node (plain / single-thread) | 800,000 | no shared memory, no race |
| **Rust** | **does not compile** | **compile time** |

(One run of `make demo-races`. The racy counts are different every run, and —
as the C++ `-O2` row shows — a racy build can even print the right answer. The
only stable fact is that the locked and atomic versions are always exactly
800,000.)

### `counter++` is never one operation

It is load, add, store. Two threads read the same value, both add one, both
write the same result — one increment vanishes. Nothing crashes. You just get a
different wrong number every run.

### The `volatile` trap — worth a full minute

Juniors reach for `volatile` constantly because it sounds like "make this
thread-safe". The demo shows a `volatile` counter losing 474,741 increments in Java and
227,541 in C#.

> `volatile` guarantees **visibility** (you will see other threads' writes).
> It does not guarantee **atomicity** (read-modify-write is still three steps).

### C++: the same bug is *undefined behaviour*

Look at the two C++ rows. The **same source file**, built with `-O0` and with
`-O2`, loses 433,438 increments in one build and **none** in the other. That is
not luck in the scheduler. GCC at `-O2` rewrites each thread's 100,000-iteration
loop into a single `add $100000, counter` — you can see it in
`g++ -O2 -S` — which shrinks the race window to almost nothing.

The C++ memory model says a data race on a non-atomic object is **undefined
behaviour**, so the optimiser is entitled to assume it cannot happen, and
anything that follows from that assumption is legal. "It passed at `-O2`" is
therefore worth exactly nothing; compare Python's Experiment 1 below, which
also comes out correct for the wrong reason. The tool is
`g++ -fsanitize=thread` (ThreadSanitizer), C++'s counterpart to Go's `-race`:
it finds the race at either optimisation level, and, like `-race`, it only
finds races your tests actually execute.

### Rust: the concurrency twin of Block 1

```
error[E0499]: cannot borrow `counter` as mutable more than once at a time
```

This is exactly the shape of the typing demo. Six languages compile the broken
program; one refuses. The mechanism is `Send` + `Sync` plus the borrow
checker's "one mutable borrow XOR many shared borrows" rule, which makes
unsynchronised shared mutation *unrepresentable*.

And the fix is not "add a lock and remember to use it" — it is to put the
strategy in the type:

```rust
Mutex<u64>    // a u64 you can only touch while holding the lock
AtomicU64     // a u64 whose reads and writes are indivisible
```

You cannot read the `u64` without locking, because the `u64` is *inside* the
`Mutex`. In Go and Java that knowledge lives in a comment or in someone's head.

**The honest caveat, which you must state:** Rust prevents **data races**
(unsynchronised access to shared memory). It does **not** prevent **race
conditions** in the logical sense — deadlocks, lost wakeups, check-then-act
across an `await`, or two correct services disagreeing about who owns a row.
No type system saves you there.

### Python: the GIL question, answered honestly

The demo runs two experiments, and the *contrast* is the lesson:

```
EXPERIMENT 1 - tight CPU loop, no I/O
  racy `+=`       800000   (lost 0)
  -> Came out CORRECT. That is NOT safety.

EXPERIMENT 2 - check-then-act with I/O between check and act
  seat limit      100
  booking attempts 320
  racy   -> sold  20        <- 80 bookings vanished
  locked -> sold  100
```

Experiment 1 usually passes, because a thread that never blocks tends to hold
the GIL for its whole loop. **A race that does not reproduce is still a race.**

Experiment 2 fails every time, and it is the realistic one: every Python service
is I/O-bound, and **the GIL is released on every socket read, database call and
file access.** The moment your code waits for anything, other threads run — right
between your check and your act.

> Python's races do not hide in tight loops. They hide exactly where all real
> Python code lives.

---

## Per-chapter callbacks

Concurrency changes the conclusion of every earlier block. Worth revisiting
explicitly:

| Block | What concurrency adds |
| --- | --- |
| **1 Types** | Rust's `Send`/`Sync` are types that describe *thread safety*. Java's `@GuardedBy` is a comment; Rust's `Mutex<T>` is a type. |
| **2 Compilation** | The JIT must deoptimise safely while other threads run its code — a large part of why JIT compilers are so complex. Go's escape analysis gets *harder* when a value may be shared. |
| **3 Memory** | GC and threads are the same problem twice. Java's TLABs give each thread its own nursery so allocation needs no lock. ZGC's low pauses exist to stop one thread's GC stalling all the others. |
| **4 Cold start** | Thread pools, executors and worker isolates are all paid at startup. Node's ~30 ms per worker is cold start, charged N times. |
| **5 Carbon** | Parallelism does not reduce CPU-*seconds*; it reduces wall time. Look at the CPU column in the benchmark: Go's `binarytrees` uses 1.00 s of CPU for 464 ms of wall time. Going parallel can *increase* energy while decreasing latency. |

---

## Discussion prompts

1. Your Python API server is slow under load. Someone proposes
   `multiprocessing`. What do you ask first? *(Is it CPU-bound? If it is waiting
   on the database, processes add memory and pickling and fix nothing — you
   want more concurrency, not more parallelism.)*
2. Why do virtual threads not speed up Mandelbrot? *(They solve blocking-I/O
   concurrency. CPU work is limited by cores; you want exactly as many threads
   as cores.)*
3. Your Go service passes all tests but corrupts a counter in production once a
   week. What do you run? *(`-race` in CI, over tests that actually exercise the
   concurrent path. The detector only sees what executes.)*
4. Node is single-threaded — does that mean it is free of concurrency bugs?
   *(No. Interleaved `await` points give you check-then-act races without any
   threads at all.)*
5. Where does Amdahl's law bite hardest in this session's table? *(Python
   processes: spawn and pickling are pure serial overhead, so the scaling
   ceiling drops as chunks get smaller.)*
