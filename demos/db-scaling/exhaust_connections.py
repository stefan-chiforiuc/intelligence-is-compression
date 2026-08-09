#!/usr/bin/env python3
"""Walk into the connection wall on purpose, and look at what it costs.

    bash demos/db-scaling/db.sh up
    python3 demos/db-scaling/exhaust_connections.py

Three things juniors have usually never seen:

  1. `max_connections` is a HARD limit, and it is far lower than they expect.
  2. Hitting it does not degrade the service - it makes healthy pods start
     failing, because they cannot connect at all.
  3. A PostgreSQL connection is an OS PROCESS with real memory behind it.

This is the demo that makes the virtual-threads warning concrete: one JVM can
now run 10,000 concurrent requests, and this is the wall those requests hit.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _db import banner, require_db  # noqa: E402

import psycopg  # noqa: E402


def server_side_stats(url: str) -> tuple[int, str]:
    with psycopg.connect(url) as con:
        n = con.execute("SELECT count(*) FROM pg_stat_activity").fetchone()[0]
        by_state = con.execute("""
            SELECT state, count(*) FROM pg_stat_activity
            WHERE backend_type = 'client backend'
            GROUP BY state ORDER BY 2 DESC
        """).fetchall()
    return n, ", ".join(f"{s or 'null'}={c}" for s, c in by_state)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--attempts", type=int, default=80,
                    help="how many connections to try to open")
    args = ap.parse_args()

    url = require_db("pool_sizing.py")
    banner(url)

    with psycopg.connect(url) as con:
        limit = int(con.execute(
            "SELECT setting FROM pg_settings WHERE name='max_connections'").fetchone()[0])
        reserved = int(con.execute(
            "SELECT setting FROM pg_settings WHERE name='superuser_reserved_connections'"
        ).fetchone()[0])

    print(f"max_connections = {limit}, of which {reserved} are reserved for superusers.")
    print(f"Opening connections one at a time until the server says no ...\n")

    held: list[psycopg.Connection] = []
    failed_at = None
    first_error = ""
    t0 = time.perf_counter()

    try:
        for i in range(1, args.attempts + 1):
            try:
                con = psycopg.connect(url, connect_timeout=5)
                con.execute("SELECT 1")
                held.append(con)
                if i % 10 == 0:
                    print(f"  {i:>3} connections open")
            except Exception as exc:
                failed_at = i
                first_error = str(exc).strip().splitlines()[0]
                break

        elapsed = time.perf_counter() - t0
        print()
        if failed_at:
            print(f"FAILED on connection #{failed_at} after {elapsed:.1f}s")
            print(f"  {first_error}")
        else:
            print(f"Opened all {len(held)} connections without hitting the limit.")
            print(f"  Raise --attempts above {limit} to hit the wall.")

        print()
        try:
            total, states = server_side_stats(url)
            print(f"Server side now: {total} backends  ({states})")
        except Exception as exc:
            # This failure IS the lesson: we cannot even open a MONITORING
            # connection any more.
            print("Could not open a connection to inspect the server:")
            print(f"  {str(exc).strip().splitlines()[0]}")
            print("  ^ note what just happened: your metrics agent, your health")
            print("    check and your on-call engineer's psql are all locked out")
            print("    at exactly the moment you need them.")

    finally:
        for con in held:
            try:
                con.close()
            except Exception:
                pass

    print(f"""
WHAT THIS MEANS IN PRODUCTION
=============================

  THE ARITHMETIC NOBODY DOES
    pods x pool_size <= max_connections - reserved - (your monitoring, your
    migrations, your admin sessions, your read replicas' feedback...)

    10 pods x a pool of 20  = 200 connections
    max_connections         = {limit}
    -> the 6th pod to start cannot connect. It is not slow. It is DOWN.

  AND IT FAILS IN THE WORST POSSIBLE ORDER
    Connections are handed out first-come-first-served. Under load, the pods
    that get starved are the NEW ones - the ones your autoscaler just started
    to handle the load. Scaling up makes it worse. That is the incident.

  WHY THE LIMIT IS SO LOW
    In PostgreSQL every connection is a separate OS PROCESS, with its own work
    memory and catalogue caches - order 5-10 MB each. 500 connections is
    gigabytes of RAM doing no work. MySQL uses threads and is cheaper, but has
    the same shape of limit.

  THE FIXES, IN ORDER
    1. Smaller pools. Genuinely: (cores * 2) + spindles.
    2. A connection POOLER in front - PgBouncer, RDS Proxy, Cloud SQL Auth
       Proxy - so thousands of clients multiplex onto tens of connections.
       This is mandatory for serverless, where every instance has its own pool.
    3. Back-pressure in the app: a bounded queue with a timeout, so you shed
       load deliberately instead of collapsing.
    4. Reserve headroom. `superuser_reserved_connections` exists precisely so
       you can still get in to fix it.

  THE VIRTUAL THREADS CONNECTION
    Before JDK 21, your 200-thread pool was an accidental rate limiter: you
    physically could not have more than 200 requests in flight. Virtual threads
    remove that accident. If you do not replace it with a deliberate limit, the
    first thing you discover is this wall.""")


if __name__ == "__main__":
    main()
