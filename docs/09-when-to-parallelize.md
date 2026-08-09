# Block 4b — When *should* you parallelise? (and virtual threads)

**Run:** `make demo-parallel-cost` then `make demo-api-race`

Block 4 asked *can* you use your cores. This one asks *should* you — because
"you can parallelise this" and "you should parallelise this" are different
questions, and juniors are taught only the first.

---

## Part 1 — Parallelism is not free

`list.parallelStream()` is one word longer than `list.stream()`. That is the
whole problem: the cost is invisible at the call site.

Before any of your work happens you pay for:

- **splitting** the source into chunks — cheap for arrays, expensive for
  `LinkedList`, and genuinely bad for `HashMap` or anything `Iterator`-shaped
- **dispatching** tasks to the ForkJoinPool and waking its workers
- **memory barriers and cache-line traffic** between cores
- **combining** partial results
- **stragglers** — the slowest chunk decides when you finish

That cost is roughly constant. Your work is proportional to N. So there is
always a **crossover**.

### The measured crossover (4-core Xeon)

Cheap operation — one multiply-add per element:

| elements | sequential | parallel | speedup | |
| ---: | ---: | ---: | ---: | --- |
| 1,000 | 0.047 ms | 0.134 ms | 0.35x | parallel LOSES |
| 10,000 | 0.051 ms | 0.836 ms | **0.06x** | parallel LOSES badly |
| 100,000 | 0.118 ms | 0.208 ms | 0.57x | parallel LOSES |
| 1,000,000 | 1.18 ms | 1.00 ms | 1.18x | crossover |
| 10,000,000 | 11.6 ms | 6.6 ms | 1.75x | parallel wins |

Expensive operation — ~50 float iterations per element:

| elements | sequential | parallel | speedup | |
| ---: | ---: | ---: | ---: | --- |
| 100 | 0.050 ms | 0.094 ms | 0.53x | parallel LOSES |
| 1,000 | 0.078 ms | 0.309 ms | 0.25x | parallel LOSES |
| 10,000 | 0.755 ms | 0.387 ms | 1.95x | crossover |
| 100,000 | 8.30 ms | 2.40 ms | 3.47x | parallel wins |
| 1,000,000 | 76.0 ms | 20.7 ms | 3.68x | parallel wins |

**Read the two tables together.** The crossover is *not* at a fixed element
count — it is at a fixed amount of **total work**. Cheap work crosses over at
~1,000,000 elements; expensive work crosses at ~10,000. That is a **100×
difference** driven entirely by cost-per-element.

> **The rule of thumb:**
> `N × (cost per element)` must be **much greater than ~100 µs** of setup.
>
> If you cannot say roughly how long your operation takes, you cannot say
> whether to parallelise it.

At 10,000 cheap elements, `parallelStream()` was **16× slower**. That is the
number to put on the slide.

### The `parallelStream()` traps

1. **It uses the shared `ForkJoinPool.commonPool()`.** There is *one* per JVM,
   sized to `cores - 1`. One blocking `parallelStream` anywhere in your process
   stalls every other `parallelStream` in the process, including ones in
   libraries you did not write. **Never do I/O inside a parallel stream.**
2. **Splitting quality varies enormously.** `ArrayList` and arrays split
   perfectly. `LinkedList` must be walked. `HashMap` splits unevenly. The same
   `parallelStream()` call has wildly different costs depending on the source.
3. **Order matters, sometimes.** `forEachOrdered` and `findFirst` reintroduce
   sequencing and can erase the gain entirely.
4. **You cannot easily size it.** Changing the common pool means a JVM-wide
   system property, or submitting your stream into your own ForkJoinPool.

---

## Part 2 — Virtual threads (JDK 21)

> **Virtual threads make BLOCKING cheap. They do not make COMPUTING faster.**

A **platform thread** is an OS thread: ~1 MB of reserved stack, created by a
syscall, scheduled by the kernel. Blocking one wastes an expensive resource —
which is why we invented thread pools, then callbacks, then reactive streams,
then `async`/`await`. An entire generation of complexity that exists *only*
because threads were scarce.

A **virtual thread** is a Java object, ~1 KB, scheduled by the JVM onto a small
pool of carrier threads. When it blocks, the JVM **unmounts** it and runs
something else. Blocking is cheap again, so "one thread per request" becomes
correct, and all that complexity becomes unnecessary.

But the carrier pool has exactly as many threads as you have cores.

### The three measurements

**Experiment 1 — CPU-bound.** 8 arithmetic tasks:

```
platform pool (4 threads) :  30.8 ms
virtual thread per task   :  31.3 ms
-> 1.02x. No gain. Same cores, same work.
```

**Experiment 2 — blocking I/O.** 10,000 tasks each blocking 50 ms:

```
platform pool (200 threads):  2604.8 ms
virtual thread per task    :   171.8 ms
-> 15.2x FASTER. This is what virtual threads are for.
```

**Experiment 3 — what a thread costs:**

```
100,000 virtual  threads created in    69 ms, RSS +43 MB
  2,000 platform threads created in   554 ms  (277 us each)
  -> 100,000 platform threads would take ~28 s and ~100 GB of stack.
     They would not fit.
```

### When to use what

| Workload | Use | Why |
| --- | --- | --- |
| CPU-bound | fixed pool sized to **cores** | virtual threads add scheduling, not cores |
| Blocking I/O | **virtual threads**, one per task | the entire reason they exist |
| Mixed | **two pools** | never run CPU work on the pool serving requests |

### Three traps worth naming

1. **`parallelStream()` and the common pool** — see above. Virtual threads do
   not fix this; `parallelStream` does not use them.
