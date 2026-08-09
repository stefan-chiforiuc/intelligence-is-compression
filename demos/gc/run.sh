#!/usr/bin/env bash
# Garbage collectors, compared the way your users experience them: by tail latency.
#
#   bash demos/gc/run.sh          # the comparison table
#   bash demos/gc/run.sh --log    # also show live GC events for the default JVM
set -uo pipefail
cd "$(dirname "$0")/../.."
mkdir -p build/demos

say() { printf '\n\033[1;36m%s\033[0m\n' "$*"; }
rule() { printf '\033[1;34m%s\033[0m\n' "==============================================================================="; }

echo "Building ..."
javac -d build/demos demos/gc/Service.java 2>&1 | grep -v 'Picked up' || true
go build -o build/demos/service_go demos/gc/service.go

run_java() {
  local label="$1"; shift
  printf '\n\033[1m%s\033[0m\n' "$label"
  # shellcheck disable=SC2086
  java "$@" -Xmx512m -Xms512m -cp build/demos Service 2>&1 | grep -v 'Picked up' | sed 's/^/    /'
}

run_go() {
  local label="$1"; shift
  printf '\n\033[1m%s\033[0m\n' "$label"
  env "$@" build/demos/service_go | sed 's/^/    /'
}

rule
echo "JVM COLLECTORS - same code, same heap, different collector"
rule

run_java "SerialGC     (single-threaded, stop-the-world; tiny heaps, CLI tools)" -XX:+UseSerialGC
run_java "ParallelGC   (throughput-first, stop-the-world; batch jobs)"           -XX:+UseParallelGC
run_java "G1GC         (default since 11; balanced, region-based)"               -XX:+UseG1GC
run_java "ZGC          (concurrent, sub-millisecond pauses; latency-critical)"   -XX:+UseZGC -XX:+ZGenerational 2>/dev/null \
  || run_java "ZGC          (concurrent, sub-millisecond pauses; latency-critical)" -XX:+UseZGC

echo
rule
echo "GO COLLECTOR - same code, different GOGC"
rule

run_go "GOGC=100     (default: collect when the heap doubles)" GOGC=100
run_go "GOGC=400     (collect 4x less often - faster, more memory)" GOGC=400
run_go "GOGC=off     (never collect - fastest, unbounded memory)" GOGC=off
run_go "GOMEMLIMIT   (soft 256 MiB ceiling - the right knob for containers)" GOGC=100 GOMEMLIMIT=256MiB

if [[ "${1:-}" == "--log" ]]; then
  echo
  rule
  echo "LIVE GC EVENTS (default collector, first 25 lines)"
  rule
  java -Xlog:gc -Xmx512m -cp build/demos Service 2>&1 | grep -v 'Picked up' | head -25
fi

cat <<'EOF'

===============================================================================
WHAT TO POINT AT
===============================================================================

  1. The MEAN barely moves between collectors. If you only look at averages you
     will conclude GC choice does not matter. It matters enormously - just not
     in the mean.

  2. Look at max and p99/p50. That is where a collector's personality shows:
       SerialGC    lowest overhead, worst pauses. Great for a CLI tool that
                   runs for 200 ms; catastrophic for a 100 GB heap.
       ParallelGC  best raw throughput, still stops the world. Batch jobs.
       G1GC        tries to hit a pause target by collecting regions
                   incrementally. The sane default.
       ZGC         does almost everything concurrently; pauses stay sub-ms
                   even on huge heaps, paid for in CPU and memory overhead.

  3. GOGC=off usually comes out SLOWER here, and that surprise is worth a
     minute of discussion. Turning the collector off does not just risk an
     OOM-kill - it lets the live heap sprawl until it no longer fits in cache
     and the allocator is touching cold pages. "Less GC" and "faster" are not
     the same thing; a compacting collector also improves locality.
     Meanwhile GOGC=400 IS faster than the default, because it collects less
     often while the heap is still small enough to stay cache-friendly.
     Every GC setting is a dial between CPU, memory and pause time, and the
     optimum is rarely at either extreme.

  4. Rust and C++ do not appear in this table because they have no collector.
     Their equivalent cost is spread evenly across every drop/free, and it
     shows up as a higher mean rather than a worse tail. That is why Rust is
     attractive for latency-critical work: there is no pause to tune, because
     there is no pause.

  5. For containers: set -XX:MaxRAMPercentage (Java) or GOMEMLIMIT (Go).
     A JVM that does not know it is in a container will size its heap from the
     HOST's memory and get OOM-killed. This is the single most common
     production incident with JVMs on Kubernetes.
EOF
