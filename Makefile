# Programming language trade-offs — 3-hour training
#
# Everything the session needs, in the order you need it:
#
#   make setup     install deps and generate the benchmark corpus
#   make bench     run the full suite, regenerate docs/RESULTS.md
#   make verify    run every demo once (do this before you present)
#
# Individual blocks:
#   make demo-typing   demo-jit   demo-memory   demo-gc   carbon

SHELL := /bin/bash
PY    := python3
DATA  := data/words.txt

# Filters the JAVA_TOOL_OPTIONS banner some environments inject into stderr.
NOJAVANOISE := 2>&1 | grep -v 'Picked up JAVA_TOOL_OPTIONS' || true

.DEFAULT_GOAL := help

# --------------------------------------------------------------------------
.PHONY: help
help:
	@echo ""
	@echo "  Programming language trade-offs — training repo"
	@echo "  ============================================================"
	@echo ""
	@echo "  Before the session:"
	@echo "    make setup          install deps, generate the corpus"
	@echo "    make bench          run the suite, write docs/RESULTS.md"
	@echo "    make verify         smoke-test every demo end to end"
	@echo ""
	@echo "  During the session (one per block):"
	@echo "    make bench-corpus     block 0b — same benchmark, two corpora"
	@echo "    make demo-typing      block 1  — static/dynamic, strong/weak, erasure"
	@echo "    make demo-jit         block 2  — AOT vs JIT warm-up curves"
	@echo "    make demo-tailcalls   block 2b — Java vs Scala vs Kotlin, TCO"
	@echo "    make demo-memory      block 3  — stack vs heap, object cost"
	@echo "    make demo-gc          block 3  — collectors and tail latency"
	@echo "    make demo-concurrency block 4  — parallel scaling + data races"
	@echo "    make demo-parallel-cost block 4b — when NOT to parallelise; virtual threads"
	@echo "    make demo-api-race    block 4b — 20 users, one shared array, real HTTP"
	@echo "    make demo-db          block 5b — connection pools + transaction races"
	@echo "                                     (start a real DB first: make db-up)"
	@echo "    make bench-startup    block 5  — cold starts only (fast)"
	@echo "    make carbon           block 6  — energy and CO2e estimate"
	@echo ""
	@echo "  Utilities:"
	@echo "    make doctor         check every toolchain is installed"
	@echo "    make build          compile everything, run nothing"
	@echo "    make clean          remove build output"
	@echo ""

# --------------------------------------------------------------------------
.PHONY: doctor
doctor:
	@echo "Checking toolchains ..."
	@for t in $(PY) go rustc cargo node npx java javac; do \
		if command -v $$t >/dev/null 2>&1; then \
			printf "  \033[32m ok \033[0m %-8s %s\n" "$$t" "$$(command -v $$t)"; \
		else \
			printf "  \033[31mMISS\033[0m %-8s not found in PATH\n" "$$t"; \
		fi; \
	done
	@echo ""
	@echo "Versions:"
	@$(PY) --version 2>&1        | sed 's/^/  /'
	@go version 2>/dev/null      | sed 's/^/  /' || echo "  go: missing"
	@rustc --version 2>/dev/null | sed 's/^/  /' || echo "  rustc: missing"
	@node --version 2>/dev/null  | sed 's/^/  node /' || echo "  node: missing"
	@java -version 2>&1 | grep -v 'Picked up JAVA_TOOL_OPTIONS' | head -1 | sed 's/^/  /'

# --------------------------------------------------------------------------
.PHONY: setup
setup: node_modules $(DATA)
	@$(PY) tools/bench.py --build
	@echo ""
	@echo "Setup complete. Next: make bench"

node_modules: package.json
	@echo "Installing TypeScript toolchain ..."
	@npm install --silent || echo "npm install failed — the harness will fall back to Node type stripping"
	@touch node_modules

$(DATA):
	@$(PY) tools/gen_words.py $(DATA)

.PHONY: data
data: $(DATA)

# Real English: 154 3Blue1Brown transcripts, same 3,000,000 words as the
# synthetic corpus so the two are directly comparable. Needs network once.
# Add your own text (e.g. the 2026 "Compression is Intelligence" transcript):
#   python3 tools/get_transcript.py --extra path/to/transcript.txt
data/transcript.txt:
	@$(PY) tools/get_transcript.py

