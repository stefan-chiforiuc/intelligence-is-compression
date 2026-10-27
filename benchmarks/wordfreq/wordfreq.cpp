// Mixed real-world workload: read a text file, count words, print the top 10.
//
// This is the closest of the four benchmarks to actual business code: file
// I/O, string slicing, hash map inserts, and a sort. It is dominated by
// *library and runtime quality* rather than raw loop speed.
//
// Teaching note: std::unordered_map is a node-based, chained hash table; it is
// famously not the fastest map you can write. Like Rust's SipHash default, the
// standard library is optimising for generality, not for this benchmark.
#include <algorithm>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <string_view>
#include <unordered_map>
#include <vector>

static bool is_ws(char c) {
    return c == ' ' || c == '\t' || c == '\n' || c == '\r' || c == '\v' || c == '\f';
}

int main(int argc, char** argv) {
    const char* path = argc > 1 ? argv[1] : "data/words.txt";
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        std::fprintf(stderr, "read %s: cannot open\n", path);
        return 1;
    }
    const std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());

    // string_view keys borrow directly from `text` - no per-word allocation.
    std::unordered_map<std::string_view, unsigned> counts;
    counts.reserve(1 << 16);
    const size_t len = text.size();
    size_t i = 0;
    while (i < len) {
        while (i < len && is_ws(text[i])) {
            i++;
        }
        const size_t start = i;
        while (i < len && !is_ws(text[i])) {
            i++;
        }
        if (i > start) {
            counts[std::string_view(text.data() + start, i - start)]++;
        }
    }

    std::vector<std::pair<std::string_view, unsigned>> pairs(counts.begin(), counts.end());
    std::sort(pairs.begin(), pairs.end(), [](const auto& a, const auto& b) {
        if (a.second != b.second) {
            return a.second > b.second;
        }
        return a.first < b.first;
    });

    std::printf("distinct: %zu\n", counts.size());
    for (size_t k = 0; k < 10 && k < pairs.size(); k++) {
        std::printf("%.*s %u\n", static_cast<int>(pairs[k].first.size()), pairs[k].first.data(),
                    pairs[k].second);
    }
    return 0;
}
