#!/usr/bin/env python3
"""Generate the deterministic input corpus for the wordfreq benchmark.

The file is NOT committed to git (it is ~20 MB). Regenerate it with:

    python3 tools/gen_words.py data/words.txt

Everything is driven by a fixed-seed LCG, so every machine produces a
byte-identical file and therefore a byte-identical benchmark result.
Word frequencies follow a rough Zipf curve so the hash map has a realistic
mix of very hot and very cold keys.
"""
from __future__ import annotations

import os
import sys

VOCAB_SIZE = 50_000
TOTAL_WORDS = 3_000_000
WORDS_PER_LINE = 12
ALPHABET = "abcdefghijklmnopqrstuvwxyz"

# Numerical Recipes LCG constants; any deterministic PRNG would do.
_MASK = (1 << 32) - 1
_A = 1_664_525
_C = 1_013_904_223


class Lcg:
    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK

    def next_u32(self) -> int:
        self.state = (self.state * _A + _C) & _MASK
        return self.state

    def next_float(self) -> float:
        return self.next_u32() / 4_294_967_296.0


def build_vocab(rng: Lcg, size: int) -> list[str]:
    words = []
    for _ in range(size):
        length = 3 + rng.next_u32() % 8
        words.append("".join(ALPHABET[rng.next_u32() % 26] for _ in range(length)))
    return words


def main() -> None:
    out_path = sys.argv[1] if len(sys.argv) > 1 else "data/words.txt"
    total = int(sys.argv[2]) if len(sys.argv) > 2 else TOTAL_WORDS

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    rng = Lcg(seed=20240917)
    vocab = build_vocab(rng, VOCAB_SIZE)

    with open(out_path, "w", encoding="ascii", newline="\n") as fh:
        lines: list[str] = []
        line: list[str] = []
        for _ in range(total):
            # u**3 skews selection hard toward the front of the vocabulary,
            # which approximates a Zipf distribution well enough for a demo:
            # a handful of very hot keys and a long cold tail.
            u = rng.next_float()
            idx = int(VOCAB_SIZE * (u * u * u))
            line.append(vocab[min(idx, VOCAB_SIZE - 1)])
            if len(line) == WORDS_PER_LINE:
                lines.append(" ".join(line))
                line.clear()
                if len(lines) >= 5000:
                    fh.write("\n".join(lines) + "\n")
                    lines.clear()
        if line:
            lines.append(" ".join(line))
        if lines:
            fh.write("\n".join(lines) + "\n")

    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"wrote {out_path}: {total:,} words, {size_mb:.1f} MiB, vocab {VOCAB_SIZE:,}")


if __name__ == "__main__":
    main()
