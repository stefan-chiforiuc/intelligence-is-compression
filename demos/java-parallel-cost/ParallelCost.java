// When SHOULD you parallelise? Not whenever you can.
//
//   java -cp build/demos/parcost ParallelCost
//
// `list.parallelStream()` is one word longer than `list.stream()`. That is the
// problem: the cost is invisible at the call site, so people add it everywhere
// and make their code slower.
//
// Parallelism is not free. Before any of your work happens you pay for:
//   * splitting the source into chunks (cheap for arrays, EXPENSIVE for
//     LinkedList, and impossible to do well for a HashMap or an Iterator)
//   * handing tasks to the ForkJoinPool and waking its worker threads
//   * memory barriers and cache-line traffic between cores
//   * combining the partial results
//   * the slowest chunk deciding when you finish (stragglers)
//
// That fixed cost is roughly constant. Your work is proportional to N. So there
// is always a CROSSOVER: below it, parallel is slower; above it, faster. This
// program finds that crossover empirically instead of guessing.
import java.util.concurrent.ForkJoinPool;
import java.util.stream.LongStream;

public final class ParallelCost {

    // --- two workloads with very different cost-per-element -----------------

    /** Cheap: one multiply-add. Memory bandwidth, not CPU, is the limit. */
    static long cheap(long x) {
        return x * 2 + 1;
    }

    /** Expensive: ~50 iterations of float math per element. */
    static long expensive(long x) {
        double zr = 0, zi = 0;
        double cr = (x % 1000) / 500.0 - 1.5, ci = (x % 997) / 500.0 - 1.0;
        int i = 0;
        while (i < 50 && zr * zr + zi * zi <= 4.0) {
            double t = zr * zr - zi * zi + cr;
            zi = 2 * zr * zi + ci;
            zr = t;
            i++;
        }
        return i;
    }

    static long seqCheap(long n)  { return LongStream.range(0, n).map(ParallelCost::cheap).sum(); }
    static long parCheap(long n)  { return LongStream.range(0, n).parallel().map(ParallelCost::cheap).sum(); }
    static long seqExp(long n)    { return LongStream.range(0, n).map(ParallelCost::expensive).sum(); }
    static long parExp(long n)    { return LongStream.range(0, n).parallel().map(ParallelCost::expensive).sum(); }

    interface Job { long run(long n); }

    /** Median of `reps` runs, after a warm-up run to let the JIT settle. */
    static double timeMs(Job job, long n, int reps) {
        job.run(n);                                   // warm up
        double[] times = new double[reps];
        for (int r = 0; r < reps; r++) {
            long t0 = System.nanoTime();
            long sink = job.run(n);
            times[r] = (System.nanoTime() - t0) / 1e6;
            if (sink == Long.MIN_VALUE) System.out.print("");
        }
        java.util.Arrays.sort(times);
        return times[reps / 2];
    }

    static void sweep(String title, Job seq, Job par, long[] sizes, int reps) {
        System.out.println();
        System.out.println(title);
        System.out.printf("  %12s %14s %14s %12s   %s%n",
                "elements", "sequential", "parallel", "speedup", "verdict");
        System.out.println("  " + "-".repeat(72));
        for (long n : sizes) {
            double s = timeMs(seq, n, reps);
            double p = timeMs(par, n, reps);
            double ratio = s / p;
            String verdict = ratio > 1.15 ? "parallel wins"
                           : ratio < 0.85 ? "parallel LOSES"
                           : "no real difference";
            System.out.printf("  %,12d %11.3f ms %11.3f ms %11.2fx   %s%n", n, s, p, ratio, verdict);
        }
    }

    public static void main(String[] args) {
        System.out.println("Cores available to the JVM : " + Runtime.getRuntime().availableProcessors());
        System.out.println("ForkJoinPool.commonPool()  : " + ForkJoinPool.commonPool().getParallelism()
                + " worker threads (= cores - 1; the caller thread helps too)");

        sweep("WORKLOAD A - cheap per element (one multiply-add)",
                ParallelCost::seqCheap, ParallelCost::parCheap,
                new long[]{1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000}, 5);

        sweep("WORKLOAD B - expensive per element (~50 float iterations)",
                ParallelCost::seqExp, ParallelCost::parExp,
                new long[]{100, 1_000, 10_000, 100_000, 1_000_000}, 5);

        System.out.println("""

                READ THE TWO TABLES TOGETHER
                ============================
                The crossover is NOT at a fixed element count. It is at a fixed amount
                of TOTAL WORK. Workload B crosses over at far fewer elements than A,
                because each element is worth more.

                The rule of thumb worth memorising:

                    N x (cost per element)  must be >> ~100 microseconds of setup

                If you cannot say roughly how long your operation takes, you cannot
                say whether to parallelise it. Measure, do not guess - which is the
                entire point of this session.""");
    }
}
