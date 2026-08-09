// Directly measure the true cost of one object holding two references.
// See objsize.py for the method.
//
// Java gets two numbers because they answer different questions:
//   * heap delta = what the object graph costs inside the JVM heap
//   * RSS delta  = what your Kubernetes memory limit actually has to allow for
// The second is always bigger, and the second is the one on your cloud bill.
//
// Run with a fixed heap so the numbers are reproducible:
//   java -Xms512m -Xmx512m -cp build/demos ObjSize
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

public final class ObjSize {
    static final int N = 1_000_000;

    static final class Node {
        Node l, r;
    }

    static long rssBytes() {
        try {
            for (String line : Files.readAllLines(Path.of("/proc/self/status"))) {
                if (line.startsWith("VmRSS:")) {
                    return Long.parseLong(line.replaceAll("[^0-9]", "")) * 1024;
                }
            }
        } catch (IOException | NumberFormatException ignored) {
        }
        return 0;
    }

    static long usedHeap() {
        Runtime rt = Runtime.getRuntime();
        return rt.totalMemory() - rt.freeMemory();
    }

    public static void main(String[] args) throws Exception {
        // Settle the heap before taking a baseline.
        System.gc();
        Thread.sleep(100);
        long baseRss = rssBytes();
        long baseHeap = usedHeap();

        Node[] keep = new Node[N];
        for (int i = 0; i < N; i++) {
            keep[i] = new Node();
        }

        long heapDelta = usedHeap() - baseHeap - (long) N * 4; // minus the array of refs
        long rssDelta = rssBytes() - baseRss - (long) N * 4;

        System.out.printf("Java   %-14s %6.1f bytes/node   (heap delta %.1f MB for %,d nodes)%n",
                "(heap)", (double) heapDelta / N, heapDelta / 1048576.0, N);
        System.out.printf("       %-14s %6.1f bytes/node   (RSS  delta %.1f MB - what the pod pays)%n",
                "(RSS)", (double) rssDelta / N, rssDelta / 1048576.0);

        if (keep[N - 1] == null && keep[0] != null) {
            System.out.println("unreachable");
        }
    }
}
