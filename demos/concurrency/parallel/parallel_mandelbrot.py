#!/usr/bin/env python3
"""Parallel Mandelbrot in Python — with threads AND processes, because the
difference between them is the single most important fact about Python
concurrency.

    python3 parallel_mandelbrot.py <n> <workers> <thread|process>

CPython has a Global Interpreter Lock: only one thread may execute Python
bytecode at a time. For CPU-bound work, N threads therefore give you 1x, not
Nx — they take turns. For I/O-bound work threads are fine, because the GIL is
released while waiting on a socket or a file.

`multiprocessing` sidesteps the GIL by using separate OS processes, each with
its own interpreter and its own GIL. You get real parallelism, and you pay for
it: process spawn cost, and every argument and result must be pickled and
copied between address spaces.

Python 3.13+ ships an experimental free-threaded build (PEP 703) that removes
the GIL. It is not the default, and single-thread performance is currently
lower. Worth knowing about; not yet worth planning around.
"""
from __future__ import annotations

import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

MAX_ITER = 50


def band(args: tuple[int, int, int]) -> int:
    """Count points inside the set for rows [y0, y1)."""
    n, y0, y1 = args
    inside = 0
    for y in range(y0, y1):
        ci = 2.0 * y / n - 1.0
        for x in range(n):
            cr = 2.0 * x / n - 1.5
            zr = 0.0
            zi = 0.0
            i = 0
            while i < MAX_ITER and zr * zr + zi * zi <= 4.0:
                t = zr * zr - zi * zi + cr
                zi = 2.0 * zr * zi + ci
                zr = t
                i += 1
            if i == MAX_ITER:
                inside += 1
    return inside


def split(n: int, workers: int) -> list[tuple[int, int, int]]:
    step = (n + workers - 1) // workers
    return [(n, y, min(y + step, n)) for y in range(0, n, step)]


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    mode = sys.argv[3] if len(sys.argv) > 3 else "thread"

    chunks = split(n, workers)
    pool_cls = ThreadPoolExecutor if mode == "thread" else ProcessPoolExecutor

    t0 = time.perf_counter()
    if workers == 1:
        total = band(chunks[0]) if len(chunks) == 1 else sum(band(c) for c in chunks)
    else:
        with pool_cls(max_workers=workers) as pool:
            total = sum(pool.map(band, chunks))
    ms = (time.perf_counter() - t0) * 1000

    print(f"inside={total} workers={workers} ms={ms:.1f}")


if __name__ == "__main__":
    main()