2. **Virtual threads do not increase your database's capacity.** If 10,000
   virtual threads reach for a 10-connection pool, you have *moved* the queue,
   not removed it — and you can now overwhelm the database far more easily than
   before. This connects directly to the database block.
3. **Pinning.** On **JDK 21**, a virtual thread that blocks inside a
   `synchronized` block **pins** its carrier thread and cannot unmount, which
   can deadlock a small carrier pool. Use `ReentrantLock` instead.

### A note on JDK versions

Virtual threads were **finalised in JDK 21** (JEP 444) — no preview flag, and
that is what these demos run on. Two later changes matter, though, and are
worth knowing when someone says "don't you need a newer JDK?":

| Feature | Status |
| --- | --- |
| Virtual threads | **final in 21** |
| `synchronized` no longer pins (JEP 491) | **JDK 24+** — on 21 you must avoid `synchronized` on virtual threads |
| Structured concurrency (`StructuredTaskScope`) | still preview through 21–24, final in **25** |
| Scoped values | preview in 21, final in **25** |

So: virtual threads work on 21, but if your team is writing serious virtual
thread code, **24+ removes the biggest footgun** and **25** gives you structured
concurrency without `--enable-preview`. If you are presenting on a JDK 25
machine, everything here still runs unchanged.

---

## Part 3 — 20 users, one shared array, a real API

**Run:** `make demo-api-race`

This is the concurrency bug as it actually appears in production code. It looks
like this, and it passes review:

```java
private final List<String> items = new ArrayList<>();   // a controller field
...
items.add(payload);                                     // in a request handler
```

A field is shared by every request thread. `ArrayList` is not thread-safe.
That is the entire bug.

### The measured result — 20 users, 200,000 appends over real HTTP

| Implementation | expected | actual | ms | verdict |
| --- | ---: | ---: | ---: | --- |
| `ArrayList` (no sync) | 200,000 | 196,126 | 572 | **LOST 3,874 items** |
| `ArrayList` + `synchronized` | 200,000 | 200,000 | 332 | correct |
| `Collections.synchronizedList` | 200,000 | 200,000 | 288 | correct |
| `CopyOnWriteArrayList` | 200,000 | 200,000 | **16,080** | correct but **56× slower** |
| `ConcurrentLinkedQueue` | 200,000 | 200,000 | **143** | correct and fastest |

Nothing crashed. The API returned `204` to every caller. Every one of those
users believes their item was saved.

### "Thread-safe" is not one property

This is the part worth slowing down on, because the naive lesson — "use a
thread-safe collection" — is *wrong on its own*:

| | Correct? | Cost | Use when |
| --- | --- | --- | --- |
| `synchronized` block | only if **every** access is inside it | one lock, coarse | you control all access |
| `Collections.synchronizedList` | per-method only | one lock per call | legacy code |
| `CopyOnWriteArrayList` | yes | **O(n) per write → O(n²) to fill** | read-mostly: listeners, config |
| `ConcurrentLinkedQueue` | yes | lock-free | append-only, which is most of the time |

`CopyOnWriteArrayList` was 112× slower than `ConcurrentLinkedQueue` here. It is
genuinely thread-safe and genuinely the wrong choice for a write-heavy
endpoint. **Ask "thread-safe for what access pattern, at what cost?"**

And the trap that survives all of these: **compound operations**.

```java
if (!list.contains(x)) list.add(x);   // two thread-safe calls, one race
```

`synchronizedList` makes each call atomic. It does not make the *pair* atomic.

### Rust: the same API, and why the bug is unreachable

```
error[E0382]: use of moved value: `items`
```

Two doors, both locked — show both, because students always try the other one:

- **with `move`**: the `Vec` is moved into the first handler's closure; the
  second request has nothing to append to
- **without `move`**: the closure borrows `items` and the compiler cannot prove
  the thread ends first — `E0373 closure may outlive the current function`

The working version puts the strategy in the type:

```rust
Arc<Mutex<Vec<String>>>
 |    |     |
 |    |     +-- the data
 |    +-------- only touchable while holding the lock
 +------------- shared ownership across threads, refcounted
```

The mechanism is `Send`/`Sync`: `Vec<String>` is `Send` but **not** `Sync`, so
`&Vec<String>` cannot cross a thread boundary at all. `Mutex<Vec<String>>` *is*
`Sync`. You cannot forget to **lock** (the data is inside the mutex) and you
cannot forget to **unlock** (the guard drops, even on panic).

Measured: `Arc<Mutex<Vec>>` completed the same 200,000 appends in **110 ms** —
faster than Java's `synchronized` at 332 ms, despite using one global lock.

### The honest limits — state all three

1. Rust prevents **data races**, not deadlocks, not check-then-act logic bugs,
   not two services disagreeing about who owns a row.
2. The Rust demo uses **one global lock**, the worst possible design for
   throughput. Safe ≠ scalable.
3. **Java has good answers too** — `ConcurrentLinkedQueue` was correct *and*
   fastest. The difference is the **default**: Java's default is a data
   structure that quietly breaks.

---

## Discussion prompts

1. Your colleague adds `.parallelStream()` to a loop over 500 config entries
   and reports it "feels faster". What do you ask for? *(A measurement. At 500
   cheap elements it is almost certainly slower.)*
2. You switch a service to virtual threads and throughput does not improve.
   What are the two most likely reasons? *(It was CPU-bound, or the bottleneck
   moved to the connection pool / downstream service.)*
3. Why is `CopyOnWriteArrayList` in the JDK at all, given the numbers above?
   *(Reads are lock-free and never block — ideal for listener lists read
   thousands of times and written twice at startup.)*
4. Where else in this session did the fix turn out to be "make the invalid
   state unrepresentable"? *(Static types, `@tailrec`, `Mutex<T>`, and — coming
   next — a database CHECK constraint.)*
