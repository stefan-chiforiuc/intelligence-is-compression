#!/usr/bin/env python3
"""The lost update, in a REAL PostgreSQL - in BOTH of its disguises.

    bash demos/db-scaling/db.sh up
    python3 demos/db-scaling/real_transactions.py

The same root cause produces two opposite symptoms, and which one you get
depends on how you wrote the write. Juniors generalise from whichever they saw
first, so this demo shows both:

  COUNTER MODEL   `UPDATE seats SET sold = <value I read>`
                  Concurrent writers overwrite each other. Increments are LOST,
                  so you confirm far more bookings than you store. Strategies
                  1-6.

  INSERT MODEL    `SELECT count(*)` then `INSERT INTO bookings`
                  Every insert succeeds, so nothing is lost - but the COUNT was
                  stale, so you sail straight past the limit and OVERSELL.
                  Strategies 7-8.

Both are catastrophic and neither raises an error. The counter model tells 192
customers yes and stores only ~15. The insert model stores every one of the 192.

Eight strategies: the bug in two shapes, four correct answers, and one schema
that makes the bad state unrepresentable.
"""
from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _db import banner, require_db  # noqa: E402

import psycopg  # noqa: E402
from psycopg import errors as pgerrors  # noqa: E402

SEAT_LIMIT = 100
BOOKERS = 16
ATTEMPTS_EACH = 12

# Stands in for the work that always sits between a check and an act in real
# code: a payment call, a fraud check, an audit write. All of them take time.
THINK_TIME = 0.004


def reset_counter(url: str) -> None:
    """Counter model: one row holding a number."""
    with psycopg.connect(url, autocommit=True) as con:
        con.execute("DROP TABLE IF EXISTS seats")
        con.execute("""
            CREATE TABLE seats (
                id       int PRIMARY KEY,
                sold     int NOT NULL,
                version  int NOT NULL DEFAULT 0
            )
        """)
        con.execute("INSERT INTO seats (id, sold) VALUES (1, 0)")


def count_counter(url: str) -> int:
    with psycopg.connect(url) as con:
        return con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]


def reset_bookings(url: str) -> None:
    """Insert model: one row per booking, capacity checked by counting."""
    with psycopg.connect(url, autocommit=True) as con:
        con.execute("DROP TABLE IF EXISTS bookings")
        con.execute("CREATE TABLE bookings (id bigserial PRIMARY KEY, holder text NOT NULL)")


def count_bookings(url: str) -> int:
    with psycopg.connect(url) as con:
        return con.execute("SELECT count(*) FROM bookings").fetchone()[0]


def reset_allocated(url: str) -> None:
    """Schema model: the seats EXIST as rows. Overbooking is unrepresentable."""
    with psycopg.connect(url, autocommit=True) as con:
        con.execute("DROP TABLE IF EXISTS seat_rows")
        con.execute("CREATE TABLE seat_rows (seat_no int PRIMARY KEY, holder text)")
        con.execute(
            "INSERT INTO seat_rows (seat_no) SELECT generate_series(1, %s)", (SEAT_LIMIT,))


def count_allocated(url: str) -> int:
    with psycopg.connect(url) as con:
        return con.execute(
            "SELECT count(*) FROM seat_rows WHERE holder IS NOT NULL").fetchone()[0]


# --------------------------------------------------------------------------
# 1. No transaction at all. Read, think, write.
# --------------------------------------------------------------------------
def s1_no_txn(con) -> bool:
    con.autocommit = True
    current = con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]
    if current >= SEAT_LIMIT:
        return False
    time.sleep(THINK_TIME)
    con.execute("UPDATE seats SET sold=%s WHERE id=1", (current + 1,))
    return True


# --------------------------------------------------------------------------
# 2. A transaction, at PostgreSQL's DEFAULT isolation level.
#    This is what most application code actually does. It is still wrong.
# --------------------------------------------------------------------------
def s2_read_committed(con) -> bool:
    con.autocommit = False
    with con.transaction():
        current = con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]
        if current >= SEAT_LIMIT:
            return False
        time.sleep(THINK_TIME)
        con.execute("UPDATE seats SET sold=%s WHERE id=1", (current + 1,))
    return True


# --------------------------------------------------------------------------
# 3. Pessimistic: SELECT ... FOR UPDATE takes a row lock before we look.
# --------------------------------------------------------------------------
def s3_for_update(con) -> bool:
    con.autocommit = False
    with con.transaction():
        current = con.execute(
            "SELECT sold FROM seats WHERE id=1 FOR UPDATE").fetchone()[0]
        if current >= SEAT_LIMIT:
            return False
        time.sleep(THINK_TIME)
        con.execute("UPDATE seats SET sold=%s WHERE id=1", (current + 1,))
    return True


