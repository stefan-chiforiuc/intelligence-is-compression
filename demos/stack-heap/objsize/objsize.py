#!/usr/bin/env python3
"""Directly measure the true cost of one object holding two references.

Method: read RSS, allocate N nodes and KEEP THEM ALL LIVE in an array, read
RSS again. The delta divided by N is what that object really costs, including
headers, allocator rounding and GC headroom.

This is measured, not derived. Deriving it from the binarytrees peak RSS does
not work, because each runtime hits its peak at a different moment (Rust frees
the stretch tree before building the long-lived one; a generational GC may
still be holding both).

Two variants are reported because the gap between them is a genuinely useful
Python lesson.
"""
import os

N = 1_000_000


def rss_bytes() -> int:
    with open("/proc/self/status") as fh:
        for line in fh:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    return 0


class NodeSlots:
    __slots__ = ("l", "r")

    def __init__(self, l, r):
        self.l = l
        self.r = r


class NodeDict:
    def __init__(self, l, r):
        self.l = l
        self.r = r


def measure(cls, label: str) -> None:
    base = rss_bytes()
    keep = [None] * N
    for i in range(N):
        keep[i] = cls(None, None)
    delta = rss_bytes() - base
    # Subtract the list of N pointers itself; we want the node cost only.
    delta -= N * 8
    print(f"Python {label:<14} {delta / N:6.1f} bytes/node   (RSS delta {delta / 1048576:.1f} MB for {N:,} nodes)")
    keep.clear()


if __name__ == "__main__":
    measure(NodeSlots, "(__slots__)")
    measure(NodeDict, "(plain class)")
    print()
    print("That gap is why __slots__ exists: a per-instance __dict__ costs more")
    print("than the data it holds. It is also why dataclasses(slots=True) and")
    print("attrs are worth knowing about for anything you allocate in bulk.")
