#!/usr/bin/env python3
"""'Warm-up' curve for CPython - a third control group, for a different reason.

CPython 3.11 has a "specialising adaptive interpreter" (PEP 659) which does a
small amount of run-time specialisation, so you may see a slight improvement
over the first batch or two. But there is no machine-code compiler here at all,
so the line is essentially flat AND high.

Worth mentioning to the class: this is exactly what CPython 3.13+'s optional
JIT and projects like PyPy set out to change, and it is why the numeric Python
world (NumPy, PyTorch, Polars) works by handing the hot loop to C or Rust
rather than by making the interpreter faster.

Output: one "batch,milliseconds" line per batch, for run.py to chart.
"""
import time

BATCHES = 60
CALLS_PER_BATCH = 10         # Python is ~100x slower here, so far fewer calls
SIZE = 16
MAX_ITER = 50


def kernel(n: int) -> int:
    inside = 0
    for y in range(n):
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


def main() -> None:
    sink = 0
    for b in range(BATCHES):
        t0 = time.perf_counter_ns()
        for _ in range(CALLS_PER_BATCH):
            sink += kernel(SIZE)
        ms = (time.perf_counter_ns() - t0) / 1e6
        # Scale to the same number of calls the compiled languages do, so the
        # chart is comparable. We print the honest per-call cost either way.
        print(f"{b},{ms * (200 / CALLS_PER_BATCH):.3f}")
    if sink < 0:
        print("unreachable")


if __name__ == "__main__":
    main()
