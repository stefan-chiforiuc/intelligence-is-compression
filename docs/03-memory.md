# Block 3 — Memory: stack, heap, and garbage collection

**Run:** `make demo-memory` then `make demo-gc`

---

## Part 1 — Stack vs heap

### The mental model

| | Stack | Heap |
| --- | --- | --- |
| Allocation | bump a pointer | find a free block (allocator work) |
| Deallocation | automatic, on return | GC, or manual, or ownership rules |
| Size | small and fixed (~8 MB) | large (GBs) |
| Lifetime | tied to the function call | arbitrary |
| Cost | ~free | allocation now + collection later |
| Failure mode | stack overflow → usually fatal | OOM, or slow GC death |

The rule that decides which one you get:

> A value can live on the stack if the compiler can prove it does not outlive
> the function that created it.

That is it. Everything else is a consequence.

### Watch a compiler decide

Go's escape analysis is observable, which makes this concrete instead of
theoretical:

```bash
go build -gcflags='-m' demos/stack-heap/escape.go
```
```
escape.go:40:7: &Point{...} escapes to heap      <- returns a pointer
escape.go:50:14: Point{...} escapes to heap      <- passed to interface{}
```

Three functions, identical arithmetic, different fate:

```go
func makeStackPoint(x, y float64) Point  { p := Point{x, y}; return p }   // stack
func makeHeapPoint(x, y float64) *Point  { p := &Point{x, y}; return p }  // heap
func leakToInterface(x, y float64) any   { return Point{x, y} }           // heap
```

The measured cost, 20 million iterations:

```
stack-allocated :   13.1 ms
heap-allocated  :  321.1 ms      24.4x slower
```

Plus 20 million objects for the collector to deal with afterwards.

**The third case is the one that bites people:** passing a value to
`interface{}` (or `any`, or a `fmt` call) forces a heap allocation, because the
callee might keep it. *This is why logging inside a hot loop costs far more than
it looks.*

### How each language handles it

| Language | Stack allocation |
| --- | --- |
| Rust | default. `Box`/`Vec`/`String` opt into the heap explicitly, visible in the type. |
| Go | compiler decides via escape analysis; `-gcflags=-m` shows you. |
| Java | everything is heap in principle; the JIT's **escape analysis + scalar replacement** can eliminate allocations after inlining. Not guaranteed — an optimisation, not a language rule. |
| TypeScript | everything is heap; V8 has similar (unreliable) escape analysis. |
| Python | everything is heap. Even `1` is an object (small ints are interned). |

### Stack depth is a budget

Run `bash demos/stack-heap/stack_limits.sh`:

| Language | Depth limit | Failure mode |
| --- | --- | --- |
| Python | ~soft limit, `sys.setrecursionlimit` | `RecursionError` — catchable |
| Node | ~10k frames | `RangeError` — catchable |
| Java | ~10–50k frames | `StackOverflowError` — catchable, but do not |
| Go | goroutine stacks **start at 2 KB and grow**, 1 GB ceiling | fatal, **not** recoverable |
| Rust | 8 MB main thread | SIGSEGV/abort, **not** catchable |

Go's growable stacks are why it can run hundreds of thousands of goroutines: it
does not have to reserve a big stack per concurrent task. That is a direct
consequence of a memory-layout decision, and it is most of why Go is good at
networked services.

---

## Part 2 — What an object actually costs

Measured directly: allocate 1,000,000 live nodes, each holding two references.
The **data** is 16 bytes in every language. Everything above that is the
runtime's fee.

| Language | bytes/node | What the overhead buys |
| --- | ---: | --- |
| Go | **16.0** | nothing — type info lives in span metadata, not the object |
| Java | 24.8 | 12-byte header: mark word (locking, `identityHashCode`, GC age) + compressed class pointer |
| Rust | 32.1 | 16 B of data rounded up to the allocator's 32-byte size class |
| Python `__slots__` | 48.4 | `PyObject` header: refcount + type pointer |
| Node | 80.0 | hidden-class pointer + properties store + elements store |
| Python plain class | **94.6** | the above **plus a per-instance `__dict__`** |

Three things worth saying:

1. **Rust is not automatically the smallest.** Go beat it here, because Rust's
   `malloc` rounded 16 bytes up to a 32-byte size class. Allocator behaviour
   matters as much as language semantics.
2. **Java's header is not waste** — it is what makes `synchronized`,
   `identityHashCode`, and generational GC possible. You are buying features.
3. **Python's `__slots__` halves the cost.** This is the cheapest large win
   available in Python. Use `__slots__`, `@dataclass(slots=True)`, or attrs for
   anything allocated in bulk.

### Heap vs RSS — the number that gets you OOM-killed

Java and Go report both, and the gap matters:

- **Heap delta** answers *"what does this object cost?"*
- **RSS delta** answers *"what must my container memory limit allow?"*

RSS is always larger: it includes the JVM/runtime itself, thread stacks, JIT
code cache, metaspace, and GC bookkeeping. **Size container limits from RSS,
never from heap.** More on this below.

---

## Part 3 — Garbage collection

### The three families

| Family | How | Used by |
| --- | --- | --- |
| **Reference counting** | each object counts its references; free at zero | CPython, Swift, Rust's `Rc` |
| **Tracing** | periodically trace from roots; anything unreached is garbage | JVM, Go, V8 |
| **Ownership (no GC)** | compiler proves lifetimes; frees are inserted at compile time | Rust, C++ RAII |

