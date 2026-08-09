#!/usr/bin/env python3
"""CPU-bound workload: count points inside the Mandelbrot set.

Pure scalar float math in a tight nested loop. No allocation, no I/O.
This isolates *raw interpreter/compiler quality* from everything else.
"""
import sys

MAX_ITER = 50


def mandelbrot(n: int) -> int:
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
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    print(mandelbrot(n))


if __name__ == "__main__":
    main()
