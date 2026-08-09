#!/usr/bin/env python3
"""Benchmark harness for the language trade-offs training.

Measures, per (workload, language):
  * wall time      - what the user feels
  * CPU time       - user+sys, the input to the energy/carbon estimate
  * peak RSS       - what you actually have to pay a cloud provider for

It also verifies that every language produced byte-identical output for a
workload. A benchmark you have not verified is just a random number generator,
and that is worth saying out loud in front of juniors.

Usage:
    python3 tools/bench.py --build
    python3 tools/bench.py --reps 5
    python3 tools/bench.py --workloads mandelbrot startup --langs rust go
    python3 tools/bench.py --reps 5 --json results.json --md docs/RESULTS.md
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
# Relative on purpose: every child process is spawned with cwd=ROOT, and a
# relative path keeps the generated report readable on any machine.
DATA = os.path.join("data", "words.txt")

# Order matters: this is the order columns appear in the report, fastest
# family first, so the story reads left to right during the session.
ALL_LANGS = ["rust", "go", "java", "typescript", "python"]

LANG_LABEL = {
    "rust": "Rust",
    "go": "Go",
    "java": "Java",
    "typescript": "TypeScript",
    "python": "Python",
}


def bench_dir(*parts: str) -> str:
    return os.path.join(ROOT, "benchmarks", *parts)


def build_path(*parts: str) -> str:
    return os.path.join(BUILD, *parts)


# --------------------------------------------------------------------------
# Workload definitions
# --------------------------------------------------------------------------
# Each entry: build command (may be None) and run command factory.
# `default_arg` is the size knob; keep it identical across languages.

WORKLOADS: dict[str, dict] = {
    "mandelbrot": {
        "blurb": "CPU-bound float math, no allocation",
        "default_arg": "1000",
        "langs": {
            "rust": {
                "build": ["rustc", "-O", "-C", "target-cpu=native",
                          bench_dir("mandelbrot", "mandelbrot.rs"),
                          "-o", build_path("mandelbrot_rs")],
                "run": [build_path("mandelbrot_rs")],
            },
            "go": {
                "build": ["go", "build", "-o", build_path("mandelbrot_go"),
                          bench_dir("mandelbrot", "mandelbrot.go")],
                "run": [build_path("mandelbrot_go")],
            },
            "java": {
                "build": ["javac", "-d", build_path("java"),
                          bench_dir("mandelbrot", "Mandelbrot.java")],
                "run": ["java", "-cp", build_path("java"), "Mandelbrot"],
            },
            "typescript": {
                "build": None,  # handled by the shared tsc build step
                "run": ["node", build_path("js", "mandelbrot", "mandelbrot.js")],
            },
            "python": {
                "build": None,
                "run": [sys.executable, bench_dir("mandelbrot", "mandelbrot.py")],
            },
        },
    },
    "binarytrees": {
        "blurb": "allocation + GC pressure, millions of tiny objects",
        "default_arg": "16",
        "langs": {
            "rust": {
                "build": ["rustc", "-O", "-C", "target-cpu=native",
                          bench_dir("binarytrees", "binarytrees.rs"),
                          "-o", build_path("binarytrees_rs")],
                "run": [build_path("binarytrees_rs")],
            },
            "go": {
                "build": ["go", "build", "-o", build_path("binarytrees_go"),
                          bench_dir("binarytrees", "binarytrees.go")],
                "run": [build_path("binarytrees_go")],
            },
            "java": {
                "build": ["javac", "-d", build_path("java"),
                          bench_dir("binarytrees", "BinaryTrees.java")],
                "run": ["java", "-cp", build_path("java"), "BinaryTrees"],
            },
            "typescript": {
                "build": None,
                "run": ["node", "--stack-size=10000", build_path("js", "binarytrees", "binarytrees.js")],
            },
            "python": {
                "build": None,
                "run": [sys.executable, bench_dir("binarytrees", "binarytrees.py")],
            },
        },
    },
    "wordfreq": {
        "blurb": "file I/O, strings, hash map, sort - closest to real code",
        "default_arg": DATA,
        "langs": {
            "rust": {
                "build": ["rustc", "-O", "-C", "target-cpu=native",
                          bench_dir("wordfreq", "wordfreq.rs"),
                          "-o", build_path("wordfreq_rs")],
                "run": [build_path("wordfreq_rs")],
            },
            "go": {
                "build": ["go", "build", "-o", build_path("wordfreq_go"),
                          bench_dir("wordfreq", "wordfreq.go")],
                "run": [build_path("wordfreq_go")],
            },
            "java": {
                "build": ["javac", "-d", build_path("java"),
                          bench_dir("wordfreq", "WordFreq.java")],
                "run": ["java", "-cp", build_path("java"), "WordFreq"],
            },
            "typescript": {
                "build": None,
                "run": ["node", build_path("js", "wordfreq", "wordfreq.js")],
            },
            "python": {
                "build": None,
                "run": [sys.executable, bench_dir("wordfreq", "wordfreq.py")],
            },
        },
    },
    "startup": {
        "blurb": "cold start: process spawn + runtime boot, no real work",
        "default_arg": "21",
        "langs": {
            "rust": {
                "build": ["rustc", "-O", bench_dir("startup", "hello.rs"),
                          "-o", build_path("hello_rs")],
                "run": [build_path("hello_rs")],
            },
            "go": {
                "build": ["go", "build", "-o", build_path("hello_go"),
                          bench_dir("startup", "hello.go")],
                "run": [build_path("hello_go")],
            },
            "java": {
                "build": ["javac", "-d", build_path("java"),
                          bench_dir("startup", "Hello.java")],
                "run": ["java", "-cp", build_path("java"), "Hello"],
            },
            "typescript": {
                "build": None,
                "run": ["node", build_path("js", "startup", "hello.js")],
            },
            "python": {
                "build": None,
                "run": [sys.executable, bench_dir("startup", "hello.py")],
            },
        },
    },
}

TS_SOURCES = [
    bench_dir("mandelbrot", "mandelbrot.ts"),
    bench_dir("binarytrees", "binarytrees.ts"),
    bench_dir("wordfreq", "wordfreq.ts"),
    bench_dir("startup", "hello.ts"),
]


# --------------------------------------------------------------------------
# Measurement
# --------------------------------------------------------------------------

class RunResult:
    __slots__ = ("wall", "cpu", "max_rss_kb", "stdout", "exit_code")

    def __init__(self, wall: float, cpu: float, max_rss_kb: int, stdout: str, exit_code: int):
        self.wall = wall
        self.cpu = cpu
        self.max_rss_kb = max_rss_kb
        self.stdout = stdout
        self.exit_code = exit_code


def measure(cmd: list[str], cwd: str) -> RunResult:
    """Run `cmd` once, returning wall/CPU/peak-RSS for that process tree.

    We redirect to temp files rather than pipes so there is no reader-thread
    overhead in the measurement, and we reap with os.wait4 so we get the
    child's own rusage instead of a process-wide running maximum.
    """
    with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
        t0 = time.perf_counter()
        proc = subprocess.Popen(cmd, stdout=out_f, stderr=err_f, cwd=cwd)
        _, status, ru = os.wait4(proc.pid, 0)
        wall = time.perf_counter() - t0
        proc.returncode = os.waitstatus_to_exitcode(status)

        out_f.seek(0)
        stdout = out_f.read().decode("utf-8", "replace")
        if proc.returncode != 0:
            err_f.seek(0)
            sys.stderr.write(err_f.read().decode("utf-8", "replace")[-4000:])

    return RunResult(
        wall=wall,
        cpu=ru.ru_utime + ru.ru_stime,
        max_rss_kb=ru.ru_maxrss,
        stdout=stdout,
        exit_code=proc.returncode,
    )


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def build_typescript() -> bool:
    """Compile all TS sources to build/js.

    Prefers a real `tsc` compile (which is what you ship in production).
    Falls back to Node's built-in type stripping if tsc or @types/node is not
    available, so the repo still runs on a laptop with no network.
    """
    os.makedirs(build_path("js"), exist_ok=True)
    res = subprocess.run(["npx", "--no-install", "tsc", "-p", "tsconfig.json"],
                         cwd=ROOT, capture_output=True, text=True)
    if res.returncode == 0:
        return True

    print("  tsc unavailable (run `npm install`); falling back to Node's")
    print("  built-in type stripping. Types are erased either way - which is")
    print("  precisely the lesson in section 2.")
    for src in TS_SOURCES:
        workload = os.path.basename(os.path.dirname(src))
        dst_dir = build_path("js", workload)
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copyfile(src, os.path.join(dst_dir, os.path.basename(src)))
    return False


def build_all(langs: list[str], workloads: list[str]) -> None:
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(build_path("java"), exist_ok=True)

    done: set[tuple] = set()
    for wl in workloads:
        for lang in langs:
            spec = WORKLOADS[wl]["langs"].get(lang)
            if not spec or not spec["build"]:
                continue
            key = tuple(spec["build"])
            if key in done:
                continue
            done.add(key)
            print(f"  building {wl}/{lang} ...", flush=True)
            res = subprocess.run(spec["build"], cwd=ROOT, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"  BUILD FAILED {wl}/{lang}:\n{res.stdout}\n{res.stderr}")
                sys.exit(1)

    if "typescript" in langs:
        print("  building typescript ...", flush=True)
        build_typescript()
        # If tsc emitted .ts passthrough, point the runner at it.
        for wl in workloads:
            spec = WORKLOADS[wl]["langs"].get("typescript")
            if not spec:
                continue
            js = spec["run"][-1]
            if not os.path.exists(js) and os.path.exists(js[:-3] + ".ts"):
                spec["run"][-1] = js[:-3] + ".ts"


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------

def fmt_time(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.1f} ms"
    return f"{seconds:.2f} s"


def fmt_mem(kb: int) -> str:
    mb = kb / 1024.0
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"


def machine_info() -> dict:
    info = {
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "python": platform.python_version(),
    }
    try:
        with open("/proc/cpuinfo") as fh:
            for line in fh:
                if line.startswith("model name"):
                    info["cpu_model"] = line.split(":", 1)[1].strip()
                    break
    except OSError:
        pass
    for lang, cmd in (
        ("go", ["go", "version"]),
        ("rust", ["rustc", "--version"]),
        ("node", ["node", "--version"]),
        ("java", ["java", "-version"]),
    ):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = (res.stdout or res.stderr).strip().splitlines()
            info[f"{lang}_version"] = out[-1].strip() if out else "?"
        except Exception:
            info[f"{lang}_version"] = "not found"
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workloads", nargs="*", default=list(WORKLOADS))
    ap.add_argument("--langs", nargs="*", default=ALL_LANGS)
    ap.add_argument("--reps", type=int, default=5, help="measured runs per cell")
    ap.add_argument("--warmup", type=int, default=1, help="unmeasured runs first")
    ap.add_argument("--build", action="store_true", help="build only, then exit")
    ap.add_argument("--no-build", action="store_true", help="skip building")
    ap.add_argument("--json", help="write raw results here")
    ap.add_argument("--md", help="write a Markdown report here")
    ap.add_argument("--render-only", metavar="JSON",
                    help="re-render the Markdown report from a previous run, measuring nothing")
    args = ap.parse_args()

    if args.render_only:
        with open(args.render_only) as fh:
            previous = json.load(fh)
        write_markdown(previous, args.md or "docs/RESULTS.md", args.langs)
        print(f"wrote {args.md or 'docs/RESULTS.md'} from {args.render_only}")
        return

    for wl in args.workloads:
        if wl not in WORKLOADS:
            ap.error(f"unknown workload {wl!r}; choose from {list(WORKLOADS)}")
    for lang in args.langs:
        if lang not in ALL_LANGS:
            ap.error(f"unknown language {lang!r}; choose from {ALL_LANGS}")

    if "wordfreq" in args.workloads and not os.path.exists(os.path.join(ROOT, DATA)):
        print(f"missing {DATA}; generating it now ...")
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "gen_words.py"), DATA],
                       cwd=ROOT, check=True)

    if not args.no_build:
        print("Building ...")
        build_all(args.langs, args.workloads)
        if args.build:
            print("Build complete.")
            return

    results: dict = {"machine": machine_info(), "reps": args.reps, "workloads": {}}

    for wl in args.workloads:
        spec = WORKLOADS[wl]
        arg = spec["default_arg"]
        print(f"\n=== {wl} ({spec['blurb']}) arg={arg} ===")
        results["workloads"][wl] = {"blurb": spec["blurb"], "arg": str(arg), "langs": {}}
        outputs: dict[str, str] = {}

        for lang in args.langs:
            lspec = spec["langs"].get(lang)
            if not lspec:
                continue
            cmd = [*lspec["run"], str(arg)]

            for _ in range(args.warmup):
                measure(cmd, ROOT)

            runs = [measure(cmd, ROOT) for _ in range(args.reps)]
            failed = [r for r in runs if r.exit_code != 0]
            if failed:
                print(f"  {LANG_LABEL[lang]:<11} FAILED (exit {failed[0].exit_code})")
                results["workloads"][wl]["langs"][lang] = {"error": failed[0].exit_code}
                continue

            walls = sorted(r.wall for r in runs)
            cpus = [r.cpu for r in runs]
            rss = max(r.max_rss_kb for r in runs)
            outputs[lang] = runs[0].stdout.strip()

            cell = {
                "wall_min": walls[0],
                "wall_median": statistics.median(walls),
                "wall_max": walls[-1],
                "cpu_median": statistics.median(cpus),
                "max_rss_kb": rss,
            }
            results["workloads"][wl]["langs"][lang] = cell
            print(f"  {LANG_LABEL[lang]:<11} "
                  f"wall {fmt_time(cell['wall_median']):>9}  "
                  f"cpu {fmt_time(cell['cpu_median']):>9}  "
                  f"peak {fmt_mem(rss):>9}")

        # Correctness cross-check.
        distinct = set(outputs.values())
        if len(distinct) > 1:
            print("  !! OUTPUT MISMATCH between languages:")
            for lang, out in outputs.items():
                head = out.splitlines()[0] if out else "<empty>"
                print(f"     {LANG_LABEL[lang]:<11} {head[:70]}")
            results["workloads"][wl]["output_match"] = False
        else:
            results["workloads"][wl]["output_match"] = True
            print("  output verified identical across all languages")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nwrote {args.json}")

    if args.md:
        write_markdown(results, args.md, args.langs)
        print(f"wrote {args.md}")


def write_markdown(results: dict, path: str, langs: list[str]) -> None:
    m = results["machine"]
    lines = [
        "# Measured results",
        "",
        "> Generated by `python3 tools/bench.py --md docs/RESULTS.md`.",
        "> **Re-run this on the machine you present from.** The absolute numbers",
        "> below are not the point; the ratios and the shape of the table are.",
        "",
        "## Machine",
        "",
        f"- CPU: {m.get('cpu_model', m.get('processor', '?'))} ({m.get('cpu_count')} cores)",
        f"- OS: {m.get('platform')}",
        f"- Rust: {m.get('rust_version')}",
        f"- Go: {m.get('go_version')}",
        f"- Java: {m.get('java_version')}",
        f"- Node: {m.get('node_version')}",
        f"- Python: {m.get('python')}",
        f"- Repetitions per cell: {results['reps']} (median reported)",
        "",
    ]

    for wl, data in results["workloads"].items():
        lines += [
            f"## {wl}",
            "",
            f"_{data['blurb']}_ — argument `{data['arg']}`",
            "",
            "| Language | Wall (median) | CPU | Peak RSS | vs fastest |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
        cells = {l: c for l, c in data["langs"].items() if "error" not in c}
        if cells:
            fastest = min(c["wall_median"] for c in cells.values())
        else:
            fastest = 1.0
        for lang in langs:
            cell = data["langs"].get(lang)
            if not cell:
                continue
            if "error" in cell:
                lines.append(f"| {LANG_LABEL[lang]} | failed | | | |")
                continue
            ratio = cell["wall_median"] / fastest
            lines.append(
                f"| {LANG_LABEL[lang]} "
                f"| {fmt_time(cell['wall_median'])} "
                f"| {fmt_time(cell['cpu_median'])} "
                f"| {fmt_mem(cell['max_rss_kb'])} "
                f"| {ratio:.1f}x |"
            )
        match = "yes" if data.get("output_match") else "**NO - investigate**"
        lines += ["", f"Output identical across languages: {match}", ""]

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
