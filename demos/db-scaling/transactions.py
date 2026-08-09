#!/usr/bin/env python3
"""The same race condition, one layer down: in the database.

    python3 demos/db-scaling/transactions.py

In the concurrency block we oversold seats with an in-memory counter. Moving
the counter into a database does NOT fix it. Juniors assume it does — "the
database is transactional" — and that assumption is the source of a large
fraction of real-world data corruption.

A transaction gives you atomicity (all or nothing) and durability. It does not
automatically give you the isolation you imagined. Under READ COMMITTED, which
is the default in PostgreSQL, Oracle and SQL Server, this sequence is entirely
legal and entirely wrong:

    T1: SELECT sold FROM seats   -> 99
    T2: SELECT sold FROM seats   -> 99
    T1: UPDATE seats SET sold=100
    T2: UPDATE seats SET sold=100     <- T1's booking has vanished

That is the LOST UPDATE anomaly, and it is invisible in every log you have.

We use SQLite because it is in the Python standard library, so the demo runs
anywhere. The anomaly and all four fixes are the same shape in PostgreSQL and
MySQL; the SQL dialect notes are inline.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time

BOOKERS = 16
ATTEMPTS_EACH = 25
SEAT_LIMIT = 100

DB_PATH = os.path.join(tempfile.gettempdir(), "seats_demo.sqlite")


def fresh_db() -> None:
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")          # allow concurrent readers
    con.execute("CREATE TABLE seats (id INTEGER PRIMARY KEY, sold INTEGER, version INTEGER)")
    con.execute("INSERT INTO seats (id, sold, version) VALUES (1, 0, 0)")
    con.commit()
    con.close()


def connect() -> sqlite3.Connection:
    # timeout: how long to wait for a write lock before raising "database is
    # locked". isolation_level=None means WE control transactions explicitly,
    # which is what you want when the transaction boundary is the lesson.
    con = sqlite3.connect(DB_PATH, timeout=30.0, isolation_level=None)
    con.execute("PRAGMA busy_timeout=30000")
    return con


def sold() -> int:
    con = connect()
    try:
        return con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Strategy 1 - read, think, write. No transaction. The bug.
# ---------------------------------------------------------------------------
def book_naive(con: sqlite3.Connection) -> bool:
    row = con.execute("SELECT sold FROM seats WHERE id=1").fetchone()
    current = row[0]
    if current >= SEAT_LIMIT:
        return False
    # In real code this gap is a payment call, a validation, an audit write.
    # Here it is a tiny sleep that stands in for all of them.
    time.sleep(0.001)
    con.execute("UPDATE seats SET sold=? WHERE id=1", (current + 1,))
    return True


# ---------------------------------------------------------------------------
# Strategy 2 - wrap it in a transaction, change nothing else.
# ---------------------------------------------------------------------------
def book_deferred_txn(con: sqlite3.Connection) -> bool:
    # BEGIN (DEFERRED) takes no lock until the first write, so two readers still
    # both see the old value. This is the closest analogue to PostgreSQL's
    # default READ COMMITTED, and it demonstrates the key point: a transaction
    # alone does NOT prevent a lost update.
    con.execute("BEGIN")
    try:
        current = con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]
        if current >= SEAT_LIMIT:
            con.execute("COMMIT")
            return False
        time.sleep(0.001)
        con.execute("UPDATE seats SET sold=? WHERE id=1", (current + 1,))
        con.execute("COMMIT")
        return True
    except sqlite3.OperationalError:
        con.execute("ROLLBACK")
        return False


# ---------------------------------------------------------------------------
# Strategy 3 - pessimistic lock. Take the write lock UP FRONT.
# ---------------------------------------------------------------------------
def book_pessimistic(con: sqlite3.Connection) -> bool:
    # SQLite: BEGIN IMMEDIATE acquires the write lock at BEGIN.
    # PostgreSQL / MySQL: SELECT ... FOR UPDATE on the row.
    con.execute("BEGIN IMMEDIATE")
    try:
        current = con.execute("SELECT sold FROM seats WHERE id=1").fetchone()[0]
        if current >= SEAT_LIMIT:
            con.execute("COMMIT")
            return False
        time.sleep(0.001)
        con.execute("UPDATE seats SET sold=? WHERE id=1", (current + 1,))
        con.execute("COMMIT")
        return True
    except sqlite3.OperationalError:
        con.execute("ROLLBACK")
        return False


# ---------------------------------------------------------------------------
# Strategy 4 - optimistic lock. Don't lock; detect and retry.
# ---------------------------------------------------------------------------
def book_optimistic(con: sqlite3.Connection) -> bool:
    for _ in range(50):                       # bounded retries
        row = con.execute("SELECT sold, version FROM seats WHERE id=1").fetchone()
        current, version = row
        if current >= SEAT_LIMIT:
            return False
        time.sleep(0.001)
        try:
            cur = con.execute(
                "UPDATE seats SET sold=?, version=? WHERE id=1 AND version=?",
                (current + 1, version + 1, version),
            )
            if cur.rowcount == 1:             # nobody changed it under us
                return True
            # rowcount 0 => someone else won the race; re-read and try again.
        except sqlite3.OperationalError:
            time.sleep(0.002)
    return False


# ---------------------------------------------------------------------------
# Strategy 5 - don't read at all. Let the database do the whole thing.
# ---------------------------------------------------------------------------
def book_atomic(con: sqlite3.Connection) -> bool:
    # One statement. The check and the increment are the same operation, so
    # there is no window to interleave. This is almost always the right answer,
    # and it is the one juniors reach for last.
    for _ in range(50):
        try:
            cur = con.execute(
                "UPDATE seats SET sold = sold + 1 WHERE id=1 AND sold < ?", (SEAT_LIMIT,)
            )
            return cur.rowcount == 1
        except sqlite3.OperationalError:
            time.sleep(0.002)
    return False


STRATEGIES = [
    ("1. read-then-write, no txn", book_naive, "the bug"),
    ("2. BEGIN (deferred) txn", book_deferred_txn, "a transaction is not enough"),
    ("3. BEGIN IMMEDIATE / FOR UPDATE", book_pessimistic, "pessimistic lock"),
    ("4. optimistic (version column)", book_optimistic, "detect + retry"),
    ("5. single atomic UPDATE", book_atomic, "no read at all"),
]


def run(fn) -> tuple[int, int, float]:
    fresh_db()
    barrier = threading.Barrier(BOOKERS)
    granted = [0]
    lock = threading.Lock()

    def worker() -> None:
        con = connect()
        local = 0
        try:
            barrier.wait()
            for _ in range(ATTEMPTS_EACH):
                try:
                    if fn(con):
                        local += 1
                except sqlite3.OperationalError:
                    pass
        finally:
            con.close()
        with lock:
            granted[0] += local

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(BOOKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ms = (time.perf_counter() - t0) * 1000
    return granted[0], sold(), ms


def main() -> None:
    print(f"{BOOKERS} concurrent bookers x {ATTEMPTS_EACH} attempts, seat limit {SEAT_LIMIT}")
    print("Correct behaviour: exactly 100 confirmations AND sold == 100.\n")
    print(f"{'strategy':<34} {'confirmed':>10} {'sold in DB':>12} {'ms':>8}   verdict")
    print("-" * 88)

    for name, fn, _note in STRATEGIES:
        confirmed, in_db, ms = run(fn)
        ok = confirmed == in_db == SEAT_LIMIT
        if confirmed != in_db:
            verdict = f"BROKEN: told {confirmed} users yes, stored {in_db}"
        elif in_db > SEAT_LIMIT:
            verdict = f"BROKEN: oversold by {in_db - SEAT_LIMIT}"
        elif ok:
            verdict = "correct"
        else:
            verdict = f"BROKEN: only sold {in_db} of {SEAT_LIMIT}"
        print(f"{name:<34} {confirmed:>10} {in_db:>12} {ms:>8.0f}   {verdict}")

    print("""
