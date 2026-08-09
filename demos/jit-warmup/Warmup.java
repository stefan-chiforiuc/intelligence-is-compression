// JIT warm-up curve, measured from INSIDE one process.
//
// The benchmark suite measures whole processes, so the JVM's startup cost and
// its warm-up cost are tangled together. This demo separates them: the process
// has already booted, and we watch the SAME code get faster as HotSpot's
// tiered compiler promotes it interpreter -> C1 -> C2.
//
// Run it twice to make the point:
//   java  -cp build/demos Warmup          # normal: tiered JIT
//   java -Xint -cp build/demos Warmup     # interpreter only, JIT disabled
//
// Output: one "batch,milliseconds" line per batch, for run.py to chart.
public final class Warmup {
    static final int BATCHES = 60;
    static final int CALLS_PER_BATCH = 200;
    static final int SIZE = 16;
    static final int MAX_ITER = 50;

    // Deliberately a separate method with a modest loop: we want HotSpot's
    // *invocation* counter to drive promotion, not a single long-running loop
    // that gets on-stack-replaced during the very first batch.
    static long kernel(int n) {
        long inside = 0;
        for (int y = 0; y < n; y++) {
            double ci = 2.0 * y / n - 1.0;
            for (int x = 0; x < n; x++) {
                double cr = 2.0 * x / n - 1.5;
                double zr = 0.0, zi = 0.0;
                int i = 0;
                while (i < MAX_ITER && zr * zr + zi * zi <= 4.0) {
                    double t = zr * zr - zi * zi + cr;
                    zi = 2.0 * zr * zi + ci;
                    zr = t;
                    i++;
                }
                if (i == MAX_ITER) inside++;
            }
        }
        return inside;
    }

    public static void main(String[] args) {
        long sink = 0;
        for (int b = 0; b < BATCHES; b++) {
            long t0 = System.nanoTime();
            for (int c = 0; c < CALLS_PER_BATCH; c++) {
                sink += kernel(SIZE);
            }
            double ms = (System.nanoTime() - t0) / 1_000_000.0;
            System.out.printf("%d,%.3f%n", b, ms);
        }
        // Keep `sink` observable so nothing can be optimised away entirely.
        if (sink == Long.MIN_VALUE) System.out.println("unreachable");
    }
}
