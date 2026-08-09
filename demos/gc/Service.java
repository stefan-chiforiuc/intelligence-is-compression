// What a garbage collector costs you, measured the way your users feel it.
//
// This simulates a service handling requests. Each "request" allocates a
// realistic amount of short-lived garbage (a few thousand small objects, like
// parsing a JSON body) and does a little work. We time EVERY request and then
// report percentiles.
//
// The average is boring and roughly the same for every collector. The story is
// in p99 and max: that is where GC pauses live, and that is what your SLO is
// written against.
//
// Run it once per collector (demos/gc/run.sh does this for you):
//   java -XX:+UseSerialGC   -Xmx512m -cp build/demos Service
//   java -XX:+UseParallelGC -Xmx512m -cp build/demos Service
//   java -XX:+UseG1GC       -Xmx512m -cp build/demos Service   (default)
//   java -XX:+UseZGC        -Xmx512m -cp build/demos Service
//
// Add -Xlog:gc to watch the collections happen in real time.
import java.util.Arrays;

public final class Service {
    static final int REQUESTS = 200_000;
    static final int OBJECTS_PER_REQUEST = 200;

    // A long-lived cache. Its whole job is to make the GC's life harder: a
    // heap that is ONLY short-lived garbage is the easy case, and real
    // services always have a big pile of live data too.
    static Object[] cache = new Object[100_000];

    static final class Payload {
        final long id;
        final String name;
        Payload next;

        Payload(long id, String name) {
            this.id = id;
            this.name = name;
        }
    }

    public static void main(String[] args) {
        // Populate the long-lived set first, so the collector has real work.
        for (int i = 0; i < cache.length; i++) {
            cache[i] = new Payload(i, "cached-" + i);
        }

        long[] latenciesNs = new long[REQUESTS];
        long sink = 0;

        for (int r = 0; r < REQUESTS; r++) {
            long t0 = System.nanoTime();

            // One "request": build a small object graph, use it, drop it.
            Payload head = null;
            for (int i = 0; i < OBJECTS_PER_REQUEST; i++) {
                Payload p = new Payload(r * 31L + i, "req");
                p.next = head;
                head = p;
            }
            while (head != null) {
                sink += head.id;
                head = head.next;
            }

            // Occasionally promote something into the long-lived set, which is
            // what forces objects to survive into the old generation.
            if ((r & 1023) == 0) {
                cache[r % cache.length] = new Payload(r, "promoted-" + r);
            }

            latenciesNs[r] = System.nanoTime() - t0;
        }

        report(latenciesNs, sink);
    }

    static void report(long[] ns, long sink) {
        long[] sorted = ns.clone();
        Arrays.sort(sorted);
        double total = 0;
        for (long v : ns) total += v;

        System.out.printf("requests    %,d%n", ns.length);
        System.out.printf("mean        %8.1f us%n", total / ns.length / 1000.0);
        System.out.printf("p50         %8.1f us%n", sorted[(int) (ns.length * 0.50)] / 1000.0);
        System.out.printf("p99         %8.1f us%n", sorted[(int) (ns.length * 0.99)] / 1000.0);
        System.out.printf("p99.9       %8.1f us%n", sorted[(int) (ns.length * 0.999)] / 1000.0);
        System.out.printf("max         %8.1f us   <-- the worst pause a user saw%n",
                sorted[ns.length - 1] / 1000.0);
        System.out.printf("p99/p50     %8.1fx  <-- tail amplification%n",
                (double) sorted[(int) (ns.length * 0.99)] / sorted[(int) (ns.length * 0.50)]);
        if (sink == Long.MIN_VALUE) System.out.println("unreachable");
    }
}
