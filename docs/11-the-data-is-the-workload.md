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
| Distinct words | **50,000** invented strings | **10,469** real English words |
| Distribution | approximate Zipf (`u³`) | actual Zipf — `the` appears 29,448× |
| Sample | `tgxuzmz joxuhsf hwzineb` | `in my video on the circle division problem` |
| Needs network | no | yes, once |

Matching the word count exactly is the point. If one corpus had more words, any
difference would just be volume, and the comparison would say nothing about
vocabulary.

---

## The measured result

Median of 5 runs, two independent passes, 4-core Xeon:

| Language | Synthetic (50k vocab) | Real English (10.5k vocab) | Gain |
| --- | ---: | ---: | ---: |
| Rust | 168 ms | **126 ms** | 1.33× |
| Go | 378 ms | **322 ms** | 1.17× |
| Java | 660 ms | **436 ms** | **1.51×** |
| Python | 644 ms | **486 ms** | 1.32× |
| TypeScript | 1100 ms | **905 ms** | 1.22× |

### Three things to point at

**1. Every language got faster on the same amount of text.** Nothing about the
programs changed. Fewer distinct keys means a smaller hash map, which means it
fits in cache. **Vocabulary size mattered more than word count.**

**2. The gains are not equal, so the gaps move.** Java gained 1.51×, Go only
1.17×. Any sentence of the form "language X is N× faster than Y at text
processing" is incomplete until you say *on what text*.

**3. There is a rank change.** On the synthetic corpus Python (644 ms) **ties
or beats Java** (660 ms). On real English, Java (436 ms) clearly beats Python
(486 ms). Third and fourth place swap, purely because of the input data.

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
2. Java gained 1.51× and Go only 1.17×. What might explain the difference?
   *(Java's per-object overhead and GC pressure scale with the number of live
   distinct keys, so it has more to gain when that number drops.)*
3. Your team benchmarks a JSON parser with a 2 KB sample payload and picks the
   winner. What did they fail to test? *(Their real payload sizes, key
   cardinality, nesting depth, unicode. The 2 KB result may not survive any of
   them.)*
4. Is repeating the source text 5.7× cheating? *(It scales frequencies, not
   vocabulary — and vocabulary is the variable under test. But say it out loud;
   an audience that spots it and is not told first will distrust the rest.)*
