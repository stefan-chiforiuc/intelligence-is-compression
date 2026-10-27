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
make verify      # runs all 14 demo checks once, end to end (~5 min)
```

`make verify` is the one that matters. It exercises every demo you plan to run.

**Then update your numbers.** The tables in `AGENDA.md` and `docs/*.md` are from
a 4-vCPU cloud container (Xeon @ 2.8 GHz). Yours will differ. The **ratios and the shape** hold
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
| Python lands next to Java at `wordfreq`, and beats TS | you are benchmarking libraries as much as languages |
| C++ loses to Go (and nearly 2x Rust) at `wordfreq` | "compiled" is not a performance guarantee; the library is the benchmark |
| Java and C# allocate faster than Rust and C++ | speed and footprint are different axes |
| C# ties Rust, Java is within 15% (JIT demo) | "compiled > JIT" is folklore at steady state |
| `GOGC=off` is *slower* | "less GC" ≠ "faster"; locality matters |
| Python threads give 0.92x on 4 cores | the GIL; and processes give 2.67x |
| Java's and C#'s `volatile` counters still lose increments | visibility ≠ atomicity |
| The C++ race prints the right answer at `-O2` | a race that does not reproduce is still a race (undefined behaviour) |
| The same code overflows in Java, runs in Scala | the runtime is not the language |

---

## Questions you will get, with answers

**"So which language should I learn?"**
The one your target job posting lists. Then a second one from a different
family — if you know Python, learn Go or Rust; if you know Java, learn Python.
The second language is what teaches you which of your habits were universal and
which were dialect.

**"Is Rust going to replace Go/Java/C++/C#?"**
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

**"What about C, PHP, Ruby, Zig…?"**
They fit the same framework. C/Zig sit with C++ and Rust (AOT, manual/ownership
memory). PHP/Ruby sit with Python (interpreted, dynamic, strong-ish). The seven
core languages (Rust, C++, Go, C#, Java, TypeScript, Python) cover every
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
have to verify the result. That is what this session is for, and the closing
block ([`08`](08-robust-vs-antifragile.md)) is about the *verify* half.

**"The agent writes better tests than I do — why shouldn't it write them?"**
(you will get this in the closing block)
It probably does write them well, and that is not the claim. The claim is that
**the oracle must be independent of the thing it judges.** An agent drafting
acceptance criteria that you read, challenge and approve *before* it implements
is fine — good, even. The same agent writing code and its tests in one
unreviewed pass gives you two artifacts that agree with each other and no
information about whether either matches what you wanted. Green means "these
two files are consistent", not "this is correct".

**"TDD slows me down, and the agent is fast. Isn't insisting on tests-first a net loss?"**
Compare the right two things. The alternative to writing 20 lines of intent is
not "nothing" — it is *reading 500 lines of plausible implementation closely
enough to be sure*. Specifying is cheaper than auditing, and the gap widens as
the codebase grows. Also note what the agent's speed did: it moved the
bottleneck from *typing* to *reviewing*, so the practice that saves review time
is the one that got more valuable, not less.

**"Isn't this just TDD evangelism with a new coat of paint?"**
Push back honestly: the empirical literature on TDD and defect rates is
genuinely mixed, and some of it suggests the gains come from working in small
verified increments rather than the test-first *ordering* as such. The argument
in the closing block is deliberately not a productivity statistic — it is
epistemic. It is about who is permitted to grade whom, which is a question
agents made urgent rather than one TDD advocates invented.

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
- **the hypothesis-first lab, in two halves.** Half the room writes acceptance
  tests for a small feature *first*, then has an agent implement against them;
  the other half has an agent implement *and* write the tests in one pass. Then
  swap and try to break each other's code with an input neither suite covers.
  The second group's suite is usually greener and weaker — the point lands
  harder from experiencing it than from being told. Follow with: rewrite one
  example-based test as a property (`reverse(reverse(xs)) == xs` shape) and see
  what it catches that the examples did not.

**Remote:** run demos yourself and share the terminal. Do not ask 20 people to
install seven toolchains; you will lose 40 minutes.

---

## What to hand out

1. [`docs/00-how-to-choose.md`](00-how-to-choose.md) — the one page that matters
2. The repo URL, so they can re-run everything on their own hardware
3. `docs/RESULTS.md` **from your machine**, as the worked example

---

## Your own preparation

The one thing to internalise: **you are not teaching seven languages, you are
teaching a way of asking questions.** Every demo exists to make one trade-off
physical. If someone leaves able to say "that depends on whether it is CPU-bound
and how long the process lives", the session worked — even if they forget every
number.
