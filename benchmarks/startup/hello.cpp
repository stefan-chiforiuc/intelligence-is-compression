// Cold-start workload: do essentially nothing, as fast as possible.
//
// Everything this program measures happens BEFORE your business logic runs:
// process spawn, dynamic linking, runtime initialisation. That fixed cost is
// what you pay on every single serverless invocation and on every pod restart
// during a rolling deploy.
//
// C++ has essentially no runtime to initialise; what is left is the dynamic
// loader pulling in libstdc++/libc, so this sits just above Rust and Go.
#include <cstdio>
#include <cstdlib>

int main(int argc, char** argv) {
    const long n = argc > 1 ? std::atol(argv[1]) : 1;
    std::printf("ready %ld\n", n * 2);
    return 0;
}
