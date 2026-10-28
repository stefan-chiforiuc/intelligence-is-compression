// Allocation-bound workload: build and walk many short-lived binary trees.
//
// This is the mirror image of mandelbrot.cpp. Like Rust, there is no garbage
// collector: every node is freed deterministically when its owner goes out of
// scope (unique_ptr), so the "GC cost" shows up as malloc/free traffic spread
// evenly through the run instead of as pauses.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <memory>

static const int MIN_DEPTH = 4;

struct Node {
    std::unique_ptr<Node> l, r;
};

static std::unique_ptr<Node> make(int depth) {
    auto node = std::make_unique<Node>();
    if (depth > 0) {
        node->l = make(depth - 1);
        node->r = make(depth - 1);
    }
    return node;
}

static uint64_t count(const Node& n) {
    if (!n.l) {
        return 1;
    }
    return 1 + count(*n.l) + count(*n.r);
}

int main(int argc, char** argv) {
    const int n = argc > 1 ? std::atoi(argv[1]) : 16;
    const int max_depth = std::max(MIN_DEPTH + 2, n);

    const int stretch_depth = max_depth + 1;
    std::printf("stretch tree of depth %d\t check: %llu\n", stretch_depth,
                static_cast<unsigned long long>(count(*make(stretch_depth))));

    const auto long_lived = make(max_depth);

    for (int depth = MIN_DEPTH; depth <= max_depth; depth += 2) {
        const uint64_t iterations = 1ULL << (max_depth - depth + MIN_DEPTH);
        uint64_t check = 0;
        for (uint64_t i = 0; i < iterations; i++) {
            check += count(*make(depth));
        }
        std::printf("%llu\t trees of depth %d\t check: %llu\n",
                    static_cast<unsigned long long>(iterations), depth,
                    static_cast<unsigned long long>(check));
    }

    std::printf("long lived tree of depth %d\t check: %llu\n", max_depth,
                static_cast<unsigned long long>(count(*long_lived)));
    return 0;
}
