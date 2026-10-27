# Block 4 — Cold starts and cloud deployment

**Run:** `make bench-startup`

---

## The measurement

A program that parses one argument and prints one line. Everything measured
here happens **before your business logic runs**: process spawn, dynamic
linking, runtime/VM initialisation, class loading, module resolution.

| Language | Cold start | Baseline RSS | Typical image size |
| --- | ---: | ---: | ---: |
| C++ | **1.5 ms** | 14.6 MB | 5–30 MB (static on scratch, or distroless/cc) |
| Rust | 1.9 ms | 14.6 MB | 5–10 MB (scratch/distroless) |
| Go | 2.0 ms | 14.6 MB | 10–20 MB (scratch/distroless) |
| Python | 18.5 ms | 14.6 MB | 50–120 MB (slim) |
| Node | 34 ms | 42.8 MB | 60–150 MB (slim/alpine) |
| C# | 44 ms | 23.3 MB | 80–220 MB (.NET runtime image); 10–30 MB with Native AOT |
| Java | 69 ms | 40.1 MB | 180–400 MB (JRE base) |

(Cold start and RSS are measured: median of 11, `make bench-startup`. Image
sizes are typical figures, not measured here.)

Two results worth pausing on:

- **Python starts 1.8x faster than Node.** People expect the opposite. CPython's
  interpreter boot is cheap; V8 has a much larger heap and bootstrap to set up.
- **C++, Rust and Go are indistinguishable** (1.5–2.0 ms) and effectively at the
  floor imposed by `execve` itself. There is no runtime to initialise.
- **C# sits between Node and Java** (44 ms). `dotnet app.dll` first has to find
  and load the runtime (`hostfxr`, `hostpolicy`, the CLR), then JIT `Main`
  before it can print anything. ReadyToRun and Native AOT exist to shrink this.

> These are floors, and the floor is not what you ship. **We measured a real
> Spring Boot app: 4626 ms** — 67× the bare JVM and ~3000× Go — and that app has
> four endpoints and no security, JPA or messaging. See
> [Block 4d](12-spring-boot-cold-start-and-pools.md) and run `make demo-spring`.
> Measure *your* app, not `Hello`.

---

## Why this is the most decision-relevant table in the session

Cold start is not one cost — it is a cost multiplied by how often you pay it.

### Serverless

You pay cold start on **every scale-out event**, and on every invocation if you
are scaled to zero. A 69 ms JVM boot on a 100 ms function is a **69% tax on
every request that hits a cold instance**.

This is why AWS Lambda's Java story is dominated by workarounds — provisioned
concurrency, SnapStart, GraalVM — and why Go and Rust are over-represented in
Lambda-native architectures.

### Autoscaling

Cold start *is* how fast you can absorb a traffic spike. If your pods take 40
seconds to become ready, your autoscaler cannot react to a 10-second spike, and
you must over-provision permanently. That over-provisioning is a direct,
recurring cash cost of a slow start-up.

### Rolling deploys

`cold start × number of pods ÷ parallelism` = deploy duration, which sets your
rollback time, which sets how brave you feel about deploying on a Friday.

### Bin packing — the one that actually dominates the bill

Baseline RSS decides how many replicas fit on a node; node count is most of your
compute bill.

A worked example, 100 replicas on 8 GB nodes:

| Runtime | RSS/replica | Replicas/node | Nodes needed |
| --- | ---: | ---: | ---: |
| Go | 40 MB | ~180 | **1** |
| Java (512 MB heap) | 700 MB | ~11 | **10** |

Same service, same traffic, 10x the nodes. That is usually a much bigger number
than any CPU efficiency difference — and it is the strongest *practical*
argument for a compact runtime.

---

## Mitigations — so nobody leaves thinking "never use Java"

### Java

| Technique | Effect | Cost |
| --- | --- | --- |
| CDS (default, already on) | ~37% of startup — verify with `-Xshare:off` | none |
| AppCDS | scales with your class count; ~0 on a trivial app, 20–40% on a big one | needs a JAR, small build step |
| GraalVM native-image | 69 ms → ~5 ms | slow builds, reflection config, lower peak throughput |
| CRaC / Lambda SnapStart | restore from a warmed snapshot | infra complexity, snapshot correctness |
| **Keep the JVM warm** | eliminates the problem | you pay for idle capacity |

The last one is the honest answer for most teams. A long-lived pod behind a
queue makes the whole problem disappear, and it is why the JVM remains
excellent for long-running services.

### .NET

