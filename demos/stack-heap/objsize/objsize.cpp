// Directly measure the true cost of one object holding two references.
// See objsize.py for the method.
//
// C++ has no per-object header either: `new Node` costs sizeof(Node) rounded up
// to what malloc hands back (glibc: 16-byte chunks with an 8-byte size field
// shared with the previous chunk, so 16 bytes of data costs 32).
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <memory>
#include <string>
#include <vector>

static const size_t N = 1000000;

struct Node {
    Node* l = nullptr;
    Node* r = nullptr;
};

static int64_t rss_bytes() {
    std::ifstream in("/proc/self/status");
    std::string line;
    while (std::getline(in, line)) {
        if (line.rfind("VmRSS:", 0) == 0) {
            return std::stoll(line.substr(6)) * 1024;
        }
    }
    return 0;
}

int main() {
    const int64_t base = rss_bytes();
    std::vector<std::unique_ptr<Node>> keep;
    keep.reserve(N);
    for (size_t i = 0; i < N; i++) {
        keep.push_back(std::make_unique<Node>());
    }
    const int64_t delta = rss_bytes() - base - static_cast<int64_t>(N * sizeof(void*));

    std::printf("C++    %-14s %6.1f bytes/node   (RSS delta %.1f MB for %s nodes)\n",
                "(new Node)", static_cast<double>(delta) / N, delta / 1048576.0, "1,000,000");
    std::printf("       %-14s %6zu bytes        (sizeof(Node) - the data alone)\n", "", sizeof(Node));

    // Keep the vector observable so the allocations cannot be elided.
    if (keep.back() == nullptr) {
        std::puts("unreachable");
    }
    return 0;
}
