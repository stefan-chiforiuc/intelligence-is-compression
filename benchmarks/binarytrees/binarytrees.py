#!/usr/bin/env python3
"""Allocation / GC-bound workload: build and walk many short-lived binary trees.

This is the mirror image of mandelbrot.py: almost no arithmetic, but millions
of tiny object allocations with a mix of short-lived garbage and one long-lived
tree. It is the classic way to expose garbage collector behaviour and the true
per-object memory overhead of a runtime.

Note: we use __slots__ deliberately. Without it, every node carries a __dict__
and the memory cost roughly doubles. Benchmarking the *best reasonable* version
of each language is the only fair way to do this.
"""
import sys

MIN_DEPTH = 4


class Node:
    __slots__ = ("l", "r")

    def __init__(self, l: "Node | None", r: "Node | None") -> None:
        self.l = l
        self.r = r


def make(depth: int) -> Node:
    if depth > 0:
        return Node(make(depth - 1), make(depth - 1))
    return Node(None, None)


def count(node: Node) -> int:
    if node.l is None:
        return 1
    return 1 + count(node.l) + count(node.r)


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    max_depth = max(MIN_DEPTH + 2, n)
    sys.setrecursionlimit(max_depth * 4 + 1000)

    stretch_depth = max_depth + 1
    print(f"stretch tree of depth {stretch_depth}\t check: {count(make(stretch_depth))}")

    long_lived = make(max_depth)

    for depth in range(MIN_DEPTH, max_depth + 1, 2):
        iterations = 1 << (max_depth - depth + MIN_DEPTH)
        check = 0
        for _ in range(iterations):
            check += count(make(depth))
        print(f"{iterations}\t trees of depth {depth}\t check: {check}")

    print(f"long lived tree of depth {max_depth}\t check: {count(long_lived)}")


if __name__ == "__main__":
    main()
