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
	@echo "    make demo-typing      block 1  — static/dynamic, strong/weak, erasure"
	@echo "    make demo-jit         block 2  — AOT vs JIT warm-up curves"
	@echo "    make demo-tailcalls   block 2b — Java vs Scala vs Kotlin, TCO"
	@echo "    make demo-memory      block 3  — stack vs heap, object cost"
	@echo "    make demo-gc          block 3  — collectors and tail latency"
	@echo "    make demo-concurrency block 4  — parallel scaling + data races"
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
	@echo "=== 1/9 benchmark suite (quick) ==============================="
	@$(PY) tools/bench.py --reps 1 --warmup 0 --no-build
	@echo ""
	@echo "=== 2/9 typing demo ==========================================="
	@bash demos/typing/run.sh --fast >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 3/9 jit warm-up demo ======================================"
	@$(PY) demos/jit-warmup/run.py --langs rust go java >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 4/9 tail-call demo (Java/Scala/Kotlin) ===================="
	@bash demos/tail-calls/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 5/9 memory demo ==========================================="
	@bash demos/stack-heap/objsize/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 6/9 gc demo ==============================================="
	@bash demos/gc/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 7/9 parallel scaling demo ================================="
	@$(PY) demos/concurrency/parallel/run.py --size 600 >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 8/9 data race demo ========================================"
	@bash demos/concurrency/races/run.sh >/dev/null && echo "  ok"
	@echo ""
	@echo "=== 9/9 carbon estimate ======================================="
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
