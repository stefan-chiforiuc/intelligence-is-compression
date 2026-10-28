// "Warm-up" curve for C++ - the third AOT control group.
//
// Like Rust and Go, C++ is compiled ahead of time, so this line should be
// FLAT. All the optimisation work (inlining, vectorisation, scheduling) was
// done by the compiler at build time, not while your users wait.
//
// Output: one "batch,milliseconds" line per batch, for run.py to chart.
#include <chrono>
#include <cstdint>
#include <cstdio>

static const int BATCHES = 60;
static const int CALLS_PER_BATCH = 200;
static const int SIZE = 16;
static const int MAX_ITER = 50;

__attribute__((noinline)) static uint64_t kernel(int n) {
    uint64_t inside = 0;
    const double fn = n;
    for (int y = 0; y < n; y++) {
        const double ci = 2.0 * y / fn - 1.0;
        for (int x = 0; x < n; x++) {
            const double cr = 2.0 * x / fn - 1.5;
            double zr = 0.0, zi = 0.0;
            int i = 0;
            while (i < MAX_ITER && zr * zr + zi * zi <= 4.0) {
                const double t = zr * zr - zi * zi + cr;
                zi = 2.0 * zr * zi + ci;
                zr = t;
                i++;
            }
            if (i == MAX_ITER) {
                inside++;
            }
        }
    }
    return inside;
}

int main() {
    using clock = std::chrono::steady_clock;
    // volatile keeps the compiler from hoisting the call out of the loop.
    volatile int size = SIZE;
    uint64_t sink = 0;
    for (int b = 0; b < BATCHES; b++) {
        const auto t0 = clock::now();
        for (int c = 0; c < CALLS_PER_BATCH; c++) {
            sink += kernel(size);
        }
        const std::chrono::duration<double, std::milli> ms = clock::now() - t0;
        std::printf("%d,%.3f\n", b, ms.count());
    }
    if (sink == UINT64_MAX) {
        std::puts("unreachable");
    }
    return 0;
}
