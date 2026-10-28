# Block 0b — The data is part of the workload

**Run:** `make transcript` once, then `make bench-corpus`

A five-minute addition to Block 0, and the sharpest methodology lesson in the
session: we turn the benchmark on itself.

---

## Two corpora, one benchmark

`wordfreq` reads a text file, counts words, prints the top 10. We feed it two
different files. **Both contain exactly 3,000,000 words** — the only thing that
differs is the vocabulary.

| | Synthetic (`data/words.txt`) | Real English (`data/transcript.txt`) |
| --- | --- | --- |
| Source | a fixed-seed LCG in `tools/gen_words.py` | 154 **3Blue1Brown** video transcripts (2015–2024) |
| Distinct words | **50,000-word** vocabulary of invented strings (49,979 drawn) | **10,469** real English words |
| Distribution | approximate Zipf (`u³`) | actual Zipf — `the` appears 168,447× in the 3,000,000 words |
| Sample | `tgxuzmz joxuhsf hwzineb` | `in my video on the circle division problem` |
| Needs network | no | yes, once |

Matching the word count exactly is the point. If one corpus had more words, any
difference would just be volume, and the comparison would say nothing about
vocabulary.

---

## The measured result

Median of 11 runs, one pass per corpus, 4-vCPU Xeon @ 2.8 GHz:

| Language | Synthetic (50k vocab) | Real English (10.5k vocab) | Gain |
| --- | ---: | ---: | ---: |
| Rust | 405 ms | **170 ms** | **2.38×** |
| C++ | 594 ms | **261 ms** | 2.28× |
| Go | 499 ms | **335 ms** | 1.49× |
| C# | 827 ms | **502 ms** | 1.65× |
| Java | 1131 ms | **625 ms** | 1.81× |
| Python | 1240 ms | **729 ms** | 1.70× |
| TypeScript | 1790 ms | **1428 ms** | 1.25× |

### Four things to point at

**1. Every language got faster on the same amount of text.** Nothing about the
programs changed. Fewer distinct keys means a smaller hash map, and a smaller
map is the likely reason — it fits in cache — though this repo does not measure
cache misses, so call it a hypothesis. **Vocabulary size mattered more than word
count.**

**2. The gains are not equal, so the gaps move.** Rust gained 2.38×,
TypeScript only 1.25×. Any sentence of the form "language X is N× faster than Y
at text processing" is incomplete until you say *on what text*: Rust's lead
over TypeScript is 4.4× on the synthetic corpus and 8.4× on real English.

**3. There is a rank change.** On the synthetic corpus **Go beats C++**
(499 ms vs 594 ms). On real English **C++ beats Go** (261 ms vs 335 ms).
Second and third place swap, purely because of the input data. It reproduced:
the full-suite run of the synthetic corpus also had Go ahead (577 vs 726 ms),
and a second pass over real English also had C++ ahead (273 vs 338 ms).

**4. Be careful with the smaller gaps.** The same synthetic benchmark measured
in two sessions (this table, and the Block 0 suite) differed by up to ~20% in
the same program (C++: 594 ms vs 726 ms). Python and Java sit within ~10% of
each other here — Java is ahead on both corpora in this table, while Python was
ahead in the Block 0 suite run — so their order is *not* a finding. An earlier
version of this page claimed a Python/Java swap; it did not reproduce, and the
C++/Go swap is the one that did.

> If a change of dataset can reorder your benchmark, then a benchmark without
> its dataset is not a result. It is an anecdote with numbers attached.

---

## Why this is more than a caveat

This is the session's thesis applied to the session's own evidence. Block 0
argues that there is no fastest language, only workloads. Block 0b shows that
"workload" does not stop at the *code* — **the data is part of it**.

The practical version, for the room:

- When someone shows you a benchmark, ask **what data it ran on** before you ask
  anything else.
- When you benchmark your own service, use **your own production data
  distribution**, not `lorem ipsum` and not a random-string generator. Cardinality,
  key length and skew all change the answer.
- When you profile, remember the profile is only valid for the input you
  profiled with. A cache that is 95% hits on Tuesday's traffic may be 40% hits
  on Black Friday's.

---

## Where the text comes from

`tools/get_transcript.py` shallow-clones
[github.com/3b1b/captions](https://github.com/3b1b/captions), the 3Blue1Brown
captions repository, and extracts all 154 English `transcript.txt` files
(~523,000 words, 10,469 distinct), then repeats them 5.7× to reach exactly
3,000,000 words.

Two honest notes:

- **That repo is deprecated.** Grant Sanderson moved translation work to
  [criblate.com](https://criblate.com), so videos after 2024 are not in it —
  including the 2026 **"Compression is Intelligence"** series that Block 7's
  philosophy note is built around. If you want that specific transcript in the
  corpus, save it to a file and pass it in:

  ```bash
  python3 tools/get_transcript.py --extra compression-is-intelligence.txt
  ```

- **The text is not committed to this repository.** The captions repo carries no
  LICENSE file, so we fetch at setup time into `data/` (gitignored) rather than
  vendoring somebody else's words.

Text is lowercased and reduced to `[a-z']` tokens so the file has exactly the
same shape as the synthetic corpus — which is why all five `wordfreq`
implementations run against both without a single line changing.

---

## A neat coincidence worth using

The corpus is 3Blue1Brown talking, at length, about mathematics — including the
`attention` and `gpt` videos on transformers.

Block 7 closes on Grant Sanderson's **"Compression is Intelligence"** argument:
that prediction and compression are two sides of the same coin, and that
extracting structure from experience is what learning *is*.

Block 0b has the class run a word-frequency count over 3 million words of his
narration — which is, quite literally, **building a statistical model of a
corpus by measuring how often each symbol occurs**. That is the first step of
every compressor ever written, and the entropy calculation in Part 1 of his
series starts from exactly this table.

You do not have to labour the point. Just note, when the top-10 table appears
in Block 0, that the room has already built the front end of a compressor — and
then call back to it in Block 7.

---

## Discussion prompts

1. Why would a smaller vocabulary make *every* language faster? *(Smaller hash
   map, better cache locality, fewer distinct allocations, more branch
   predictability.)*
2. Rust gained 2.38× and TypeScript only 1.25×. What might explain the
   difference? *(A hypothesis, not a finding: the part of a run that vocabulary
   can touch — hash-map size and sort length — is a bigger share of Rust's total
   time than of TypeScript's, where costs that do not depend on vocabulary, such
   as reading and slicing strings, dominate. A profile would confirm or refute
   it; we have not taken one.)*
3. Your team benchmarks a JSON parser with a 2 KB sample payload and picks the
   winner. What did they fail to test? *(Their real payload sizes, key
   cardinality, nesting depth, unicode. The 2 KB result may not survive any of
   them.)*
4. Is repeating the source text 5.7× cheating? *(It scales frequencies, not
   vocabulary — and vocabulary is the variable under test. But say it out loud;
   an audience that spots it and is not told first will distrust the rest.)*