Reference counting gives **predictable, low memory** (freed the instant the
count hits zero) and pays a **constant CPU cost on every assignment**. It also
cannot collect cycles — which is why CPython *also* runs a cycle collector.

Tracing collectors make allocation nearly free (bump a pointer in a nursery)
and batch the cost into collections. That is why **Java allocated faster than
Rust** in `binarytrees`.

### Generational GC and the hypothesis behind it

> **The weak generational hypothesis:** most objects die young.

This is empirically true for almost all programs. So: allocate into a small
nursery, collect it often and cheaply (only survivors are copied out), and
promote long-lived survivors to an old generation that is collected rarely.

The `binarytrees` benchmark is designed to exercise exactly this — a flood of
short-lived trees plus one long-lived one.

### The measured trade-off

Same code, same 512 MB heap, different collector. **Look at `max`, not `mean`:**

| Collector | mean | p99 | max | Character |
| --- | ---: | ---: | ---: | --- |
| SerialGC | 1.5 µs | 5.3 µs | **12111 µs** | lowest overhead, worst pauses |
| ParallelGC | 1.5 µs | 4.2 µs | 11865 µs | throughput king, stops the world |
| G1GC (default) | 4.8 µs | 37.8 µs | 6972 µs | balanced, region-based, pause-target driven |
| ZGC | 7.3 µs | 52.0 µs | **1222 µs** | concurrent; ~10x better worst case |
| Go GOGC=100 | 5.6 µs | 32.4 µs | 1611 µs | tuned for pauses over throughput |
| Go GOGC=400 | 4.7 µs | 16.8 µs | 856 µs | collect 4x less often |
| Go GOGC=off | **25.9 µs** | 116 µs | 5451 µs | *slower* — see below |

**1. The mean barely moves.** If you only look at averages you will conclude
collector choice does not matter. It matters enormously — just not in the mean.
This is the single best argument for percentile monitoring you will ever get.

**2. `GOGC=off` is 4.6x slower, not faster.** Turning the collector off lets the
live heap sprawl until it no longer fits in cache and the allocator is touching
cold pages. **"Less GC" ≠ "faster"**; a compacting collector also buys you
*locality*. Meanwhile `GOGC=400` *is* faster than default — the optimum is
somewhere in the middle, not at either extreme.

**3. Rust is absent from this table** because it has no collector. Its cost is
spread evenly across every `drop`, so it appears in the mean and never as a
pause. That — not raw speed — is the real reason Rust attracts latency-critical
work: **there is no pause to tune, because there is no pause.**

### Choosing a JVM collector

| Situation | Collector |
| --- | --- |
| Heap < 4 GB, throughput matters, pauses do not | ParallelGC |
| Tiny heap, short-lived process, container with 1 CPU | SerialGC |
| General-purpose service | G1GC (the default; leave it alone) |
| Large heap + strict latency SLO | ZGC (or Shenandoah) |
| You have not measured | **G1GC. Do not tune. Measure first.** |

### Go's knobs

```bash
GOGC=100          # default: collect when the heap doubles
GOGC=400          # collect less often: faster, more memory
GOGC=off          # do not
GOMEMLIMIT=256MiB # soft ceiling (Go 1.19+) — the right knob for containers
```

`GOMEMLIMIT` is the fix for most Go OOM-kills: it makes the collector work
harder as you approach the limit instead of sailing past it.

---

## Part 4 — The container rules

The single most common JVM production incident:

> A JVM that does not know it is in a container sizes its heap from the
> **host's** memory. On a 128 GB node with a 512 MB pod limit, it will happily
> plan for a 32 GB heap and get OOM-killed.

Modern JVMs are container-aware, but **verify it** rather than assume.

```bash
# Java: percentage of the CONTAINER limit, not the host
-XX:MaxRAMPercentage=75

# Go: soft ceiling that makes the GC lean in as you approach it
GOMEMLIMIT=450MiB

# Node: V8's old-space cap
--max-old-space-size=384
```

Rules of thumb:

- Set the runtime's memory ceiling to **~75% of the container limit.** The rest
  is thread stacks, JIT code cache, metaspace, and native allocations.
- Size the container limit from **measured RSS under load**, not from heap.
- An OOM-killed container gives you no stack trace and no graceful shutdown.
  It is the worst way to fail. Leave headroom.

---

## Discussion prompts

1. Why did Java allocate *faster* than Rust in `binarytrees` while using 14x
   the memory? *(Bump allocation in a nursery vs `malloc`; the memory is the
   headroom that makes bump allocation possible.)*
2. Your service has p50 = 5 ms and p99 = 800 ms. What do you look at first?
   *(GC logs. Then allocation rate. The mean will tell you nothing.)*
3. Why can Go run 100,000 goroutines but Java historically struggled with
   100,000 threads? *(2 KB growable stacks vs ~1 MB reserved per OS thread —
   which is exactly what Java's virtual threads, JDK 21, fix.)*
4. When is reference counting better than tracing? *(Predictable memory,
   immediate release, no pauses — good for constrained or latency-sensitive
   environments. Cost: per-assignment overhead and cycle leaks.)*
