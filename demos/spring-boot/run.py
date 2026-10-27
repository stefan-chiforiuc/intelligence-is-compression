#!/usr/bin/env python3
"""Spring Boot: what a real framework costs at startup, and what its request
thread pool does under load.

    python3 demos/spring-boot/run.py               # both parts
    python3 demos/spring-boot/run.py --part 1      # cold start only
    python3 demos/spring-boot/run.py --part 2      # thread pool only

Part 1 answers the question the `startup` benchmark cannot: `Hello.java` boots
in tens of milliseconds, but nobody ships Hello.java. What does a framework actually cost?

Part 2 answers "what is a request thread pool for". Tomcat's default is 200
threads - a number most teams have never looked at, let alone chosen - and it
is a hard ceiling on how many requests can be in flight.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import statistics
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

def startup_floor() -> dict:
    """Bare-runtime cold starts (ms) from the last `make bench`, if present."""
    ref = {"native": 1.5, "csharp": 45.0, "java": 46.0, "measured": False}
    try:
        with open(os.path.join(ROOT, "results.json")) as fh:
            langs = json.load(fh)["workloads"]["startup"]["langs"]
        ms = lambda k: langs[k]["wall_median"] * 1000
        return {"native": min(ms(k) for k in ("rust", "cpp", "go")),
                "csharp": ms("csharp"), "java": ms("java"), "measured": True}
    except (OSError, KeyError, ValueError):
        return ref

JAR = os.path.join(HERE, "target", "spring-cold-start-1.0.0.jar")


def _free_port() -> int:
    """An OS-assigned free port. A fixed port (e.g. 18080) can already be
    bound by something else on the machine - a container, a colleague's
    service, WSL's port-forwarding relay - and every scenario below would
    then fail identically with no clue why."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"

STARTED_RE = re.compile(r"Started TrainingApp in ([0-9.]+) seconds")


def ensure_jar() -> None:
    if os.path.exists(JAR):
        return
    print("Building the Spring Boot app (first run downloads dependencies) ...")
    res = subprocess.run(["mvn", "-q", "-B", "-DskipTests", "package"],
                         cwd=HERE, capture_output=True, text=True, timeout=1800)
    if res.returncode != 0 or not os.path.exists(JAR):
        print(res.stdout[-2000:])
        print(res.stderr[-2000:])
        sys.exit("maven build failed")


def wait_until_up(proc: subprocess.Popen, timeout: float = 90.0) -> float | None:
    """Seconds from spawn until the app answers a real request."""
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < timeout:
        if proc.poll() is not None:
            return None
        try:
            with urllib.request.urlopen(f"{BASE}/hello", timeout=1) as r:
                if r.status == 200:
                    return time.perf_counter() - t0
        except Exception:
            time.sleep(0.02)
    return None


def start_app(extra_args: list[str], extra_props: list[str]) -> tuple[subprocess.Popen, list[str]]:
    log: list[str] = []
    cmd = ["java", *extra_args, "-jar", JAR, f"--server.port={PORT}", *extra_props]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, cwd=HERE)

    def drain() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            log.append(line)

    threading.Thread(target=drain, daemon=True).start()
    return proc, log


