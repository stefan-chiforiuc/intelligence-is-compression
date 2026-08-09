#!/usr/bin/env python3
"""Connection pools: why a BIGGER pool is usually SLOWER.

    python3 demos/db-scaling/pool_sizing.py

Every junior's instinct when a service is slow under load is "increase the
connection pool". It is almost always the wrong move, and this demo shows why
without needing a database: a pool is a queue in front of a fixed resource, and
queueing theory does not care whether the resource is a disk or a CPU.

The model: `workers` concurrent requests, a pool of `size` connections, and a
database that can genuinely do `db_parallelism` things at once. Anything beyond
that does not run faster — it just time-slices, adds context switches, and
inflates every latency including the ones that were fine.

This mirrors the real HikariCP guidance, which surprises people:

    connections = ((core_count * 2) + effective_spindles)

For an 8-core database server that is about 17 — not 200. PostgreSQL's own
docs and the HikariCP wiki both say the same thing: small pools are faster.
"""
from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

# One "query" costs this much service time when the DB is not contended.
BASE_QUERY_MS = 4.0
# How many queries the database can genuinely execute in parallel.
DB_PARALLELISM = 8
# Offered load.
CONCURRENT_REQUESTS = 200
REQUESTS_EACH = 5
# Super-linear penalty per unit of over-subscription (see SimulatedDatabase).
OVERHEAD = 0.08


class SimulatedDatabase:
    """A database that can truly run DB_PARALLELISM queries at once.

    Beyond that, extra concurrency does not add throughput — it adds
    contention. Real databases behave this way for real reasons: a fixed
    number of cores, a fixed number of spindles/IOPS, lock contention, and
    (in PostgreSQL) one OS process per connection.
    """

    def __init__(self, parallelism: int) -> None:
        self.parallelism = parallelism
        self._lock = threading.Lock()
        self._active = 0
        self.peak_active = 0

    def query(self) -> None:
        with self._lock:
            self._active += 1
            active = self._active
            self.peak_active = max(self.peak_active, active)

        # Past the parallelism limit, everyone slows down — and slightly WORSE
        # than proportionally. That super-linear term is not a modelling trick:
        # real databases lose throughput to context switching, lock contention
        # and cache thrashing as concurrency climbs, which is why PostgreSQL
        # throughput measurably declines past roughly 2-3x core count.
        # OVERHEAD is a chosen coefficient, not a measurement — see the note
        # printed at the end.
        over = max(0.0, active - self.parallelism) / self.parallelism
        contention = max(1.0, active / self.parallelism) * (1.0 + OVERHEAD * over)
        time.sleep((BASE_QUERY_MS * contention) / 1000.0)

        with self._lock:
            self._active -= 1


class ConnectionPool:
    """A fixed-size pool. Borrow blocks until a connection is free."""

    def __init__(self, size: int, db: SimulatedDatabase) -> None:
        self.sem = threading.Semaphore(size)
        self.db = db
        self.size = size
        self.wait_total = 0.0
        self._lock = threading.Lock()

    def execute(self) -> None:
        t0 = time.perf_counter()
        with self.sem:                       # borrow a connection (may block)
            waited = time.perf_counter() - t0
            with self._lock:
                self.wait_total += waited
            self.db.query()


def run(pool_size: int) -> tuple[float, float, float, int]:
    db = SimulatedDatabase(DB_PARALLELISM)
    pool = ConnectionPool(pool_size, db)
    latencies: list[float] = []
    lat_lock = threading.Lock()

    def user() -> None:
        for _ in range(REQUESTS_EACH):
            t0 = time.perf_counter()
            pool.execute()
            with lat_lock:
                latencies.append((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=CONCURRENT_REQUESTS) as ex:
        for _ in range(CONCURRENT_REQUESTS):
            ex.submit(user)
    total_s = time.perf_counter() - t0

    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p99 = latencies[int(len(latencies) * 0.99)]
    throughput = len(latencies) / total_s
    return throughput, p50, p99, db.peak_active


def main() -> None:
    print(f"Offered load : {CONCURRENT_REQUESTS} concurrent users x {REQUESTS_EACH} queries")
    print(f"Database     : can truly run {DB_PARALLELISM} queries in parallel, {BASE_QUERY_MS:.0f} ms each")
    print()
    print(f"{'pool size':>10} {'throughput':>14} {'p50':>10} {'p99':>10} {'peak in DB':>12}")
    print("-" * 60)

    rows = []
    for size in (2, 4, 8, 16, 32, 64, 128, 200):
        tput, p50, p99, peak = run(size)
        rows.append((size, tput, p50, p99, peak))
        print(f"{size:>10} {tput:>10.0f} q/s {p50:>8.1f}ms {p99:>8.1f}ms {peak:>12}")

    peak_tput = max(r[1] for r in rows)
    # The "knee": the SMALLEST pool within 5% of the best throughput. That is
    # the one you want — same work done, lowest latency, smallest blast radius.
    knee = next(r for r in rows if r[1] >= peak_tput * 0.95)
    biggest = rows[-1]
    print()
    print(f"Knee at pool size {knee[0]}: {knee[1]:.0f} q/s at p50 {knee[2]:.1f} ms.")
    print(f"Pool size {biggest[0]} buys {biggest[1] / knee[1]:.2f}x the throughput "
          f"for {biggest[2] / knee[2]:.1f}x the p50 latency.")
    print(f"""
WHAT THIS SHOWS
===============

  Throughput peaks near the database's real parallelism ({DB_PARALLELISM}) and then
  FLATTENS or DROPS. Past that point the extra connections do not create
  capacity; they create a bigger crowd fighting over the same capacity.

  Look at what actually changes as the pool grows past the knee:
    * throughput           stops improving, then declines
    * p50                  climbs relentlessly - this is the headline
    * queries in flight    climbs, and every one of them is slower

  The queue does not disappear when you make the pool bigger. It MOVES - out of
  your application, where it is cheap, visible and fair, into the database,
  where it is expensive, invisible and unfair.

  A small pool is a bulkhead. It means requests wait in YOUR process, where you
  can see them, time them, shed them and alert on them.

THE FORMULA WORTH REMEMBERING (HikariCP / PostgreSQL guidance)

      connections = (core_count * 2) + effective_spindles

  For an 8-core DB server: about 17. Not 200. If your pool is bigger than a
  couple of dozen, you almost certainly have a problem you are hiding.

WHAT TO DO INSTEAD WHEN THE POOL IS SATURATED
  1. Make the queries faster (indexes, N+1, fewer round trips).
  2. Hold connections for less time - never across an HTTP call or a
     `Thread.sleep`, and never for the whole request if you only need it twice.
  3. Cache, so the query never happens.
  4. Add read replicas and send reads there.
  5. Only then: more database.

A NOTE ON THIS MODEL, BECAUSE IT MATTERS
  This is a SIMULATION, not a measured database - there is no PostgreSQL in
  this repo. The service time, the parallelism limit and the super-linear
  overhead coefficient are all constants at the top of this file, and you can
  change them. What is robust is the SHAPE: a fixed-capacity resource behind a
  queue always has a knee, past which you buy latency and nothing else.
  Verify it against your own database before quoting a number - and
  demos/db-scaling/GCP-RUNBOOK.md shows how to do exactly that on Cloud SQL.
""".rstrip())


if __name__ == "__main__":
    main()