.PHONY: transcript
transcript: data/transcript.txt

# --------------------------------------------------------------------------
.PHONY: build
build: node_modules
	@$(PY) tools/bench.py --build

.PHONY: bench
bench: $(DATA) node_modules
	@$(PY) tools/bench.py --reps 5 --warmup 1 --json results.json --md docs/RESULTS.md
	@echo ""
	@echo "Wrote docs/RESULTS.md — this is now YOUR machine's data."

.PHONY: bench-quick
bench-quick: $(DATA) node_modules
	@$(PY) tools/bench.py --reps 2 --warmup 0

.PHONY: bench-startup
bench-startup:
	@$(PY) tools/bench.py --workloads startup --reps 10 --warmup 2

.PHONY: bench-cpu
bench-cpu:
	@$(PY) tools/bench.py --workloads mandelbrot --reps 5

# Block 0b: the same benchmark on two different corpora. Same 3,000,000 words;
# only the vocabulary differs (50,000 invented vs 10,469 real English).
.PHONY: bench-corpus
bench-corpus: $(DATA) data/transcript.txt
	@echo ""
	@echo "=============================================================="
	@echo "A. SYNTHETIC corpus - 50,000 invented words, 3,000,000 tokens"
	@echo "=============================================================="
	@$(PY) tools/bench.py --workloads wordfreq --reps 5 --warmup 1 --no-build --corpus synthetic
	@echo ""
	@echo "=============================================================="
	@echo "B. REAL ENGLISH - 10,469 distinct words, 3,000,000 tokens"
	@echo "   (154 3Blue1Brown transcripts)"
	@echo "=============================================================="
	@$(PY) tools/bench.py --workloads wordfreq --reps 5 --warmup 1 --no-build --corpus transcript
	@echo ""
	@echo "Same programs. Same word count. Only the vocabulary changed."
	@echo "See docs/11-the-data-is-the-workload.md"

# --------------------------------------------------------------------------
.PHONY: demo-typing
demo-typing:
	@bash demos/typing/run.sh

.PHONY: demo-typing-fast
demo-typing-fast:
	@bash demos/typing/run.sh --fast

.PHONY: demo-jit
demo-jit:
	@$(PY) demos/jit-warmup/run.py --xint

.PHONY: demo-memory
demo-memory:
	@bash demos/stack-heap/run.sh

.PHONY: demo-objsize
demo-objsize:
	@bash demos/stack-heap/objsize/run.sh

.PHONY: demo-gc
demo-gc:
	@bash demos/gc/run.sh

.PHONY: demo-gc-log
demo-gc-log:
	@bash demos/gc/run.sh --log

# --- Block 2b: tail calls on the JVM ---------------------------------------
# Standalone Scala + Kotlin compilers, straight from Maven Central. No SDKMAN,
# no Gradle, no coursier — just jars and `java -cp`.
build/jvm-langs/env.sh:
	@bash tools/get_jvm_langs.sh

.PHONY: jvm-langs
jvm-langs: build/jvm-langs/env.sh

.PHONY: demo-tailcalls
demo-tailcalls: build/jvm-langs/env.sh
	@bash demos/tail-calls/run.sh

# --- Block 4: concurrency ---------------------------------------------------
.PHONY: demo-concurrency
demo-concurrency:
	@bash demos/concurrency/run.sh

.PHONY: demo-parallel
demo-parallel:
	@python3 demos/concurrency/parallel/run.py

.PHONY: demo-races
demo-races:
	@bash demos/concurrency/races/run.sh

