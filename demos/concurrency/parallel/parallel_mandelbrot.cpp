// Parallel Mandelbrot in C++: std::thread, no external libraries.
//
//     parallel_mandelbrot_cpp <n> <workers>
//
// Compare with the Rust version: the work split is identical, but nothing here
// stops you sharing a mutable variable between threads. Each worker writes only
// to its own slot of `totals`, which is correct by *discipline*, not by proof.
// (Adjacent slots share a cache line, so a hot write loop would false-share;
// here each thread writes once, at the end, so it does not matter.)
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <numeric>
#include <thread>
#include <vector>

static const int MAX_ITER = 50;

static uint64_t band(int n, int y0, int y1) {
    uint64_t inside = 0;
    const double fn = n;
    for (int y = y0; y < y1; y++) {
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

int main(int argc, char** argv) {
    const int n = argc > 1 ? std::atoi(argv[1]) : 1000;
    const int workers = argc > 2 ? std::atoi(argv[2]) : 1;

    const int step = (n + workers - 1) / workers;
    std::vector<uint64_t> totals(workers, 0);
    std::vector<std::thread> threads;

    const auto t0 = std::chrono::steady_clock::now();
    for (int w = 0; w < workers; w++) {
        const int y0 = w * step;
        const int y1 = std::min(y0 + step, n);
        if (y0 >= n) {
            continue;
        }
        threads.emplace_back([&totals, w, n, y0, y1] { totals[w] = band(n, y0, y1); });
    }
    for (auto& t : threads) {
        t.join();
    }
    const uint64_t total = std::accumulate(totals.begin(), totals.end(), uint64_t{0});
    const std::chrono::duration<double, std::milli> ms = std::chrono::steady_clock::now() - t0;

    std::printf("inside=%llu workers=%d ms=%.1f\n", static_cast<unsigned long long>(total), workers,
                ms.count());
    return 0;
}
