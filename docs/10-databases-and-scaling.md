# Block 5b — Databases: pools, connections, transactions

**Run:** `make demo-db` (uses a real PostgreSQL if one is reachable)
**Start one:** `make db-up` — a resource-limited container: **1 CPU, 512 MB,
`max_connections=50`**
**Live on Cloud SQL:** [`demos/db-scaling/GCP-RUNBOOK.md`](../demos/db-scaling/GCP-RUNBOOK.md)

> **Two versions of every demo.** `make demo-db` prefers a real PostgreSQL and
> falls back to a simulation, saying so loudly. Use the real one — the
> container is deliberately small so the walls arrive while the room is
> watching, and "we measured it" beats "we modelled it" every time.

Almost every service in the room's future is **I/O-bound on a database**. That
makes this block the one where the session's earlier conclusions actually get
applied — and where the language choice matters least and the *architecture*
matters most.

---

## Part 1 — A connection is not a cheap object

Juniors picture a connection as a socket. It is much more than that:

| | What one connection actually costs |
| --- | --- |
| **PostgreSQL** | a whole **OS process** (fork), ~5–10 MB RSS on the server, plus per-backend caches |
| **MySQL** | a thread, ~256 KB–1 MB |
| **TLS** | a handshake: 1–2 extra round trips at setup |
| **Auth** | round trips, sometimes an external IdP call |

Typical `max_connections` on a small managed instance is **~100**. Not 10,000.
Our training container ships with **50**, which is not unrealistic: a Cloud SQL
`db-f1-micro` defaults to about 25.

### Measured: walking into the wall

`python3 demos/db-scaling/exhaust_connections.py` opens connections one at a
time against `max_connections=50`:

```
   50 connections open

FAILED on connection #51 after 0.4s
  FATAL:  sorry, too many clients already

Could not open a connection to inspect the server:
  FATAL:  sorry, too many clients already
  ^ your metrics agent, your health check and your on-call engineer's psql
    are all locked out at exactly the moment you need them.
```

That second failure is the part worth pausing on. The database did not get
slower — it stopped accepting anyone, **including the people trying to
diagnose it**. And it fails in the worst possible order: connections are
first-come-first-served, so the pods that get starved are the **new** ones your
autoscaler just started. Scaling up makes it worse. That is the incident.

That single fact drives the whole block:

> Ten pods × a pool of 20 = 200 connections against a limit of 100.
> The service does not degrade gracefully — it fails to connect, and health
> checks start failing on pods that were perfectly healthy.

---

## Part 2 — Why a bigger pool is usually slower

The instinct when a service is slow is "increase the pool". It is almost always
wrong. A pool is a **queue in front of a fixed resource**, and queueing theory
does not care whether the resource is a disk or a CPU.

### Measured on a real 1-CPU PostgreSQL

`python3 demos/db-scaling/real_pool.py` — 40 concurrent users, CPU-bound
queries, against the 1-CPU container:

| pool size | throughput | p50 | p99 |
| ---: | ---: | ---: | ---: |
| **1** | 68 q/s | 588 ms | **620 ms** |
| 2 | 72 q/s | 542 ms | 635 ms |
| 4 | 75 q/s | 495 ms | 661 ms |
| 8 | 70 q/s | 561 ms | 628 ms |
| 16 | 77 q/s | 481 ms | 693 ms |
| 32 | 77 q/s | 424 ms | **947 ms** |

**Throughput is flat — a 1.14× spread across a 32× range of pool sizes. A pool
of ONE reaches 88% of what a pool of 32 achieves.** Meanwhile p99 degrades by
53%.

That is the whole lesson in one table: past the point where the database is
saturated, **extra connections buy variance, not capacity**. The HikariCP
formula `(cores × 2) + spindles` predicts ~2 for a 1-CPU database, and the
measurement agrees.

Try it live: `docker update --cpus=2 lang-training-db` and re-run. The plateau
rises. Pool size is a function of the **database's** capacity, never of your
application's traffic.

### The same shape, simulated

`pool_sizing.py` needs no infrastructure (a simulated database with parallelism
8, 200 concurrent users) and produces the same shape more dramatically:

| pool size | throughput | p50 | p99 | in-flight |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 475 q/s | 4.2 ms | 1965 ms | 2 |
| 4 | 953 q/s | 4.2 ms | 979 ms | 4 |
| **8** | **1883 q/s** | **4.2 ms** | 474 ms | 8 |
| 16 | 1815 q/s | 8.8 ms | 482 ms | 16 |
| 32 | 1595 q/s | 20.0 ms | 515 ms | 32 |
| 64 | 1298 q/s | 50.1 ms | 540 ms | 64 |
| 128 | 1009 q/s | 140.9 ms | 735 ms | 128 |
| 200 | 723 q/s | 289.7 ms | 292 ms | 200 |

> **Pool size 200 buys 0.38× the throughput for 70× the p50 latency.**

Throughput peaks at the database's *real* parallelism and then **declines**.
Past that point extra connections do not create capacity — they create a bigger
crowd fighting over the same capacity.