def stop_app(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


# --------------------------------------------------------------------------
# Part 1 - cold start
# --------------------------------------------------------------------------

SCENARIOS = [
    ("Spring Boot, defaults", [], []),
    ("+ -XX:TieredStopAtLevel=1", ["-XX:TieredStopAtLevel=1"], []),
    ("+ lazy initialisation", ["-XX:TieredStopAtLevel=1"],
     ["--spring.main.lazy-initialization=true"]),
    ("+ CDS off (for contrast)", ["-Xshare:off"], []),
]


def part1(reps: int) -> None:
    print("=" * 76)
    print("PART 1 - COLD START: what a framework actually costs")
    print("=" * 76)
    print()
    print(f"{'configuration':<32} {'time to first 200':>18} {'Spring reports':>16}")
    print("-" * 76)

    # One unmeasured start first. Otherwise the very first scenario also pays
    # for pulling a 26 MB jar into the OS page cache, and it looks slower than
    # configurations that are genuinely worse. Warm the cache, then measure.
    print("  (warming the page cache with one unmeasured start ...)")
    warm, _ = start_app([], [])
    wait_until_up(warm)
    stop_app(warm)
    print()

    baseline = None
    for label, jvm_args, props in SCENARIOS:
        times, reported = [], []
        for _ in range(reps):
            proc, log = start_app(jvm_args, props)
            t = wait_until_up(proc)
            stop_app(proc)
            if t is None:
                print(f"{label:<32} {'FAILED':>18}")
                break
            times.append(t)
            m = STARTED_RE.search("".join(log))
            if m:
                reported.append(float(m.group(1)))
        if not times:
            continue
        med = statistics.median(times)
        if baseline is None:
            baseline = med
        rep = f"{statistics.median(reported):.2f} s" if reported else "-"
        print(f"{label:<32} {med * 1000:>15.0f} ms {rep:>16}")

    print()
    floor = startup_floor()
    print("FOR COMPARISON (from the main benchmark suite" +
          (", same machine)" if floor["measured"] else "; reference-machine figures, run `make bench` for yours)"))
    print(f"  {'Go / Rust / C++ hello':<32} {floor['native']:>12.1f} ms")
    print(f"  {'bare .NET Hello.cs':<32} {floor['csharp']:>12.0f} ms")
    print(f"  {'bare JVM Hello.java':<32} {floor['java']:>12.0f} ms")
    if baseline:
        print(f"  {'Spring Boot (this app)':<32} {baseline * 1000:>12.0f} ms"
              f"   = {baseline * 1000 / floor['java']:.0f}x the bare JVM")
    print()
    print("""WHAT TO SAY
  The `startup` benchmark measures the FLOOR: a JVM that loads one class.
  This measures a framework doing what frameworks do - classpath scanning,
  bean definition, autoconfiguration, Tomcat startup, connection pool warmup.

  And this app is TINY. It has four endpoints and no security, no JPA, no
  Kafka, no service mesh sidecar. A real enterprise service is commonly
  15-60 seconds. Ask the room what their app's startup time is; most do not
  know, which is itself the lesson.

  This is the number that decides:
    * whether Spring Boot on Lambda needs SnapStart or is simply the wrong tool
    * how long your rolling deploy takes (startup x pods / parallelism)
    * how fast your autoscaler can respond to a spike
    * what your Kubernetes startupProbe failureThreshold has to be

  Note that lazy initialisation is not free: it moves work from startup to the
  FIRST REQUEST that touches each bean, so your p99 gets worse right after a
  deploy. It is a good trade for a CLI or a scale-to-zero function, and a bad
  one for a service that must be fast immediately after rollout.""")


# --------------------------------------------------------------------------
# Part 2 - the request thread pool
# --------------------------------------------------------------------------

def load(path: str, users: int, requests_each: int) -> tuple[float, float, float, int]:
    latencies: list[float] = []
    errors = 0
    lock = threading.Lock()

    def user() -> None:
        nonlocal errors
        local = []
        for _ in range(requests_each):
            t0 = time.perf_counter()
            try:
                with urllib.request.urlopen(f"{BASE}{path}", timeout=60) as r:
                    r.read()
                local.append((time.perf_counter() - t0) * 1000)
            except Exception:
                with lock:
                    errors += 1
        with lock:
            latencies.extend(local)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as ex:
        for _ in range(users):
            ex.submit(user)
    elapsed = time.perf_counter() - t0

    if not latencies:
        return 0.0, 0.0, 0.0, errors
    latencies.sort()
    p50 = statistics.median(latencies)
    p99 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.99))]
    return len(latencies) / elapsed, p50, p99, errors


POOL_SCENARIOS = [
    ("threads.max=10",            ["--server.tomcat.threads.max=10"]),
    ("threads.max=50",            ["--server.tomcat.threads.max=50"]),
    ("threads.max=200 (default)", ["--server.tomcat.threads.max=200"]),
    ("virtual threads",           ["--spring.threads.virtual.enabled=true"]),
]


