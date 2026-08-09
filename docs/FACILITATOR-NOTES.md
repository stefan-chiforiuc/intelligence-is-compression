# Facilitator notes

Everything that is not in the agenda: prep, timing discipline, what to do when
a demo misbehaves, and the questions you will actually get asked.

---

## The day before

Run this **on the machine you will present from**, on the network you will use:

```bash
make doctor      # every toolchain present?
make setup       # deps + generate the 22 MB corpus (~2 min)
make jvm-langs   # Scala + Kotlin compilers from Maven Central (~110 MB, once)
make bench       # regenerates docs/RESULTS.md with YOUR numbers (~2 min)
make verify      # runs all nine demos once, end to end (~8 min)
```

`make verify` is the one that matters. It exercises every demo you plan to run.

**Then update your numbers.** The tables in `AGENDA.md` and `docs/*.md` are from
a 4-core Xeon @ 2.1 GHz. Yours will differ. The **ratios and the shape** hold
up; the absolute values do not. Either regenerate and re-read, or say out loud
"these are from my laptop" every time you show a number. Modelling that
disclaimer is itself part of the lesson.

### If you have no network at the venue

- **Two** steps need it: `npm install` and `make jvm-langs`. Do both beforehand.
  Once `build/jvm-langs/` exists, the tail-call demo is fully offline.
- If `node_modules` is missing, the harness falls back to Node's built-in type
  stripping and everything still runs — you just lose the `tsc` type-checking
  demo in Block 1. Have `node_modules` committed to a USB stick if the venue is
  hostile.
- `data/words.txt` is generated locally, no network needed.

---

## Timing discipline

Three hours sounds like a lot. It is not — the full material runs to about 3:40
at a comfortable pace. The blocks that overrun are **Block 1 (types)**,
**Block 3 (memory)** and **Block 4 (concurrency)**, because they generate the
most discussion.

Budgets below are the **Variant A (3:00)** numbers from AGENDA.md. Variant B
(4:00) gives every block its natural length and needs no cutting.

| Block | Budget | If you are behind, cut this |
| --- | ---: | --- |
| 0 Setup + table | 15 | nothing — this is the spine |
| 1 Types | 25 | the Rust/Java strictness comparison |
| 2 Compilation | 25 | the build-time section |
| 2b Tail calls | 10 | the trampolining aside; keep the bytecode |
| Break | 10 | — |
| 3 Memory | 30 | the stack-depth demo |
| 4 Concurrency | 30 | the Node/SharedArrayBuffer case; keep Python + Rust |
| 5 Cold start + cloud + carbon | 20 | the Dockerfile and k8s walkthrough (both are in the docs) |
| 6 Framework | 7 | never — this is what they take home |
| 7 Antifragile close | 8 | drop to 4 min: the three-row table and the last line |

**Hard rule:** protect Blocks 6 and 7. If you arrive at 2:40 having covered only
half the material, skip straight to them. The measured tables live in the repo
and they can re-run everything at home; the decision framework and the closing
question are the parts they cannot reconstruct alone.

### The two new blocks, specifically

**2b Tail calls (10 min)** is the easiest block to run long, because someone
always asks "so should we use Scala?". Have the answer ready and keep it short:
*Kotlin's null safety is a bigger practical win than TCO for most teams; this
block is about compilers, not about switching languages.* The one thing you must
show is the `javap` output — `invokestatic` vs `goto` — because that is the
proof, and it takes fifteen seconds.

**4 Concurrency (30 min)** is the block most likely to overrun and the one most
worth protecting. If you must compress, run `make demo-parallel` (the GIL table)
and show only the **Python** and **Rust** halves of the race demo. Those two
carry the whole argument: one language where the bug hides until production, one
where it cannot be written.

### Pre-warm the caches

Run each demo once before the session starts. First runs include disk reads and
`npm`/`cargo` resolution that make everything look slower and less impressive
than it is.

---

## Running demos live

- `make demo-typing` **pauses between sections** so you can talk. Press enter to
  advance. Use `make demo-typing-fast` if you are behind.
- `make demo-jit` takes ~90 seconds with `--xint`. Start it, then talk over it.
- `make demo-gc` takes ~2 minutes (8 separate JVM/Go runs). Start it *before*
  you introduce the topic.
- Everything writes to stdout. Increase your terminal font **before** you start;
  the sparkline charts are the thing people at the back need to see.

### When a demo does not match the numbers in the docs

Say so, out loud, and investigate for 30 seconds. This is a gift, not a
problem — you are teaching measurement, and a benchmark that disagrees with the
handout is the most authentic thing that can happen. Common causes:

- another process is busy (a browser, an IDE indexing)
- CPU thermal throttling on a laptop, or a noisy cloud VM neighbour
- a different JDK/Node/Go version
- power-saving governor — plug the laptop in

The `binarytrees` and `mandelbrot` results are the most stable. The GC `max`
column is the noisiest by far; treat single-run outliers with suspicion and say
why.

---

## The seven surprises, and how to land them

Do **not** explain these. Show the table and ask the room what looks wrong. The
discovery is the lesson.

