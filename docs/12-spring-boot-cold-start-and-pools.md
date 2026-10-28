# Block 4d / 5c — Spring Boot: real cold start, real thread pool

**Run:** `make demo-spring` (first run downloads Spring dependencies)

The rest of this repo measures languages. This block measures a **framework**,
because two of the session's headline numbers are floors that nobody actually
ships.

---

## Part 1 — What a framework actually costs to start

`benchmarks/startup/Hello.java` boots a JVM and loads one class: **69 ms**.
Nobody ships `Hello.java`.

Measured on the same 4-vCPU machine, median of 3, page cache warmed:

| Configuration | Time to first HTTP 200 | Spring's own figure |
| --- | ---: | ---: |
| **Spring Boot, defaults** | **4626 ms** | 3.75 s |
| `-XX:TieredStopAtLevel=1` | 4354 ms | 3.65 s |
| `+ lazy initialisation` | 4114 ms | 3.33 s |
| `-Xshare:off` (CDS disabled) | 4771 ms | 3.88 s |

(An earlier full run gave 4444 / 4212 / 4401 / 4695 ms: there, lazy
initialisation was *not* faster than the `TieredStopAtLevel=1` row. Run-to-run
noise is ~5%. The honest summary is that the three variants land within ~11% of
the default, and that none is a game-changer on this machine.)

Put next to the language table:

| | Cold start | vs C++ / Rust / Go |
| --- | ---: | ---: |
| C++ / Rust / Go `hello` | 1.5 ms | 1× |
| bare .NET `Hello.cs` | 44 ms | 28× |
| bare JVM `Hello.java` | 69 ms | 45× |
| **Spring Boot (this app)** | **4626 ms** | **~3000×** |

> **67× the bare JVM, and this app is tiny.** Four endpoints, no security, no
> JPA, no Kafka, no messaging, no service mesh. A real enterprise service is
> routinely **15–60 seconds**.

### Ask the room

*"What is your application's startup time?"* Most people do not know. That is
itself the lesson — it is a number with direct consequences that nobody looks at.

### What the number decides

- **Serverless.** 4.6 s of cold start on a Lambda is not a tax, it is a
  disqualification, unless you use SnapStart/CRaC or GraalVM native-image.
- **Rolling deploys.** `startup × pods ÷ parallelism` = deploy duration =
  rollback time = how brave you feel deploying on a Friday.
- **Autoscaling.** You cannot react to a 10-second spike with a 40-second pod.
- **`startupProbe`.** `failureThreshold × periodSeconds` must exceed your
  *worst* startup, or Kubernetes kills the pod mid-boot in a crash loop.

### Two honest caveats

**Lazy initialisation is not free.** It moves work from startup to the *first
request that touches each bean*. Your p99 gets worse immediately after every
deploy — exactly when traffic is being shifted onto the new pods. Good for a
CLI or a scale-to-zero function; bad for a service that must be fast on
rollout.

**`-Xshare:off` is in the table to prove CDS is working**, not as a suggestion.
It is the slowest row — that gap is what Class Data Sharing already buys you by
default, the same effect Block 2 measured on the bare JVM.

---

## Part 2 — The request thread pool

Tomcat's default is **200 threads**. Most teams have never looked at that
number, let alone chosen it. It is a hard ceiling on how many requests can be
**in flight**.

Load: 100 concurrent users × 5 requests to `/io?ms=100` (a blocking endpoint —
i.e. what 95% of real endpoints do).

| Configuration | Throughput | p50 | p99 | Serving thread |
| --- | ---: | ---: | ---: | --- |
| `threads.max=10` | **96 r/s** | **1038 ms** | 1055 ms | platform |
| `threads.max=50` | 442 r/s | 205 ms | 237 ms | platform |
| `threads.max=200` (default) | 507 r/s | 130 ms | 198 ms | platform |
| **virtual threads** | **610 r/s** | 121 ms | **166 ms** | **virtual** |

### 1. The pool is a hard ceiling, and it is predictable

Little's law: with `P` requests in flight each taking `S` seconds, throughput is
`P/S`. With `threads.max=10` and a 100 ms endpoint:

```
10 threads / 0.100 s = 100 req/s   predicted
                        96 req/s   measured
```