**The queue does not disappear when you enlarge the pool. It moves** — out of
your application, where it is cheap, visible, fair and sheddable, into the
database, where it is expensive, invisible and unfair.

A small pool is a **bulkhead**.

### The formula

```
connections = (core_count * 2) + effective_spindles
```

For an 8-core database server that is about **17**. Not 200. This is the
HikariCP/PostgreSQL guidance and it surprises everyone. If your pool is bigger
than a couple of dozen, you are probably hiding a problem.

> **Honesty note for the room:** `pool_sizing.py` is a *simulation* — service
> time, parallelism and the super-linear overhead coefficient are constants at
> the top of the file. What is robust is the **shape**: a fixed-capacity
> resource behind a queue always has a knee. Verify against your own database
> — the GCP runbook shows how with `pgbench`.

### What to do instead when the pool is saturated

1. Make the queries faster — indexes, N+1, fewer round trips
2. **Hold connections for less time** — never across an HTTP call, never for a
   whole request when you need it twice
3. Cache, so the query never happens
4. Read replicas for reads
5. *Only then*: a bigger database

---

## Part 3 — The traps that connect to earlier blocks

### Virtual threads meet the connection pool

This is the payoff from Block 4b, and it is the most important slide here:

> Virtual threads let one JVM run **10,000 concurrent requests**.
> Your database still accepts **~100 connections**.

Virtual threads did not add database capacity. They made it trivially easy to
**exhaust** it — where before, your 200-thread pool was an accidental
rate limiter. Removing that accident without adding a deliberate one is how
teams take down their database the week they adopt virtual threads.

The fix is unchanged: a small pool, and **back-pressure** — a bounded queue
with a timeout, so you fail fast and shed load instead of collapsing.

### Serverless and pools do not mix

Each Lambda/Cloud Run instance has **its own pool**. Scale to 500 instances
with a pool of 10 and you have asked for 5,000 connections.

Fixes: a proxy that multiplexes (PgBouncer, RDS Proxy, Cloud SQL Auth Proxy),
pool size **1–2** per instance, or a database designed for it (Neon,
PlanetScale, DynamoDB).

### "Idle in transaction" — the single most common DB incident

Someone opens a transaction, then makes an HTTP call inside it. Now a
connection **and a row lock** are held for the duration of a network round
trip, per request.

```sql
SELECT pid, state, now() - state_change AS idle_for, query
FROM pg_stat_activity WHERE state = 'idle in transaction'
ORDER BY idle_for DESC;
```

**Never do I/O inside a transaction.** This is the database version of "never
block inside a `parallelStream`".

---

## Part 4 — The same race condition, one layer down

Moving the counter into a database does **not** fix it. Juniors assume it does
— "the database is transactional" — and that assumption causes a large share of
real-world data corruption.

A transaction gives you **atomicity** and **durability**. It does not
automatically give you the **isolation** you imagined. Under READ COMMITTED —
the default in PostgreSQL, Oracle and SQL Server — this is entirely legal:

```
T1: SELECT sold FROM seats  -> 99
T2: SELECT sold FROM seats  -> 99
T1: UPDATE seats SET sold=100
T2: UPDATE seats SET sold=100    <- T1's booking has vanished
```

That is the **lost update** anomaly, and it is invisible in every log you have.

### Measured on real PostgreSQL — 16 bookers × 12 attempts, limit 100

`python3 demos/db-scaling/real_transactions.py`:

| strategy | confirmed | stored | ms | verdict |
| --- | ---: | ---: | ---: | --- |
| 1. no transaction | **192** | **13** | 187 | told 192 users yes, stored 13 |
| 2. txn @ READ COMMITTED | **192** | **13** | 214 | *still* broken |
| 3. `SELECT … FOR UPDATE` | 100 | 100 | 681 | correct |
| 4. optimistic (version) | 100 | 100 | 706 | correct |
| 5. single atomic `UPDATE` | 100 | 100 | **165** | correct, fastest |
| 6. REPEATABLE READ + retry | 100 | 100 | 1033 | correct (**787** serialization failures absorbed) |
| 7. count-then-`INSERT` | 113 | 113 | 154 | **OVERSOLD by 13** |
| 8. pre-allocated seat rows | 100 | 100 | 216 | correct |

### One bug, two opposite symptoms

This is the subtlety worth the most time, because juniors generalise from
whichever failure they saw first:

- **Counter model** (`UPDATE seats SET sold = <the value I read>`) — concurrent
  writers overwrite each other. Increments are **lost**, so you confirm 192
  bookings and store 13. You **undersell** while telling customers yes.
- **Insert model** (`SELECT count(*)` then `INSERT`) — every insert succeeds, so
  nothing is lost, but the count was already stale. You **oversell**.

Same root cause — read, think, write, with a window in the middle — and you
**cannot predict the symptom from the bug**. Both are silent.

Run `transactions.py` (SQLite) alongside: it fails differently again, silently
*rejecting* bookings. **Never generalise a concurrency lesson from one engine.**

