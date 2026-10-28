#!/usr/bin/env python3
"""Parallel scaling: the same Mandelbrot kernel, fanned out N ways, in 7 languages.

    python3 demos/concurrency/parallel/run.py
    python3 demos/concurrency/parallel/run.py --workers 1 2 4 8 --size 1000

Deliberately the SAME kernel as benchmarks/mandelbrot, so the class can connect
this straight back to the single-threaded table from Block 0 - the same work,
now divided across cores.

Use --size 1000 to get exactly the Block 0 workload (inside=397380); the
default of 2000 is four times the work, which keeps the parallel region large
enough that JVM warm-up and V8 isolate boot do not dominate the result.

What the table shows:
  * Go / Rust / C++ / C# / Java  scale close to linearly - real threads on real cores
  * Python threads    scale to ~1.0x - the GIL serialises bytecode execution
  * Python processes  scale, but pay spawn + pickling overhead
  * Node workers      scale, but each worker boots a fresh V8 isolate
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
HERE = os.path.join(ROOT, "demos", "concurrency", "parallel")
OUT = os.path.join(ROOT, "build", "demos", "concurrency")

LINE = re.compile(r"inside=(\d+)\s+workers=(\d+)\s+ms=([\d.]+)")


def sh(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)


def build() -> dict[str, list[str]]:
    """Compile everything; return {label: run-command-prefix}."""
    os.makedirs(OUT, exist_ok=True)
    targets: dict[str, list[str]] = {}

    r = sh(["rustc", "-O", os.path.join(HERE, "parallel_mandelbrot.rs"),
            "-o", os.path.join(OUT, "pm_rs")])
    if r.returncode == 0:
        targets["Rust"] = [os.path.join(OUT, "pm_rs")]
    else:
        print(f"  rust build failed:\n{r.stderr[:500]}")

    r = sh(["g++", "-O2", "-std=c++20", "-pthread", os.path.join(HERE, "parallel_mandelbrot.cpp"),
            "-o", os.path.join(OUT, "pm_cpp")])
    if r.returncode == 0:
        targets["C++"] = [os.path.join(OUT, "pm_cpp")]
    else:
        print(f"  c++ build failed:\n{r.stderr[:500]}")

    r = sh(["go", "build", "-o", os.path.join(OUT, "pm_go"),
            os.path.join(HERE, "parallel_mandelbrot.go")])
    if r.returncode == 0:
        targets["Go"] = [os.path.join(OUT, "pm_go")]
    else:
        print(f"  go build failed:\n{r.stderr[:500]}")

    r = sh(["dotnet", "build", os.path.join(HERE, "ParallelMandelbrot.csproj"), "-c", "Release",
            "-o", os.path.join(OUT, "cs"), "--nologo", "-v", "q",
            f"-p:BaseIntermediateOutputPath={os.path.join(ROOT, 'build', 'obj', 'parallel')}/"])
    if r.returncode == 0:
        targets["C#"] = ["dotnet", os.path.join(OUT, "cs", "ParallelMandelbrot.dll")]
    else:
        print(f"  dotnet build failed:\n{(r.stdout + r.stderr)[:500]}")

    r = sh(["javac", "-d", OUT, os.path.join(HERE, "ParallelMandelbrot.java")])
    if r.returncode == 0:
        targets["Java"] = ["java", "-cp", OUT, "ParallelMandelbrot"]
    else:
        print(f"  javac failed:\n{r.stderr[:500]}")

    # .mts forces ESM output (.mjs), which `import.meta.url` needs so a worker
    # can re-launch this same file inside a fresh isolate.
    r = sh(["npx", "--no-install", "tsc", os.path.join(HERE, "parallel_mandelbrot.mts"),
            "--outDir", OUT, "--target", "es2022", "--module", "nodenext",
            "--moduleResolution", "nodenext", "--skipLibCheck", "--types", "node"])
    mjs = os.path.join(OUT, "parallel_mandelbrot.mjs")
    if r.returncode == 0 and os.path.exists(mjs):
        targets["TypeScript"] = ["node", mjs]
    else:
        # Node 22 can strip types directly; ESM is implied by the .mts extension.
        shutil.copyfile(os.path.join(HERE, "parallel_mandelbrot.mts"),
                        os.path.join(OUT, "parallel_mandelbrot.mts"))
        targets["TypeScript"] = ["node", os.path.join(OUT, "parallel_mandelbrot.mts")]

    py = os.path.join(HERE, "parallel_mandelbrot.py")
    targets["Python (threads)"] = [sys.executable, py]
    targets["Python (processes)"] = [sys.executable, py]
    return targets


def run(cmd: list[str], size: int, workers: int, mode: str | None) -> tuple[int, float] | None:
    full = [*cmd, str(size), str(workers)]
    if mode:
        full.append(mode)
    r = sh(full)
    if r.returncode != 0:
        return None
    m = LINE.search(r.stdout)
    if not m:
        return None
    return int(m.group(1)), float(m.group(3))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=int, default=2000)
    ap.add_argument("--workers", nargs="*", type=int, default=[1, 2, 4])
    args = ap.parse_args()

    cores = os.cpu_count() or 1
    print(f"Building ... (machine has {cores} cores)\n")
    targets = build()

    widths = args.workers
    header = f"{'Language':<20}" + "".join(f"{str(w) + ' worker':>14}" for w in widths) + f"{'scaling':>12}"
    print("=" * len(header))
    print(f"PARALLEL SCALING - Mandelbrot n={args.size} "
          f"(answer must be identical at every worker count)")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for label, cmd in targets.items():
        mode = None
        if label == "Python (threads)":
            mode = "thread"
        elif label == "Python (processes)":
            mode = "process"

        row: list[float | None] = []
        answers = set()
        for w in widths:
            res = run(cmd, args.size, w, mode)
            if res is None:
                row.append(None)
            else:
                answers.add(res[0])
                row.append(res[1])

        cells = "".join(f"{v:>11.1f} ms" if v is not None else f"{'failed':>14}" for v in row)
        base, last = row[0], row[-1]
        if base and last:
            scaling = f"{base / last:>10.2f}x"
        else:
            scaling = f"{'-':>11}"
        warn = "" if len(answers) <= 1 else "  !! answers differ"
        print(f"{label:<20}{cells}{scaling}{warn}")

    print()
    print(f"'scaling' = 1-worker time / {widths[-1]}-worker time. "
          f"Perfect would be {min(widths[-1], cores):.2f}x on {cores} cores.")
    print()
    print("""TALKING POINTS

  1. Python THREADS do not scale. That flat row is the GIL: only one thread may
     execute Python bytecode at a time, so N threads take turns rather than run
     at once. This is the most important single fact about Python concurrency,
     and it surprises almost every junior.

  2. Python PROCESSES do scale - at a price. Separate interpreters mean no
     shared GIL, but also process spawn cost and pickling every argument and
     result across address spaces. Great for coarse chunks, terrible for
     fine-grained work.

  3. Go, Rust, C++, C# and Java scale near-linearly. Different mechanisms, same
     outcome: goroutines on GOMAXPROCS threads, scoped OS threads (Rust),
     std::thread (C++, no compiler help with races), Tasks on the .NET
     ThreadPool, and a fixed Java thread pool.

  4. Node scales via worker_threads, but each worker is a whole new V8 isolate
     (~30 ms, ~40 MB). Note that `async`/`await` would have given you 0x here -
     it is concurrency for I/O, not parallelism for CPU.

  5. Nobody hits perfect linear scaling. Memory bandwidth, the unparallelised
     setup, thread startup and (on a laptop) thermal limits all take a cut.
     Amdahl's law is not a suggestion.""")


if __name__ == "__main__":
    main()
