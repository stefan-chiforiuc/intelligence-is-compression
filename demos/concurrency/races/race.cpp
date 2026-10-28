// C++: the same race. The compiler does not object, and it is not just a wrong
// answer - it is *undefined behaviour*.
//
//   g++ -O0 -std=c++20 -pthread race.cpp && ./a.out
//
// A data race on a non-atomic object is UB in the C++ memory model (since
// C++11). That is a stronger statement than "you lose some increments": the
// optimiser is entitled to assume the race cannot happen, so what you observe
// can change with -O level, compiler version or CPU. Build this with -O0 and
// again with -O2 and compare: at -O2 GCC turns each thread's 100,000-iteration
// loop into a single `add $100000, counter`, so the race window all but
// vanishes and the program often prints the "right" answer anyway.
//
// The tools are all opt-in, as in Go and Java:
//   std::mutex / std::lock_guard   correct
//   std::atomic<long>              correct
//   -fsanitize=thread              ThreadSanitizer - C++'s equivalent of `go -race`
#include <atomic>
#include <cstdio>
#include <mutex>
#include <thread>
#include <vector>

static const int THREADS = 8;
static const int INCREMENTS = 100000;

static long unsafe_counter = 0;
static long guarded_counter = 0;
static std::atomic<long> atomic_counter{0};
static std::mutex mu;

template <typename F>
static void spawn_and_join(F body) {
    std::vector<std::thread> ts;
    for (int i = 0; i < THREADS; i++) {
        ts.emplace_back(body);
    }
    for (auto& t : ts) {
        t.join();
    }
}

int main() {
    const long expected = static_cast<long>(THREADS) * INCREMENTS;

    spawn_and_join([] {
        for (int i = 0; i < INCREMENTS; i++) unsafe_counter++;                 // UB: data race
    });
    spawn_and_join([] {
        for (int i = 0; i < INCREMENTS; i++) {
            std::lock_guard<std::mutex> g(mu);
            guarded_counter++;                                                  // correct
        }
    });
    spawn_and_join([] {
        for (int i = 0; i < INCREMENTS; i++) atomic_counter.fetch_add(1);       // correct
    });

    std::printf("C++    expected      %ld\n", expected);
    std::printf("C++    racy          %ld   (lost %ld)\n", unsafe_counter, expected - unsafe_counter);
    std::printf("C++    mutex         %ld\n", guarded_counter);
    std::printf("C++    atomic        %ld\n", atomic_counter.load());
    return 0;
}
