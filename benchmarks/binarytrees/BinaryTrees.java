// Allocation / GC-bound workload: build and walk many short-lived binary trees.
//
// This is the mirror image of Mandelbrot.java: almost no arithmetic, but
// millions of tiny object allocations with a mix of short-lived garbage and one
// long-lived tree. It is the classic way to expose garbage collector behaviour
// and the true per-object memory overhead of a runtime.
//
// Try running this with different collectors to see the trade-off live:
//   java -XX:+UseSerialGC   BinaryTrees 18
//   java -XX:+UseParallelGC BinaryTrees 18
//   java -XX:+UseG1GC       BinaryTrees 18   (default)
//   java -XX:+UseZGC        BinaryTrees 18
public final class BinaryTrees {
    private static final int MIN_DEPTH = 4;

    private static final class Node {
        final Node l, r;

        Node(Node l, Node r) {
            this.l = l;
            this.r = r;
        }
    }

    static Node make(int depth) {
        if (depth > 0) {
            return new Node(make(depth - 1), make(depth - 1));
        }
        return new Node(null, null);
    }

    static long count(Node n) {
        if (n.l == null) {
            return 1;
        }
        return 1 + count(n.l) + count(n.r);
    }

    public static void main(String[] args) {
        int n = args.length > 0 ? Integer.parseInt(args[0]) : 16;
        int maxDepth = Math.max(MIN_DEPTH + 2, n);

        int stretchDepth = maxDepth + 1;
        System.out.printf("stretch tree of depth %d\t check: %d%n", stretchDepth, count(make(stretchDepth)));

        Node longLived = make(maxDepth);

        for (int depth = MIN_DEPTH; depth <= maxDepth; depth += 2) {
            long iterations = 1L << (maxDepth - depth + MIN_DEPTH);
            long check = 0;
            for (long i = 0; i < iterations; i++) {
                check += count(make(depth));
            }
            System.out.printf("%d\t trees of depth %d\t check: %d%n", iterations, depth, check);
        }

        System.out.printf("long lived tree of depth %d\t check: %d%n", maxDepth, count(longLived));
    }
}