def part2(users: int, requests_each: int, sleep_ms: int, path: str | None = None) -> None:
    target = path or f"/io?ms={sleep_ms}"
    print()
    print("=" * 76)
    print("PART 2 - THE REQUEST THREAD POOL")
    print("=" * 76)
    print()
    print(f"Load: {users} concurrent users x {requests_each} requests to "
          f"{target} (blocking)")
    # Little's law: with N requests in flight each taking S seconds, throughput
    # is N/S. Unlimited concurrency means all `users` are in flight at once.
    ideal = users / (sleep_ms / 1000.0)
    print(f"Little's law: with all {users} in flight at {sleep_ms} ms each, the")
    print(f"ceiling is {ideal:.0f} req/s. A pool of P caps you at P/{sleep_ms}ms instead.")
    print()
    print(f"{'configuration':<28} {'throughput':>13} {'p50':>10} {'p99':>10} "
          f"{'errors':>7}  {'serving thread':>16}")
    print("-" * 92)

    for label, props in POOL_SCENARIOS:
        proc, _log = start_app([], props)
        if wait_until_up(proc) is None:
            print(f"{label:<28} FAILED TO START")
            stop_app(proc)
            continue
        try:
            who = "?"
            try:
                with urllib.request.urlopen(f"{BASE}/whoami", timeout=5) as r:
                    who = "virtual" if json.load(r).get("virtual") else "platform"
            except Exception:
                pass
            load(target, 4, 2)                        # warm up
            tput, p50, p99, errors = load(target, users, requests_each)
            print(f"{label:<28} {tput:>9.0f} r/s {p50:>8.0f}ms {p99:>8.0f}ms "
                  f"{errors:>7}  {who:>16}")
        finally:
            stop_app(proc)

    print(f"""
WHAT TO POINT AT

  1. THE POOL IS A HARD CEILING ON CONCURRENCY.
     With threads.max=10, only 10 requests can be in flight. Each takes
     {sleep_ms} ms, so throughput cannot exceed ~{1000 / sleep_ms * 10:.0f} r/s no matter how many
     users arrive. The rest queue in Tomcat's accept queue, and their latency
     is queue time, not work time.

  2. RAISING IT HELPS - UNTIL IT DOES NOT.
     Going 10 -> 200 buys real throughput here, because these threads are
     SLEEPING, not computing. Try the same sweep against /cpu and the curve
     flattens at your core count instead. Which knob helps depends entirely on
     whether you are waiting or computing - the same question as Block 4.

  3. VIRTUAL THREADS REMOVE THE CEILING.
     `spring.threads.virtual.enabled=true` and threads.max stops mattering:
     each request gets its own virtual thread and blocking is cheap. Note the
     serving-thread column changed from `platform` to `virtual` - that is the
     proof it actually switched on.

  4. AND THAT IS EXACTLY WHERE THE DANGER IS.
     Your 200-thread pool was ALSO an accidental rate limiter. It guaranteed
     you never had more than 200 requests concurrently reaching for a Hikari
     pool of 10, or hammering a downstream service. Remove it without adding a
     deliberate limit and the next bottleneck finds out the hard way.

     Run this to watch it happen, with the database from Block 5b:
       make db-up
       python3 demos/spring-boot/run.py --part 2 --path '/db?sleepMs=100'
     Hikari's default pool here is 10. Virtual threads will not make it 11.""")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", type=int, choices=[1, 2], help="run only one part")
    ap.add_argument("--reps", type=int, default=3, help="cold-start repetitions")
    ap.add_argument("--users", type=int, default=100)
    ap.add_argument("--requests", type=int, default=5)
    ap.add_argument("--sleep-ms", type=int, default=100)
    ap.add_argument("--path", help="override the load target, e.g. '/db?sleepMs=100'")
    args = ap.parse_args()

    ensure_jar()
    if args.part in (None, 1):
        part1(args.reps)
    if args.part in (None, 2):
        part2(args.users, args.requests, args.sleep_ms, args.path)


if __name__ == "__main__":
    main()