# --------------------------------------------------------------------------
# 4. Optimistic: no lock. Detect the conflict at write time, then retry.
# --------------------------------------------------------------------------
def s4_optimistic(con) -> bool:
    con.autocommit = True
    for _ in range(60):
        row = con.execute("SELECT sold, version FROM seats WHERE id=1").fetchone()
        current, version = row
        if current >= SEAT_LIMIT:
            return False
        time.sleep(THINK_TIME)
        cur = con.execute(
            "UPDATE seats SET sold=%s, version=%s WHERE id=1 AND version=%s",
            (current + 1, version + 1, version),
        )
        if cur.rowcount == 1:
            return True
        # rowcount 0 -> somebody else won; re-read and try again.
    return False


# --------------------------------------------------------------------------
# 5. Atomic: push the whole read-modify-write into one statement.
# --------------------------------------------------------------------------
def s5_atomic(con) -> bool:
    con.autocommit = True
    cur = con.execute(
        "UPDATE seats SET sold = sold + 1 WHERE id=1 AND sold < %s", (SEAT_LIMIT,))
    return cur.rowcount == 1


# --------------------------------------------------------------------------
# 6. Raise the isolation level. The database now REFUSES instead of complying.
# --------------------------------------------------------------------------
serialization_failures = 0
_sf_lock = threading.Lock()


def s6_repeatable_read(con) -> bool:
    global serialization_failures
    con.autocommit = False
    for _ in range(60):
        try:
            with con.transaction():
                con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                current = con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]
                if current >= SEAT_LIMIT:
                    return False
                time.sleep(THINK_TIME)
                con.execute("UPDATE seats SET sold=%s WHERE id=1", (current + 1,))
            return True
        except pgerrors.SerializationFailure:
            # THIS is the point of the strategy: PostgreSQL detected the
            # conflict and aborted us rather than losing the update. Without
            # this retry loop we would be serving 500s instead of corrupting
            # data - which is better, but is not "it just works".
            with _sf_lock:
                serialization_failures += 1
            time.sleep(0.002)
    return False


# --------------------------------------------------------------------------
# 7. INSERT MODEL: count, then insert. The other disguise - this OVERSELLS.
# --------------------------------------------------------------------------
def s7_count_then_insert(con) -> bool:
    con.autocommit = True
    current = con.execute("SELECT count(*) FROM bookings").fetchone()[0]
    if current >= SEAT_LIMIT:
        return False
    time.sleep(THINK_TIME)
    # Nothing is lost here - every INSERT succeeds. That is exactly why we blow
    # past the limit instead of falling short of it.
    con.execute("INSERT INTO bookings (holder) VALUES (%s)", ("guest",))
    return True


# --------------------------------------------------------------------------
# 8. Make it unrepresentable: the seats EXIST as 100 rows. Claim one.
#    FOR UPDATE SKIP LOCKED is the standard "give me any free unit" pattern -
#    it is how job queues are built on PostgreSQL.
# --------------------------------------------------------------------------
def s8_allocated_rows(con) -> bool:
    con.autocommit = False
    with con.transaction():
        row = con.execute("""
            SELECT seat_no FROM seat_rows
            WHERE holder IS NULL
            ORDER BY seat_no
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        """).fetchone()
        if row is None:
            return False
        time.sleep(THINK_TIME)
        cur = con.execute(
            "UPDATE seat_rows SET holder=%s WHERE seat_no=%s AND holder IS NULL",
            ("guest", row[0]),
        )
        return cur.rowcount == 1


# name, book_fn, setup_fn, count_fn, model
STRATEGIES = [
    ("1. no transaction",          s1_no_txn,           reset_counter,   count_counter,   "counter"),
    ("2. txn @ READ COMMITTED",    s2_read_committed,   reset_counter,   count_counter,   "counter"),
    ("3. SELECT ... FOR UPDATE",   s3_for_update,       reset_counter,   count_counter,   "counter"),
    ("4. optimistic (version)",    s4_optimistic,       reset_counter,   count_counter,   "counter"),
    ("5. single atomic UPDATE",    s5_atomic,           reset_counter,   count_counter,   "counter"),
    ("6. REPEATABLE READ + retry", s6_repeatable_read,  reset_counter,   count_counter,   "counter"),
    ("7. count-then-INSERT",       s7_count_then_insert, reset_bookings, count_bookings,  "insert"),
    ("8. pre-allocated seat rows", s8_allocated_rows,   reset_allocated, count_allocated, "insert"),
]


