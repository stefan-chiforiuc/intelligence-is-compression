#!/usr/bin/env python3
"""Build, run and chart the JIT warm-up demo.

    python3 demos/jit-warmup/run.py               # all languages
    python3 demos/jit-warmup/run.py --langs java typescript
    python3 demos/jit-warmup/run.py --xint        # add interpreter-only JVM

Draws an ASCII chart of per-batch time so the shape is visible from the back
of the room. The story you are telling:

    Rust / C++ / Go - flat from batch 0       (AOT: all the work happened at build time)
    C# / Java / TS  - expensive, then plateaus (JIT: the work happens while you watch)
    Python     - flat, but an order of magnitude higher (no machine code at all)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(ROOT, "demos", "jit-warmup")
OUT = os.path.join(ROOT, "build", "demos")

TARGETS = {
    "rust": {
        "build": ["rustc", "-O", os.path.join(HERE, "warmup.rs"), "-o", os.path.join(OUT, "warmup_rs")],
        "run": [os.path.join(OUT, "warmup_rs")],
    },
    "cpp": {
        "build": ["g++", "-O2", "-std=c++20", os.path.join(HERE, "warmup.cpp"),
                  "-o", os.path.join(OUT, "warmup_cpp")],
        "run": [os.path.join(OUT, "warmup_cpp")],
    },
    "go": {
        "build": ["go", "build", "-o", os.path.join(OUT, "warmup_go"), os.path.join(HERE, "warmup.go")],
        "run": [os.path.join(OUT, "warmup_go")],
    },
    "csharp": {
        "build": ["dotnet", "build", os.path.join(HERE, "Warmup.csproj"), "-c", "Release",
                  "-o", os.path.join(OUT, "cs"), "--nologo", "-v", "q",
                  f"-p:BaseIntermediateOutputPath={os.path.join(ROOT, 'build', 'obj', 'warmup')}/"],
        "run": ["dotnet", os.path.join(OUT, "cs", "Warmup.dll")],
    },
    "java": {
        "build": ["javac", "-d", OUT, os.path.join(HERE, "Warmup.java")],
        "run": ["java", "-cp", OUT, "Warmup"],
    },
    "java-xint": {
        "build": ["javac", "-d", OUT, os.path.join(HERE, "Warmup.java")],
        "run": ["java", "-Xint", "-cp", OUT, "Warmup"],
    },
    "typescript": {
        "build": ["npx", "--no-install", "tsc", os.path.join(HERE, "warmup.ts"),
                  "--outDir", OUT, "--target", "es2022", "--module", "nodenext",
                  "--moduleResolution", "nodenext", "--skipLibCheck", "--types", "node"],
        "run": ["node", os.path.join(OUT, "warmup.js")],
    },
    "python": {
        "build": None,
        "run": [sys.executable, os.path.join(HERE, "warmup.py")],
    },
}

LABEL = {
    "rust": "Rust      (AOT)",
    "cpp": "C++       (AOT)",
    "go": "Go        (AOT)",
    "csharp": "C#        (JIT)",
    "java": "Java      (JIT)",
    "java-xint": "Java -Xint    ",
    "typescript": "TypeScript(JIT)",
    "python": "Python    (int)",
}

BLOCKS = " ▁▂▃▄▅▆▇█"


def run_target(name: str) -> list[float]:
    spec = TARGETS[name]
    if spec["build"]:
        res = subprocess.run(spec["build"], cwd=ROOT, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  build failed for {name}:\n{res.stderr[:800]}")
            return []
    res = subprocess.run(spec["run"], cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"  run failed for {name}:\n{res.stderr[:800]}")
        return []
    values = []
    for line in res.stdout.splitlines():
        if "," in line:
            try:
                values.append(float(line.split(",")[1]))
            except ValueError:
                pass
    return values


def sparkline(values: list[float], lo: float, hi: float) -> str:
    if hi <= lo:
        return BLOCKS[-1] * len(values)
    out = []
    for v in values:
        frac = (v - lo) / (hi - lo)
        idx = int(frac * (len(BLOCKS) - 1))
        out.append(BLOCKS[max(0, min(len(BLOCKS) - 1, idx))])
    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", nargs="*",
                    default=["rust", "cpp", "go", "csharp", "java", "typescript", "python"])
    ap.add_argument("--xint", action="store_true",
                    help="also run the JVM with the JIT disabled")
    args = ap.parse_args()

    langs = list(args.langs)
    if args.xint and "java-xint" not in langs:
        langs.insert(langs.index("java") + 1 if "java" in langs else len(langs), "java-xint")

    os.makedirs(OUT, exist_ok=True)
    print("Running warm-up curves (60 batches x 200 calls each) ...\n")

    series: dict[str, list[float]] = {}
    for lang in langs:
        if lang not in TARGETS:
            print(f"  unknown target {lang}")
            continue
        print(f"  {lang} ...", flush=True)
        vals = run_target(lang)
        if vals:
            series[lang] = vals

    if not series:
        print("nothing ran")
        return

    print("\n" + "=" * 78)
    print("PER-BATCH TIME  (each cell is one batch; taller = slower)")
    print("=" * 78 + "\n")

    for lang, vals in series.items():
        lo, hi = min(vals), max(vals)
        first, last = vals[0], min(vals[-5:]) if len(vals) >= 5 else vals[-1]
        speedup = first / last if last > 0 else 1.0
        print(f"{LABEL.get(lang, lang):<16} {sparkline(vals, lo, hi)}")
        print(f"{'':<16} first batch {first:8.1f} ms   "
              f"steady state {last:8.1f} ms   "
              f"warm-up gain {speedup:5.2f}x")
        print()

    print("=" * 78)
    print("ABSOLUTE COMPARISON (steady state, lower is better)")
    print("=" * 78 + "\n")
    steady = {l: min(v[-5:]) for l, v in series.items()}
    best = min(steady.values())
    width = 48
    worst = max(steady.values())
    for lang, val in sorted(steady.items(), key=lambda kv: kv[1]):
        bar = "█" * max(1, int(width * val / worst))
        print(f"{LABEL.get(lang, lang):<16} {bar} {val:8.1f} ms  ({val / best:.1f}x)")

    print()
    print("Talking points:")
    print("  * A flat line means the code was already optimal on the first run (AOT).")
    print("  * A falling line means the runtime is COMPILING WHILE YOUR USERS WAIT (JIT).")
    print("  * A spike mid-run in Node or Java is usually a deoptimisation.")
    print("  * Compare `java` with `java -Xint` (--xint) to see what the JIT is worth:")
    print("    that gap is roughly the value the JVM adds over pure interpretation.")


if __name__ == "__main__":
    main()