| Surprise | The point |
| --- | --- |
| Python beats Java and TS at `wordfreq` | you are benchmarking libraries as much as languages |
| Java allocates faster than Rust | speed and footprint are different axes |
| Java's steady state beats Rust's (JIT demo) | "compiled > JIT" is folklore |
| `GOGC=off` is *slower* | "less GC" ≠ "faster"; locality matters |
| Python threads give 0.94x on 4 cores | the GIL; and processes give 2.64x |
| Java's `volatile` counter still loses increments | visibility ≠ atomicity |
| The same code overflows in Java, runs in Scala | the runtime is not the language |

---

## Questions you will get, with answers

**"So which language should I learn?"**
The one your target job posting lists. Then a second one from a different
family — if you know Python, learn Go or Rust; if you know Java, learn Python.
The second language is what teaches you which of your habits were universal and
which were dialect.

**"Is Rust going to replace Go/Java/C++?"**
No. Rust wins where the failure cost is high and constraints are hard. It loses
on iteration speed and hiring. Languages accumulate; they rarely replace.

**"Why is Python so popular if it's this slow?"**
Because the table shows exactly why: at `wordfreq` it is competitive, because
the hot path is C. Python is a coordination language for fast native code, and
that turns out to be an extremely good design. Also: developer time costs far
more than CPU time at most companies.

**"Should we rewrite our Python service in Go?"**
Have you profiled it? Is it CPU-bound or waiting on the database? What fraction
of latency is your code? Almost always the answer is "it is I/O-bound and the
rewrite would gain nothing" — the `wordfreq` result is your evidence.

**"Isn't TypeScript just JavaScript with extra steps?"**
Extra steps that catch the class of bug you actually hit — renames, wrong
argument order, missing null checks — before you run anything. But it does
nothing at the boundary, which the erasure demo proves.

**"My benchmark shows X is faster than your table says."**
Excellent — what did you measure, on what hardware, with what input, how many
repetitions, and did you verify the outputs match? Then walk through the
harness: reps, median, output verification. This is a genuinely good moment.

**"What about C, C++, C#, PHP, Ruby, Zig…?"**
They fit the same framework. C/C++/Zig sit with Rust (AOT, manual/ownership
memory). C# sits with Java (JIT, GC, static). PHP/Ruby sit with Python
(interpreted, dynamic, strong-ish). The five core languages cover every
quadrant; Scala and Kotlin appear only in Block 2b, to make the point that the
runtime is not the language.

**"So should we move to Scala/Kotlin?"** (you will get this in Block 2b)
That block is about compilers, not migration. If pushed: Kotlin is a low-risk
step from Java with a genuinely large win (null safety in the type system) and a
big hiring pool; Scala is a much larger commitment with a much higher complexity
ceiling, and it earns its place mainly in data engineering and correctness-heavy
domains. Neither is justified by tail calls alone.

**"Is Python's GIL going away?"**
CPython 3.13+ ships an experimental free-threaded build (PEP 703). It is not the
default and single-threaded performance is currently lower. Know about it; do
not plan around it yet.

**"If Rust prevents data races, is Rust concurrency safe?"**
It prevents *data* races — unsynchronised access to shared memory. It does not
prevent deadlocks, lost wakeups, or check-then-act logic bugs across services.
Say this every time; the demo is persuasive enough to be over-read.

**"Why not use LLMs to write the fast version?"**
Fine, and increasingly common — but it does not change the decision. You still
have to know *which* resource is scarce to know what to ask for, and you still
have to verify the result. That is what this session is for.

---

## Adapting the length

**90 minutes:** Blocks 0, 1, 2, 6. Mention memory, concurrency and cold start
from the tables without running the demos. Close with the last line of Block 7.

**2 hours:** add Block 4 (concurrency). It is the highest-value addition after
the core three, because juniors have the least prior exposure to it.

**Full day:** add hands-on labs —
- have them port `wordfreq` to a sixth language and add it to the harness
- have them break the harness deliberately (no warm-up, 1 rep, mean instead of
  median) and see how much the conclusions move
- have them profile the Python `mandelbrot` and make it 100x faster with NumPy —
  the best possible ending, because the answer is "don't change language"
- have them find and fix the race in `demos/concurrency/races/race.py`, then run
  it under load to prove the fix
- have them write an antifragile mechanism for a toy service (auto-ban on
  anomaly), then attack each other's implementations — the fastest way to learn
  why step 5 in Block 7 is the hard one

**Remote:** run demos yourself and share the terminal. Do not ask 20 people to
install five toolchains; you will lose 40 minutes.

---

## What to hand out

1. [`docs/00-how-to-choose.md`](00-how-to-choose.md) — the one page that matters
2. The repo URL, so they can re-run everything on their own hardware
3. `docs/RESULTS.md` **from your machine**, as the worked example

---

## Your own preparation

The one thing to internalise: **you are not teaching five languages, you are
teaching a way of asking questions.** Every demo exists to make one trade-off
physical. If someone leaves able to say "that depends on whether it is CPU-bound
and how long the process lives", the session worked — even if they forget every
number.