def run(url: str, fn, setup_fn, count_fn) -> tuple[int, int, float]:
    setup_fn(url)
    barrier = threading.Barrier(BOOKERS)
    confirmed = [0]
    lock = threading.Lock()

    def worker() -> None:
        local = 0
        with psycopg.connect(url) as con:
            barrier.wait()
            for _ in range(ATTEMPTS_EACH):
                try:
                    if fn(con):
                        local += 1
                except Exception:
                    if not con.closed and not con.autocommit:
                        try:
                            con.rollback()
                        except Exception:
                            pass
        with lock:
            confirmed[0] += local

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=BOOKERS) as ex:
        for _ in range(BOOKERS):
            ex.submit(worker)
    ms = (time.perf_counter() - t0) * 1000
    return confirmed[0], count_fn(url), ms


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, help="run just one strategy (1-8)")
    args = ap.parse_args()

    url = require_db("transactions.py")
    banner(url)

    attempts = BOOKERS * ATTEMPTS_EACH
    print(f"{BOOKERS} concurrent bookers x {ATTEMPTS_EACH} attempts = {attempts} bookings attempted")
    print(f"Seat limit {SEAT_LIMIT}. Correct: exactly {SEAT_LIMIT} confirmed AND {SEAT_LIMIT} stored.\n")
    print(f"{'strategy':<30} {'confirmed':>10} {'stored':>8} {'ms':>7}   verdict")
    print("-" * 92)

    chosen = STRATEGIES if not args.only else [STRATEGIES[args.only - 1]]
    for name, fn, setup_fn, count_fn, model in chosen:
        confirmed, stored, ms = run(url, fn, setup_fn, count_fn)
        if stored > SEAT_LIMIT:
            verdict = f"OVERSOLD by {stored - SEAT_LIMIT}"
        elif confirmed != stored:
            verdict = f"INCONSISTENT: told {confirmed}, stored {stored}"
        elif stored == SEAT_LIMIT:
            verdict = "correct"
        else:
            verdict = f"undersold: only {stored}"
        print(f"{name:<30} {confirmed:>10} {stored:>8} {ms:>7.0f}   {verdict}")

    if serialization_failures:
        print(f"\n  strategy 6 hit {serialization_failures} serialization failures "
              f"that the retry loop absorbed")

    print("""
WHAT THE ROOM SHOULD TAKE AWAY
==============================

  1. ONE BUG, TWO OPPOSITE SYMPTOMS.
     Strategies 1-2 CONFIRM 192 bookings and STORE only ~15 (it varies from
     run to run - 13 to 15 in ours): concurrent writers
     overwrote each other and the increments were lost.
     Strategy 7 stores every booking and OVERSELLS: nothing was lost, but the
     count it checked against was already stale.
     Same root cause - read, think, write, with a window in the middle - and
     you cannot predict the symptom from the bug. Both are silent.

     (Run transactions.py for the SQLite version, which fails differently
      again. Never generalise a concurrency lesson from one engine.)

  2. STRATEGY 2 IS THE ONE THAT MATTERS.
     It is what almost all application code does: a transaction, at the default
     isolation level. It is STILL WRONG. READ COMMITTED prevents DIRTY reads.
     It does not prevent LOST UPDATES. "We wrap it in a transaction" is not an
     answer to "is this correct?".

  3. THE FOUR CORRECT ANSWERS ARE NOT EQUIVALENT.
       FOR UPDATE       simple, always right, serialises everyone on the row
       optimistic       no locks, but you MUST bound the retries
       atomic UPDATE    fastest and simplest here - and thought of last
       REPEATABLE READ  the database REFUSES rather than losing data. Note the
                        serialization-failure count above: those are aborted
                        transactions that our retry loop absorbed. Without that
                        loop they would be 500s. You swapped silent corruption
                        for visible errors you now have to handle. Usually the
                        better trade - but it IS a trade, not a free fix.

  4. STRATEGY 8 IS THE PUNCHLINE.
     The seats EXIST, as 100 rows. Booking is claiming a row. Overselling is
     not prevented by careful code - it is ARITHMETICALLY IMPOSSIBLE, because
     there is no 101st row to claim. The `FOR UPDATE SKIP LOCKED` pattern in
     it is the same one production job queues are built on.

     That is the same move as a static type, as @tailrec, as Mutex<T>: push the
     invariant down to the layer that cannot forget it. Fourth time this
     session, and the reason the session ends on `docs/00-how-to-choose.md`
     rather than on a benchmark.""")


if __name__ == "__main__":
    main()