| Technique | Effect | Cost |
| --- | --- | --- |
| ReadyToRun | precompiles IL to native code, so there is much less JIT at start-up | bigger assemblies; still boots the runtime |
| Native AOT | a self-contained native binary: no JIT, no runtime to boot | no runtime codegen, restricted reflection, trimming warnings |
| Trimming | smaller image | reflection-heavy libraries break |

(These are the standard options; this repo measures the default `dotnet app.dll`
only, so we have no numbers for them.)

### Node

- **Bundle to a single file** (esbuild/rollup). Module resolution over a deep
  `node_modules` tree routinely costs more than V8's boot. Biggest single win.
- Avoid top-level imports of things you may not need; import lazily.
- V8 snapshots / `--snapshot-blob` for CLI tools.

### Python

- Avoid heavy imports at module scope — `import pandas` alone is ~200 ms.
- Import inside the function that needs it for rarely-used paths.
- Ship `.pyc` files pre-compiled in the image.

---

## Container image checklist

### Multi-stage builds, always

```dockerfile
# ---- build stage ----
FROM golang:1.24 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download                 # cached layer: deps change rarely
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /app ./cmd/server

# ---- runtime stage ----
FROM gcr.io/distroless/static:nonroot
COPY --from=build /app /app
USER nonroot:nonroot
ENTRYPOINT ["/app"]
```

Result: ~10 MB, no shell, no package manager, no CVEs from tooling you never
ship. The equivalent single-stage image is ~900 MB.

### Base image choice

| Base | Size | Use when |
| --- | ---: | --- |
| `scratch` | 0 MB | static binaries (Go with `CGO_ENABLED=0`, Rust musl) |
| `distroless/static` | ~2 MB | static binaries, want certs + tzdata + nonroot |
| `distroless/java21` | ~180 MB | JVM without a distro |
| `alpine` | ~5 MB | need a shell; **beware musl** — different malloc, real perf differences for JVM/Python |
| `debian-slim` | ~30 MB | need glibc and a package manager |

**Alpine warning worth stating explicitly:** musl's allocator behaves very
differently from glibc's under multi-threaded load. Alpine has produced
surprising slowdowns for JVM and Python workloads. Do not switch to Alpine for
image size without measuring.

### Layer ordering

Copy dependency manifests and install **before** copying source. Dependencies
change rarely, source changes constantly. Wrong order = full reinstall on every
commit.

### Pin your base images

`FROM node:22` is a moving target. `FROM node:22.22.2-slim@sha256:...` is
reproducible. Reproducible builds are a prerequisite for debugging a
regression.

---

## Kubernetes settings that follow from Block 3

```yaml
resources:
  requests:                 # what the scheduler reserves — set from measured p50
    memory: "256Mi"
    cpu: "100m"
  limits:                   # the hard ceiling — set from measured peak RSS + headroom
    memory: "512Mi"
    # cpu: intentionally omitted - see below

startupProbe:               # the probe that makes slow-starting runtimes safe
  httpGet: { path: /health, port: 8080 }
  failureThreshold: 30
  periodSeconds: 2          # allows up to 60 s to start
readinessProbe:
  httpGet: { path: /ready, port: 8080 }
  periodSeconds: 5
```

Four rules:

1. **Use a `startupProbe` for slow starters.** Without it you must set a
   liveness `initialDelaySeconds` long enough for the worst case, which delays
   detection of real failures forever. A `startupProbe` gives a slow runtime
   room to boot *and* keeps liveness checks tight afterwards.
2. **Set the runtime's own memory ceiling**, not just the container limit:
   `-XX:MaxRAMPercentage=75`, `GOMEMLIMIT`, `--max-old-space-size`.
3. **Think hard before setting a CPU limit.** CFS throttling on a JIT runtime
   during warm-up is a classic self-inflicted latency wound: the JVM needs CPU
   *most* exactly when it is starting, and a limit strangles it. Set requests;
   be cautious with limits.
4. **`readiness` ≠ `liveness`.** Readiness removes you from the load balancer;
   liveness kills the pod. Confusing them turns a slow dependency into a crash
   loop.

---

## Discussion prompts

1. Your Lambda p50 is 40 ms, p99 is 900 ms. What is the first hypothesis?
   *(Cold starts. Check the invocation-to-init ratio before optimising code.)*
2. You must run 200 replicas of a small service on a fixed node budget. Which
   column of the table decides the language? *(Baseline RSS, not CPU.)*
3. When is a 400 MB Java image completely fine? *(Long-lived service, deployed
   a few times a week, where 69 ms of start-up is invisible and the JVM's
   throughput and ecosystem win.)*
4. Your team wants to move a Python service to Alpine to cut image size. What
   do you ask for first? *(A benchmark on musl. Image size is not free.)*
