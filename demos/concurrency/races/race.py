#!/usr/bin/env python3
"""Python: does the GIL make your code thread-safe?

    python3 demos/concurrency/races/race.py

The common junior belief is "Python has a GIL, so threads are safe." That is
half true, in the most dangerous possible way:

  * The GIL protects the INTERPRETER's data structures. You will never corrupt
    a dict's internals or segfault the runtime by racing on it.
  * The GIL does NOT protect YOUR invariants. `x += 1` is load, add, store —
    the interpreter may switch threads between those bytecodes.

This script runs two experiments, and the contrast between them is the lesson.

  EXPERIMENT 1 - a tight CPU-bound counter loop.
  On CPython this usually comes out CORRECT. Not because it is safe, but
  because the GIL effectively serialises threads that never block: a thread
  holding the GIL tends to run its whole loop before another gets scheduled.
  A race that does not reproduce is still a race.

  EXPERIMENT 2 - check-then-act with I/O in the middle.
  This breaks every time. And it is the realistic one: every Python service is
  I/O-bound, and the GIL is RELEASED on every socket read, database call and
  file access. The moment your code waits for anything, other threads run —
  right between your check and your act.

The takeaway: Python's races do not hide in tight loops. They hide exactly
where all real Python code lives.
"""
from __future__ import annotations

import threading
import time

# --- Experiment 1: the classic counter ------------------------------------
THREADS = 8
INCREMENTS = 100_000


class Counter:
    def __init__(self) -> None:
        self.value = 0


def bump(counter: Counter, n: int) -> None:
    for _ in range(n):
        counter.value += 1              # load, add, store — not atomic


def bump_locked(counter: Counter, n: int, lock: threading.Lock) -> None:
    for _ in range(n):
        with lock:
            counter.value += 1


def experiment_one() -> None:
    expected = THREADS * INCREMENTS

    counter = Counter()
    threads = [threading.Thread(target=bump, args=(counter, INCREMENTS))
               for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    racy = counter.value

    locked_counter = Counter()
    lock = threading.Lock()
    threads = [threading.Thread(target=bump_locked, args=(locked_counter, INCREMENTS, lock))
               for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("  EXPERIMENT 1 - tight CPU loop, no I/O")
    print(f"    expected        {expected}")
    print(f"    racy `+=`       {racy}   (lost {expected - racy})")
    print(f"    with Lock       {locked_counter.value}")
    if racy == expected:
        print("    -> Came out CORRECT. That is NOT safety, it is luck plus the GIL")
        print("       serialising threads that never block. Do not conclude anything.")
    else:
        print("    -> Lost updates. The GIL never protected your invariant.")


# --- Experiment 2: check-then-act around I/O -------------------------------
SEAT_LIMIT = 100
BOOKERS = 16
ATTEMPTS_EACH = 20


class Seats:
    def __init__(self) -> None:
        self.sold = 0


def book(seats: Seats, barrier: threading.Barrier, lock: threading.Lock | None) -> None:
    barrier.wait()                       # start everyone at once
    for _ in range(ATTEMPTS_EACH):
        if lock:
            with lock:
                _book_once(seats)
        else:
            _book_once(seats)


def _book_once(seats: Seats) -> None:
    if seats.sold < SEAT_LIMIT:          # CHECK
        pending = seats.sold
        # This sleep is not a cheat. It stands in for the work that ALWAYS sits
        # between a check and an act in production code: a database round trip,
        # a payment API call, a permissions lookup. All of them release the GIL.
        time.sleep(0.0005)
        seats.sold = pending + 1         # ACT


def run_booking(lock: threading.Lock | None) -> int:
    seats = Seats()
    barrier = threading.Barrier(BOOKERS)
    threads = [threading.Thread(target=book, args=(seats, barrier, lock))
               for _ in range(BOOKERS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return seats.sold


def experiment_two() -> None:
    attempts = BOOKERS * ATTEMPTS_EACH
    racy = run_booking(None)
    safe = run_booking(threading.Lock())

    print()
    print("  EXPERIMENT 2 - check-then-act with I/O between check and act")
    print(f"    seat limit      {SEAT_LIMIT}")
    print(f"    booking attempts {attempts}")
    print(f"    racy   -> sold  {racy}")
    print(f"    locked -> sold  {safe}   (correct: fills to the limit)")
    if racy != safe:
        print(f"    -> {abs(safe - racy)} bookings vanished into thin air. Sixteen threads")
        print("       read the same seat count, then all wrote back their own +1.")
        print("       Nothing crashed. The database is simply wrong now.")


def main() -> None:
    print("Python — is the GIL enough?\n")
    experiment_one()
    experiment_two()
    print()
    print("  The GIL is an implementation detail of the interpreter, not a")
    print("  concurrency model for your program. If two threads touch the same")
    print("  state, you need a Lock — in every language on this list.")


if __name__ == "__main__":
    main()
