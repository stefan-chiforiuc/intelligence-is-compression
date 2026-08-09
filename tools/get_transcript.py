#!/usr/bin/env python3
"""Build the wordfreq corpus from REAL English: 3Blue1Brown video transcripts.

    python3 tools/get_transcript.py                    # fetch + build data/transcript.txt
    python3 tools/get_transcript.py --extra my.txt     # include your own text first
    python3 tools/get_transcript.py --words 3000000

WHY A SECOND CORPUS EXISTS
--------------------------
`tools/gen_words.py` builds a SYNTHETIC corpus: 50,000 invented words with a
Zipf-ish distribution. It is perfectly reproducible and needs no network, which
is why it is the default.

But it is not English. Real prose has a much smaller vocabulary (~10,000 unique
words here, not 50,000), far more extreme repetition, and short common words.
That changes hash-map behaviour, string interning, and cache locality - so the
same benchmark can rank the languages DIFFERENTLY on the two corpora.

That is not a flaw in the benchmark. It is the entire thesis of the session,
turned on the benchmark itself: **the data is part of the workload.** Run
`make bench-corpus` to show both tables side by side.

SOURCE
------
github.com/3b1b/captions - the 3Blue1Brown captions repository, 154 English
transcripts (2015-2024). Note the repo is now DEPRECATED; Grant Sanderson moved
translation work to criblate.com, so videos after 2024 - including the 2026
"Compression is Intelligence" series - are NOT in it.

If you want that specific transcript in the corpus, save it to a file and pass
`--extra path/to/transcript.txt`. It will be placed first and repeated along
with everything else.

The text is NOT committed to this repository: it is fetched into data/, which
is gitignored. The captions repo carries no LICENSE file, so we link to it and
download at setup time rather than vendoring someone else's words.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTIONS_REPO = "https://github.com/3b1b/captions"
DEFAULT_OUT = os.path.join(ROOT, "data", "transcript.txt")

# Match the synthetic corpus's contract exactly: lowercase tokens separated by
# whitespace, so all five wordfreq implementations work unchanged and their
# outputs stay comparable.
TOKEN = re.compile(r"[a-z']+")
WORDS_PER_LINE = 12


def clone(dest: str) -> str | None:
    print(f"Cloning {CAPTIONS_REPO} (shallow) ...")
    env = {**os.environ, "GIT_LFS_SKIP_SMUDGE": "1"}
    res = subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", CAPTIONS_REPO, dest],
        capture_output=True, text=True, env=env, timeout=900,
    )
    if res.returncode != 0:
        print(f"  clone failed: {res.stderr.strip()[:300]}")
        return None
    return dest


def collect(repo_dir: str) -> list[str]:
    """Every English transcript, in sorted order so the build is reproducible."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(repo_dir):
        if os.path.basename(dirpath) != "english":
            continue
        if "transcript.txt" in filenames:
            found.append(os.path.join(dirpath, "transcript.txt"))
    return sorted(found)


def tokenize(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=DEFAULT_OUT)
    # Match tools/gen_words.py's TOTAL_WORDS exactly. If the two corpora had
    # different word counts, a comparison between them would be confounded by
    # volume and would say nothing about vocabulary - which is the whole point.
    ap.add_argument("--words", type=int, default=3_000_000,
                    help="total words to emit; default matches the synthetic "
                         "corpus exactly so the two are directly comparable")
    ap.add_argument("--extra", action="append", default=[],
                    help="your own text file(s) to include first, e.g. the 2026 "
                         "'Compression is Intelligence' transcript")
    ap.add_argument("--keep-clone", help="reuse/keep the clone at this path")
    args = ap.parse_args()

    words: list[str] = []
    sources = 0

    for path in args.extra:
        if not os.path.exists(path):
            print(f"--extra file not found: {path}")
            sys.exit(1)
        with open(path, encoding="utf-8", errors="replace") as fh:
            words.extend(tokenize(fh.read()))
        sources += 1
        print(f"included {path}")

    tmp = args.keep_clone or tempfile.mkdtemp(prefix="captions-")
    cloned_here = False
    try:
        if not os.path.isdir(os.path.join(tmp, ".git")):
            if clone(tmp) is None:
                print()
                print("Could not fetch the transcripts (no network?).")
                if words:
                    print("Continuing with your --extra text only.")
                else:
                    print("Fall back to the synthetic corpus, which needs nothing:")
                    print("  python3 tools/gen_words.py data/words.txt")
                    sys.exit(1)
            else:
                cloned_here = not args.keep_clone

        if os.path.isdir(os.path.join(tmp, ".git")):
            files = collect(tmp)
            print(f"found {len(files)} English transcripts")
            for f in files:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    words.extend(tokenize(fh.read()))
            sources += len(files)
    finally:
        if cloned_here and os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)

    if not words:
        print("No text collected.")
        sys.exit(1)

    unique = len(set(words))
    target = args.words
    repeats = target / len(words)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="ascii", errors="ignore", newline="\n") as fh:
        buf: list[str] = []
        line: list[str] = []
        total = 0
        done = False
        while not done:
            for w in words:
                line.append(w)
                total += 1
                if len(line) == WORDS_PER_LINE:
                    buf.append(" ".join(line))
                    line.clear()
                    if len(buf) >= 5000:
                        fh.write("\n".join(buf) + "\n")
                        buf.clear()
                if total >= target:
                    done = True
                    break
        if line:
            buf.append(" ".join(line))
        if buf:
            fh.write("\n".join(buf) + "\n")

    size_mb = os.path.getsize(args.out) / (1024 * 1024)
    print()
    print(f"wrote {args.out}")
    print(f"  sources        {sources} files")
    print(f"  distinct words {unique:,}")
    print(f"  words written  {total:,} ({repeats:.1f}x the source text)")
    print(f"  size           {size_mb:.1f} MiB")
    print()
    print("Compare the two corpora with:  make bench-corpus")
    if repeats > 1:
        print()
        print(f"NOTE: the source text was repeated {repeats:.1f}x to reach exactly")
        print(f"{target:,} words - the same count the synthetic corpus emits - so the")
        print("two are directly comparable and VOCABULARY is the only variable.")
        print("Repetition scales word FREQUENCIES but leaves the vocabulary")
        print("unchanged, which is exactly the property under test. Say that out")
        print("loud if anyone asks; it is a fair question.")


if __name__ == "__main__":
    main()