# --- Block 4b: when to parallelise, virtual threads, the API race -----------
.PHONY: demo-parallel-cost
demo-parallel-cost:
	@mkdir -p build/demos/parcost
	@javac -d build/demos/parcost demos/java-parallel-cost/*.java $(NOJAVANOISE)
	@java -cp build/demos/parcost ParallelCost $(NOJAVANOISE)
	@echo ""
	@java -cp build/demos/parcost VirtualThreads $(NOJAVANOISE)

.PHONY: demo-api-race
demo-api-race:
	@bash demos/api-race/run.sh

# --- Block 5b: databases ----------------------------------------------------
# A deliberately small PostgreSQL: 1 CPU, 512 MB, max_connections=50, so the
# pool plateau and the connection wall both arrive while the room is watching.
.PHONY: db-up
db-up:
	@bash demos/db-scaling/db.sh up

.PHONY: db-down
db-down:
	@bash demos/db-scaling/db.sh down

.PHONY: db-status
db-status:
	@bash demos/db-scaling/db.sh status

.PHONY: db-psql
db-psql:
	@bash demos/db-scaling/db.sh psql

# Uses the real database if one is reachable; otherwise falls back to the
# simulation and says so.
.PHONY: demo-db
demo-db:
	@bash demos/db-scaling/run.sh

.PHONY: demo-db-sim
demo-db-sim:
	@bash demos/db-scaling/run.sh --sim

.PHONY: demo-db-wall
demo-db-wall:
	@$(PY) demos/db-scaling/exhaust_connections.py

.PHONY: demo-db-pool
demo-db-pool:
	@$(PY) demos/db-scaling/real_pool.py

.PHONY: demo-db-txn
demo-db-txn:
	@$(PY) demos/db-scaling/real_transactions.py

.PHONY: demo-db-pool-sim
demo-db-pool-sim:
	@$(PY) demos/db-scaling/pool_sizing.py

.PHONY: demo-db-txn-sim
demo-db-txn-sim:
	@$(PY) demos/db-scaling/transactions.py

.PHONY: carbon
carbon: results.json
	@$(PY) tools/carbon.py --requests 50e6
	@echo ""
	@echo "Now run the same thing on a clean grid — this is the punchline:"
	@echo "  $(PY) tools/carbon.py --requests 50e6 --region eu-north-1"

results.json:
	@echo "No results.json yet — running the benchmark first."
	@$(MAKE) --no-print-directory bench

# --------------------------------------------------------------------------
.PHONY: verify
verify: setup jvm-langs
	@echo ""
	@echo "=== 1/12 benchmark suite (quick) ==============================="
	@$(PY) tools/bench.py --reps 1 --warmup 0 --no-build
	@echo ""
	@echo "=== 2/12 typing demo ==========================================="
	@bash demos/typing/run.sh --fast >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 3/12 jit warm-up demo ======================================"
	@$(PY) demos/jit-warmup/run.py --langs rust go java >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 4/12 tail-call demo (Java/Scala/Kotlin) ===================="
	@bash demos/tail-calls/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 5/12 memory demo ==========================================="
	@bash demos/stack-heap/objsize/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 6/12 gc demo ==============================================="
	@bash demos/gc/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 7/12 parallel scaling demo ================================="
	@$(PY) demos/concurrency/parallel/run.py --size 600 >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 8/12 data race demo ========================================"
	@bash demos/concurrency/races/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 9/12 parallelism cost + virtual threads ==================="
	@mkdir -p build/demos/parcost
	@javac -d build/demos/parcost demos/java-parallel-cost/*.java $(NOJAVANOISE)
	@java -cp build/demos/parcost ParallelCost >/dev/null 2>&1 && echo "  ok"
	@echo ""
	@echo "=== 10/12 api race (20 users, shared array) ==================="
	@bash demos/api-race/run.sh 8 5 50 >/dev/null 2>&1 && echo "  ok"
	@echo ""
	@echo "=== 11/12 database pools + transactions ======================="
	@bash demos/db-scaling/run.sh >/dev/null 2>&1 && echo "  ok (real DB or simulation, whichever was reachable)"
	@echo ""
	@echo "=== 12/12 carbon estimate ====================================="
	@$(PY) tools/carbon.py >/dev/null && echo "  ok"
	@echo ""
	@echo "All demos ran. You are ready to present."

# --------------------------------------------------------------------------
.PHONY: typecheck
typecheck: node_modules
	@npx tsc -p tsconfig.json --noEmit && echo "TypeScript: no type errors"

.PHONY: clean
clean:
	@rm -rf build results.json
	@find . -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
	@echo "Cleaned build output. (data/ and node_modules/ kept — use clean-all)"

.PHONY: clean-all
clean-all: clean
	@rm -rf data node_modules package-lock.json
	@echo "Cleaned everything."
