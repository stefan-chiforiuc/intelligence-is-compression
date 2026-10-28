// CPU-bound workload: count points inside the Mandelbrot set.
//
// Pure scalar float math in a tight nested loop. No allocation, no I/O.
// This isolates *raw interpreter/compiler quality* from everything else.
//
// Build note: compiled with -ffp-contract=off. GCC otherwise fuses a*b+c into
// a single FMA when -march=native is on, which rounds differently from the
// other languages and could change the count at the set's boundary.
#include <cstdint>
#include <cstdio>
#include <cstdlib>

static const int MAX_ITER = 50;

static uint64_t mandelbrot(int n) {
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

int main(int argc, char** argv) {
    const int n = argc > 1 ? std::atoi(argv[1]) : 1000;
    std::printf("%llu\n", static_cast<unsigned long long>(mandelbrot(n)));
    return 0;
}