HOW TO READ THIS
================

  Strategy 1 is the catastrophe: it confirms far more bookings than it stores.
  Every one of those extra confirmations is a customer holding a receipt for a
  seat that does not exist.

  Strategy 2 shows that a transaction ALONE does not fix it - but be precise
  about how it fails, because it is engine-specific:
    * In SQLite (here) a deferred transaction that tries to upgrade to a write
      lock hits conflicts, so bookings are silently REJECTED and we UNDERSELL.
    * In PostgreSQL under READ COMMITTED you get the classic LOST UPDATE
      instead: both transactions read 99, both write 100, and you OVERSELL.
  Different anomaly, same root cause, and both are wrong. "We use transactions"
  is not an answer to "is this correct?".

  Watch the two columns disagree. "confirmed" is how many users got a success
  response. "sold in DB" is what was actually persisted. When those differ, you
  have told N customers they have a seat and kept fewer. No exception was
  raised. No log line is wrong. Your monitoring is green.

THE FOUR FIXES, AND WHEN TO USE EACH
====================================

  PESSIMISTIC (SELECT ... FOR UPDATE / BEGIN IMMEDIATE)
    Take the lock before you look. Simple and always correct.
    Cost: serialises everyone on that row, and holds a lock for the whole
    transaction - including any slow work you foolishly do inside it.
    Use when: contention is high and conflicts are likely.

  OPTIMISTIC (version column, UPDATE ... WHERE version = ?)
    Don't lock. Detect the conflict at write time via rowcount, then retry.
    Cost: wasted work on conflict, and you MUST bound the retries.
    Use when: conflicts are rare. This is what JPA/Hibernate @Version does.

  ATOMIC SINGLE STATEMENT (UPDATE ... SET x = x + 1 WHERE ...)
    Push the whole read-modify-write into one statement so there is no window.
    Cost: none, when your logic fits in SQL.
    Use when: you can. This is usually the right answer and usually the last
    one people think of.

  DATABASE CONSTRAINT (CHECK, UNIQUE, exclusion constraint)
    Make the invalid state unrepresentable in the schema. The database enforces
    it no matter which service, script or intern writes to the table.
    THIS IS THE SAME IDEA AS STATIC TYPING, one layer down: move the guarantee
    to where it cannot be forgotten. Note the pattern - it is the third time
    this session, after the type system and the borrow checker.

ISOLATION LEVELS, THE SHORT VERSION
===================================

  READ UNCOMMITTED   dirty reads.  Never use.
  READ COMMITTED     default in PostgreSQL/Oracle/SQL Server.
                     Prevents dirty reads. Does NOT prevent lost updates.
  REPEATABLE READ    default in MySQL/InnoDB. In PostgreSQL this DOES catch
                     the lost update - by aborting your transaction with a
                     serialisation failure that you must be ready to retry.
  SERIALIZABLE       behaves as if transactions ran one at a time.
                     Correct, slowest, and still needs retry logic.

  The trap: raising the isolation level does not make your code correct, it
  makes the database TELL you when it is not - by throwing. If you have no
  retry logic, you have swapped silent corruption for visible 500s. That may
  well be the better trade, but it is a trade.""")


if __name__ == "__main__":
    main()