**The arithmetic predicted the machine.** Everything past 10 concurrent
requests waits in Tomcat's accept queue — which is why p50 is **1038 ms for a
100 ms endpoint**. Over 90% of that latency is queue time, and your endpoint
timer will not show it. It looks fast in the application logs and slow to the
user.

### 2. Raising it helps — until it does not

10 → 200 buys real throughput here, because these threads are **sleeping**, not
computing. Run the same sweep against `/cpu` and the curve flattens at your
core count instead.

> Which knob helps depends entirely on whether you are **waiting or computing**
> — the same question as Block 4, one layer up the stack.

### 3. Virtual threads remove the ceiling

`spring.threads.virtual.enabled=true` (Spring Boot 3.2+, JDK 21) and
`threads.max` stops mattering: each request gets its own virtual thread and
blocking is cheap. Note the *serving thread* column flips from `platform` to
`virtual` — that is your proof it actually switched on, and `/whoami` shows it
in one curl.

The gain over a well-tuned 200-thread pool is modest here (610 vs 507 r/s, +20%).
**That is the honest result.** Virtual threads' win is not raw throughput at
this scale — it is that you stop having to guess the number, and you keep
scaling when concurrency goes to 10,000 where 10,000 platform threads would not
fit.

### 4. And that is exactly where the danger is

Your 200-thread pool was **also an accidental rate limiter**. It guaranteed you
never had more than 200 requests concurrently reaching for:

- a HikariCP pool of **10**
- a downstream service with its own limits
- a database with `max_connections=50`

Remove the accident without adding a deliberate limit and the next bottleneck
finds out the hard way. Watch it happen live, using the database from Block 5b:

```bash
make db-up
python3 demos/spring-boot/run.py --part 2 --path '/db?sleepMs=100'
```

`/db` reports `connectionWaitMs` — the time spent *waiting for a connection*,
not executing. Virtual threads will not make a pool of 10 into 11.

---

## The three settings, and how they interact

```properties
server.tomcat.threads.max=200                 # requests in flight
spring.threads.virtual.enabled=false          # or remove the ceiling entirely
spring.datasource.hikari.maximum-pool-size=10 # the REAL ceiling, usually
```

The third one is almost always the binding constraint, and it is the one people
tune last. A 200-thread pool in front of a 10-connection pool means 190 threads
can be parked waiting on Hikari — burning memory, holding request state, and
timing out — while the database is barely working.

**Size from the back forwards:** database capacity → connection pool → request
threads → replicas. Most teams do it in exactly the opposite order.

---

## Mitigations for the cold start

| Technique | Effect | Cost |
| --- | --- | --- |
| CDS (already on) | measured above as the `-Xshare:off` gap | none |
| AppCDS with your classes | 20–40% on a class-heavy app | small build step, needs a JAR |
| `-XX:TieredStopAtLevel=1` | ~7% here; helps short-lived processes | lower peak throughput — do **not** use on a long-running service |
| Lazy initialisation | ~11% here | worse p99 after deploy |
| **GraalVM native-image** | seconds → **tens of milliseconds** | slow builds, reflection config, lower peak throughput |
| **CRaC / Lambda SnapStart** | restore from a warmed snapshot | infrastructure complexity |
| **Keep it warm** | eliminates the problem | you pay for idle capacity |

For most teams running long-lived services, the last row is the correct answer
and the whole issue is a non-problem. **Cold start only matters in proportion to
how often you pay it** — which is Block 2's execution-shape question again.

---

## Discussion prompts

1. Your service starts in 40 s and you run 30 pods with `maxSurge: 1`. How long
   is a deploy, and what does that do to your incident response?
2. p50 is 1038 ms for an endpoint whose own timer says 100 ms. Where is the
   other 938 ms, and why does your APM not show it? *(Queue time before the
   request was assigned a thread. Most instrumentation starts the clock at the
   controller.)*
3. You enable virtual threads and throughput barely moves. Name two reasons.
   *(You were not thread-limited — the DB pool or a downstream was the real
   bottleneck; or your work is CPU-bound.)*
4. Why might a 200-thread pool in front of a 10-connection pool be *worse* than
   a 20-thread pool? *(180 threads parked on Hikari: memory, held request
   state, timeouts, and a queue you cannot see. A smaller pool sheds load
   earlier and more honestly.)*
