# Live on GCP: showing this against a real Cloud SQL instance

> **Try the local container first.** `make db-up` starts a deliberately small
> PostgreSQL (1 CPU, 512 MB, `max_connections=50`) and `make demo-db` runs
> every demo below against it — the connection wall, the pool plateau and both
> transaction anomalies — with no cloud account, no cost and no IP allowlisting.
> That gets you roughly 90% of the value of this runbook in about 30 seconds.
>
> Do the **GCP** version when you want the last 10%: a managed instance, a real
> network, `pg_stat_activity` on a server you did not configure yourself, and
> the credibility of "this is the same product we run in production".

The local demos prove the *shape* of the problem with no infrastructure. This
runbook reproduces the same results on real Cloud SQL for PostgreSQL.

> **Do this on a scratch project and a throwaway instance.** You are going to
> deliberately saturate a database and deliberately corrupt a row. Never point
> this at anything shared, and never at production. Budget ~30 minutes to set
> up and about €1–3 of instance time if you delete it afterwards.

---

## 0. Decide before the session

| Question | Recommendation |
| --- | --- |
| Which project? | A personal sandbox, or a training project with its own budget alert |
| Public IP or private? | Public IP + authorised network = your laptop's IP. Simplest for a demo |
| Instance size | `db-custom-2-7680` (2 vCPU). **Small is better** — the knee arrives sooner and the demo is more dramatic |
| Delete after? | Yes. Put it in the calendar invite |

Small instance is not a cost-saving compromise here, it is a pedagogical
choice: on 2 vCPUs the connection-pool knee shows up at ~5 connections and the
whole table fits on one screen.

---

## 1. Create the instance

```bash
export PROJECT=your-sandbox-project
export REGION=europe-west1
export INSTANCE=lang-training-demo

gcloud config set project "$PROJECT"

gcloud sql instances create "$INSTANCE" \
  --database-version=POSTGRES_16 \
  --tier=db-custom-2-7680 \
  --region="$REGION" \
  --storage-size=10GB \
  --no-backup

gcloud sql users set-password postgres \
  --instance="$INSTANCE" --password="$(openssl rand -base64 24 | tee /tmp/pgpass)"

# Authorise only your current IP
gcloud sql instances patch "$INSTANCE" \
  --authorized-networks="$(curl -s ifconfig.me)/32"

gcloud sql databases create seats --instance="$INSTANCE"
```

Get the connection details:

```bash
export PGHOST=$(gcloud sql instances describe "$INSTANCE" \
  --format='value(ipAddresses[0].ipAddress)')
export PGUSER=postgres
export PGPASSWORD=$(cat /tmp/pgpass)
export PGDATABASE=seats
psql -c 'SELECT version();'
```

> Prefer the **Cloud SQL Auth Proxy** if your org forbids public IPs:
> `cloud-sql-proxy --port 5432 "$PROJECT:$REGION:$INSTANCE"` then use
> `PGHOST=127.0.0.1`.

---

## 2. Demo A — the connection limit is real and small

This is the single most surprising fact for juniors: your database has a hard
ceiling on connections, it is much lower than they expect, and hitting it takes
the whole service down rather than slowing it gracefully.

```sql
-- What is the actual ceiling?
SHOW max_connections;              -- ~100 on a 2 vCPU Cloud SQL instance

-- How many are in use right now, and what are they doing?
SELECT state, count(*) FROM pg_stat_activity GROUP BY state;

-- What does one idle connection cost the server?
SELECT count(*) AS backends,
       pg_size_pretty(sum(pg_backend_memory_contexts_total())) AS approx_mem
FROM pg_stat_activity, LATERAL (SELECT 1) _;
```

Then blow past it live — this takes about ten seconds and always lands:

```bash
# Open 150 connections against a ~100 connection limit
for i in $(seq 1 150); do
  psql -c 'SELECT pg_sleep(30);' >/dev/null 2>>/tmp/pgerrors &
done
sleep 5
grep -c "too many clients" /tmp/pgerrors
wait
```

**Say out loud:** every application instance holds its own pool. Ten pods ×
a pool of 20 = 200 connections against a limit of 100. The service does not
degrade — it fails to connect, and health checks start failing on pods that
were perfectly healthy.

> **This is the trap from the virtual threads block, made concrete.** Virtual
> threads let one JVM run 10,000 concurrent requests. Your database still
> accepts ~100 connections. Virtual threads did not add database capacity; they
> made it trivially easy to exhaust it. The fix is the same as always: a small
> pool, and back-pressure in the application.

---

## 3. Demo B — pool sizing against the real thing

Run the local simulation's conclusion against the real database with `pgbench`:

```bash
pgbench -i -s 10 "$PGDATABASE"          # initialise ~1M rows

for c in 1 2 4 8 16 32 64 128; do
  printf "clients=%-4s " "$c"
  pgbench -c "$c" -j 4 -T 15 -S "$PGDATABASE" 2>/dev/null \
    | grep -E 'tps|latency average'  | tr '\n' ' '
  echo
done
```