**Strategy 2 is the one that matters.** It is what almost all application code
does: a transaction, at the default isolation level. It is still wrong. READ
COMMITTED prevents *dirty* reads; it does not prevent *lost updates*.
*"We wrap it in a transaction"* is not an answer to *"is this correct?"*.

**Strategy 6 has a hidden cost.** Those 787 serialization failures were aborted
transactions that our retry loop absorbed. Without the loop they are 500s. You
swapped silent corruption for visible errors you now have to handle — usually
the better trade, but a trade.

**Strategy 8 is the punchline.** The seats *exist*, as 100 rows. Booking is
claiming a row with `FOR UPDATE SKIP LOCKED` (the same pattern production job
queues use). Overselling is not prevented by careful code — it is
**arithmetically impossible**, because there is no 101st row.

### The four fixes and when to use each

| Fix | How | Cost | Use when |
| --- | --- | --- | --- |
| **Pessimistic** | `SELECT … FOR UPDATE` | serialises everyone on the row; holds a lock for the whole transaction | conflicts are likely |
| **Optimistic** | `UPDATE … WHERE version = ?`, check `rowcount`, retry | wasted work on conflict; **must** bound retries | conflicts are rare (this is JPA `@Version`) |
| **Atomic statement** | `UPDATE … SET sold = sold + 1 WHERE sold < 100` | none, when the logic fits in SQL | almost always — and it is the last one people think of |
| **Constraint** | `CHECK (sold <= 100)`, `UNIQUE`, exclusion constraints | none | always, as a backstop |

> The constraint is the same idea as static typing, one layer down: **move the
> guarantee to where it cannot be forgotten.** It holds no matter which
> service, script or intern writes to that table.
>
> That is the fourth time this session — the type system, `@tailrec`, the
> borrow checker, and now the schema.

### Isolation levels, the short version

| Level | Prevents | Note |
| --- | --- | --- |
| READ UNCOMMITTED | nothing useful | never use |
| **READ COMMITTED** | dirty reads | **default** in PostgreSQL/Oracle/SQL Server. Does **not** prevent lost updates |
| REPEATABLE READ | non-repeatable reads | MySQL default. In PostgreSQL this *catches* the lost update — by **aborting** your transaction |
| SERIALIZABLE | everything | slowest, and still needs retry logic |

**The trap:** raising the isolation level does not make your code correct — it
makes the database **tell you** when it is not, by throwing. With no retry
logic you have swapped silent corruption for visible 500s. Often the better
trade, but a trade.

---

## Part 5 — Scaling, in the order you should try it

1. **Don't query** — cache, batch, denormalise the hot read
2. **Query better** — indexes, fix N+1, `EXPLAIN ANALYZE`, select fewer columns
3. **Hold connections for less time** — shrink transaction scope
4. **Right-size the pool** — smaller, not bigger
5. **Read replicas** — most workloads are read-heavy
6. **Connection proxy** — PgBouncer / RDS Proxy / Cloud SQL Auth Proxy
7. **Vertical scale** — genuinely fine, and cheaper than an engineer-month
8. **Partition / shard** — last, because it is mostly irreversible

Juniors reach for 8 first. The wins are almost always in 1–4.

### The N+1 that eats everything

```java
List<Order> orders = repo.findAll();            // 1 query
for (Order o : orders) o.getCustomer().getName();  // N more queries
```

101 round trips instead of 1. At 2 ms each that is 200 ms of pure latency, and
it holds a connection the whole time. No language choice, no pool size and no
GC tuning fixes this — which is the honest closing note for the whole session:
**the biggest performance wins are almost never the language.**

---

## Live on GCP

[`demos/db-scaling/GCP-RUNBOOK.md`](../demos/db-scaling/GCP-RUNBOOK.md) has a
full runbook: create a small Cloud SQL instance, blow past `max_connections`
live in ten seconds, reproduce the pool curve with `pgbench`, and walk the
lost update through two side-by-side `psql` sessions.

If you only do one thing live, do **the two-session lost update**. Watching a
committed row lose a booking in front of the room is the thing they will
remember.

---

## Discussion prompts

1. Your API p99 is 2 s. Pool metrics show connections at 100% and a growing
   wait queue. What are the three things you check before enlarging the pool?
   *(Slow query log; transaction scope / idle-in-transaction; N+1.)*
2. You move to virtual threads and the database starts refusing connections.
   What happened? *(The thread pool was your accidental rate limiter. You need
   a deliberate one.)*
3. Why is `UPDATE … SET sold = sold + 1 WHERE sold < 100` better than
   `SELECT` + `UPDATE` in a transaction? *(No window to interleave, no lock
   held across application logic, one round trip instead of two.)*
4. When is optimistic locking the wrong choice? *(High contention — you burn
   CPU on retries that keep losing. Use pessimistic there.)*
5. Your service runs on Cloud Run and scales to 300 instances. What is the
   first thing you check about the database? *(Total connections =
   instances × pool size. You need a proxy or a pool of 1–2.)*
