#!/usr/bin/env python3
"""Mixed real-world workload: read a text file, count words, print the top 10.

This is the closest of the four benchmarks to actual business code: file I/O,
string slicing, hash map inserts, and a sort. It is dominated by *library and
runtime quality* (how good is the string type, how good is the hash map) rather
than by raw loop speed, which is why the language ranking here looks very
different from mandelbrot.
"""
import sys
from collections import Counter


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/words.txt"
    with open(path, "r", encoding="ascii") as fh:
        text = fh.read()

    counts = Counter(text.split())

    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    print(f"distinct: {len(counts)}")
    for word, n in top:
        print(f"{word} {n}")


if __name__ == "__main__":
    main()
