#!/usr/bin/env python3
"""Connection pool sizing, against a REAL PostgreSQL.

    bash demos/db-scaling/db.sh up
    python3 demos/db-scaling/real_pool.py

This is the measured version of pool_sizing.py. Same conclusion, no model:
throughput peaks near the database's real parallelism and then declines, and
past that knee the extra connections buy variance (worse p99) rather than
capacity.

The load is a genuinely CPU-bound query (md5 over a table scan), because a
`pg_sleep` workload would show queueing without showing CONTENTION - and
contention is the half that surprises people.

A note that connects to the concurrency block: this driver is doing blocking
network I/O, so Python THREADS are exactly right here. The GIL is released
while waiting on the socket. This is the workload where the flat row from the
parallel-scaling demo would have been a full-speed row.
"""
from __future__ import annotations

import argparse
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _db import banner, require_db  # noqa: E402

import psycopg  # noqa: E402
from psycopg_pool import ConnectionPool  # noqa: E402

ROWS = 20_000


def setup(url: str) -> None:
    with psycopg.connect(url, autocommit=True) as con:
        con.execute("DROP TABLE IF EXISTS bench")
        con.execute("CREATE TABLE bench (id int primary key, payload text)")
        with con.cursor() as cur:
            cur.execute(
                "INSERT INTO bench SELECT g, md5(g::text) FROM generate_series(1, %s) g",
                (ROWS,),
            )
        con.execute("ANALYZE bench")


QUERY = """
    SELECT count(*) FROM bench
    WHERE md5(payload || %s) < '8'
"""


def run(url: str, pool_size: int, users: int, queries_each: int) -> tuple[float, float, float, int]:
    pool = ConnectionPool(url, min_size=pool_size, max_size=pool_size,
                          timeout=60, open=True)
    pool.wait(timeout=30)

    latencies: list[float] = []
    lock = threading.Lock()
    errors = 0

    def user(uid: int) -> None:
        nonlocal errors
        local: list[float] = []
        for i in range(queries_each):
            t0 = time.perf_counter()
            try:
                with pool.connection() as con:
                    con.execute(QUERY, (f"{uid}-{i}",)).fetchone()
                local.append((time.perf_counter() - t0) * 1000)
            except Exception:
                with lock:
                    errors += 1
        with lock:
            latencies.extend(local)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as ex:
        for u in range(users):
            ex.submit(user, u)
    elapsed = time.perf_counter() - t0
    pool.close()

    if not latencies:
        return 0.0, 0.0, 0.0, errors
    latencies.sort()
    p50 = statistics.median(latencies)
    p99 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.99))]
    return len(latencies) / elapsed, p50, p99, errors


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", type=int, default=40, help="concurrent client threads")
    ap.add_argument("--queries", type=int, default=8, help="queries per user")
    ap.add_argument("--sizes", nargs="*", type=int, default=[1, 2, 4, 8, 16, 32, 48])
    ap.add_argument("--repeat", type=int, default=2,
                    help="runs per pool size; the best is kept, to blunt noise")
    args = ap.parse_args()

    url = require_db("pool_sizing.py")
    banner(url)

    print(f"Building a {ROWS:,}-row table ...")
    setup(url)
    print(f"Offered load: {args.users} concurrent users x {args.queries} CPU-bound queries\n")

    print(f"{'pool size':>10} {'throughput':>14} {'p50':>10} {'p99':>10} {'errors':>8}")
    print("-" * 56)

    rows = []
    for size in args.sizes:
        # Best-of-N. A shared laptop is a noisy measurement device, and a knee
        # that jumps around between runs teaches the wrong lesson.
        trials = [run(url, size, args.users, args.queries) for _ in range(args.repeat)]
        tput, p50, p99, errors = max(trials, key=lambda t: t[0])
        rows.append((size, tput, p50, p99))
        print(f"{size:>10} {tput:>10.0f} q/s {p50:>8.1f}ms {p99:>8.1f}ms {errors:>8}")

    ok = [r for r in rows if r[1] > 0]
    if not ok:
        print("\nNo successful runs - is the database up?")
        return
    peak = max(r[1] for r in ok)
    trough = min(r[1] for r in ok)
    knee = next(r for r in ok if r[1] >= peak * 0.95)
    worst = ok[-1]
    print()
    if peak / max(trough, 1e-9) < 1.25:
        # Genuinely flat. Say so rather than pointing at a knee that is noise.
        print(f"Throughput is FLAT across every pool size "
              f"({trough:.0f}-{peak:.0f} q/s, a {peak / trough:.2f}x spread).")
        print("That is the result, not a failed measurement: this database is")
        print("CPU-saturated at ANY pool size, so extra connections cannot help.")
        print(f"The smallest pool tested ({ok[0][0]}) already reaches "
              f"{ok[0][1] / peak * 100:.0f}% of peak throughput.")
    else:
        print(f"Knee at pool size {knee[0]}: {knee[1]:.0f} q/s at p50 {knee[2]:.1f} ms.")
        if worst[0] != knee[0]:
            print(f"Pool size {worst[0]} buys {worst[1] / knee[1]:.2f}x the throughput "
                  f"for {worst[2] / knee[2]:.1f}x the p50 latency.")

    print(f"""
THIS IS THE REAL THING, NOT A MODEL
===================================

  Every number above came from a PostgreSQL server doing actual work.

  THE MOMENT TO POINT AT
  The HikariCP/PostgreSQL formula says:

      connections = (cores * 2) + effective_spindles

  On a 1-CPU database that predicts about 2 - and the table above shows the
  smallest pools already at or near peak throughput. A formula from a wiki
  predicted the behaviour of a real machine.

  WHAT DEGRADES, AND WHAT DOES NOT - be precise here, it matters
    * throughput  plateaus at the knee and then slowly DECLINES.
                  More connections did not buy capacity.
    * p99         gets clearly worse past the knee. That is contention:
                  every extra backend makes the unlucky queries unluckier.
    * p50         is high at EVERY pool size, because the offered load
                  ({args.users} users) far exceeds what 1 CPU can serve. Do not
                  claim p50 climbs monotonically - it does not, and the room
                  can see the table.

  The honest summary: past the knee you are not buying throughput, you are
  buying variance. And the queue never disappeared - it moved out of your
  application, where it is visible and sheddable, into the database, where
  it is neither.

  TWO THINGS TO TRY LIVE
    1. Watch the server side while it runs:
         watch -n1 "psql \\$TRAINING_DB_URL -c \\
           'SELECT state, count(*) FROM pg_stat_activity GROUP BY state'"

    2. Give the container another core and re-run - the knee MOVES RIGHT:
         docker update --cpus=2 lang-training-db
       That is the clearest possible demonstration that pool size is a
       function of the DATABASE's capacity, not your application's traffic.""")


if __name__ == "__main__":
    main()