You will see the same curve as `pool_sizing.py`: TPS climbs, plateaus around
2–3× vCPU count, then declines while latency keeps rising. Put the local
simulation's table next to this one on the screen — matching *shapes* from a
20-line model and a real managed database is a strong moment.

---

## 4. Demo C — the lost update, in PostgreSQL

Two-session `psql` is the most convincing way to show this, because the room
watches the anomaly happen one statement at a time.

Note which symptom you get — it depends on how the write is expressed, not on
the engine alone (`real_transactions.py` measures all of these):

  * **counter model** (`UPDATE seats SET sold = <value I read>`) — increments
    are LOST. Locally this confirmed 192 bookings and stored 13.
  * **insert model** (`SELECT count(*)` then `INSERT`) — nothing is lost, but
    the count was stale, so you OVERSELL. Locally: 113 stored against a limit
    of 100.
  * **SQLite** fails a third way, silently rejecting writes.

Same root cause every time; you cannot predict the symptom from the bug.

```sql
CREATE TABLE seats (id int PRIMARY KEY, sold int NOT NULL, version int NOT NULL DEFAULT 0);
INSERT INTO seats VALUES (1, 99, 0);
```

Open **two** psql sessions side by side on the projector:

| | Session 1 | Session 2 |
| --- | --- | --- |
| 1 | `BEGIN;` | |
| 2 | `SELECT sold FROM seats WHERE id=1;` → 99 | |
| 3 | | `BEGIN;` |
| 4 | | `SELECT sold FROM seats WHERE id=1;` → 99 |
| 5 | `UPDATE seats SET sold=100 WHERE id=1;` | |
| 6 | `COMMIT;` | |
| 7 | | `UPDATE seats SET sold=100 WHERE id=1;` |
| 8 | | `COMMIT;` |
| 9 | `SELECT sold FROM seats;` → **100** | Two bookings. One increment. |

Now repeat each fix, live:

```sql
-- Pessimistic: session 2 BLOCKS at step 4 until session 1 commits
SELECT sold FROM seats WHERE id=1 FOR UPDATE;

-- Optimistic: session 2's UPDATE reports 0 rows and it must retry
UPDATE seats SET sold=sold+1, version=version+1 WHERE id=1 AND version=0;

-- Atomic: no read at all, no window to interleave
UPDATE seats SET sold=sold+1 WHERE id=1 AND sold < 100;

-- Constraint: make the bad state unrepresentable
ALTER TABLE seats ADD CONSTRAINT seat_limit CHECK (sold <= 100);

-- Isolation level: the DB now REFUSES rather than silently losing the update
BEGIN ISOLATION LEVEL REPEATABLE READ;
-- ... session 2 gets: ERROR: could not serialize access due to concurrent update
```

That last one is the point to end on: raising the isolation level does not make
your code correct, it makes the database *tell you* when it is not. If you have
no retry logic you have swapped silent corruption for visible 500s — often the
better trade, but a trade.

---

## 5. Demo D — where the connections actually go

Worth 60 seconds if you have them, because it makes "a connection is an
expensive OS resource" concrete rather than abstract:

```sql
-- One PostgreSQL connection = one OS process on the server
SELECT pid, backend_type, state, query
FROM pg_stat_activity
WHERE datname = current_database();

-- Idle-in-transaction is the silent killer: it holds locks AND a connection
SELECT pid, state, now() - state_change AS idle_for, query
FROM pg_stat_activity
WHERE state = 'idle in transaction'
ORDER BY idle_for DESC;
```

**"Idle in transaction" is the single most common production database
incident.** Someone opened a transaction, then made an HTTP call, then a slow
one, and now a connection and a row lock are held for eight seconds per
request. The fix is not a bigger pool — it is never doing I/O inside a
transaction.

---

## 6. Tear down (do not skip)

```bash
gcloud sql instances delete "$INSTANCE" --quiet
rm -f /tmp/pgpass /tmp/pgerrors
```

Add a budget alert to the sandbox project regardless.

---

## If you cannot use GCP on the day

Everything above degrades gracefully:

- **Demos A, B, D** → run `python3 demos/db-scaling/pool_sizing.py`. Say
  explicitly that it is a model, and show the constants at the top of the file.
- **Demo C** → run `python3 demos/db-scaling/transactions.py`, and note that
  SQLite undersells where PostgreSQL oversells.
- The two-session `psql` walk-through also works against **any** local
  PostgreSQL, including `docker run -p 5432:5432 -e POSTGRES_PASSWORD=x postgres:16`.

Given the choice, do the two-session lost-update demo live even if everything
else is simulated. Watching a committed row lose a booking in front of them is
the thing they will remember.
