// Parallel Mandelbrot in Java: platform threads via an ExecutorService.
//
//   java -cp build/demos/concurrency ParallelMandelbrot <n> <workers>
//
// A NOTE ON VIRTUAL THREADS (JDK 21), because juniors will ask:
// virtual threads do NOT make this faster. They are a fix for BLOCKING I/O
// concurrency — they let you write "one thread per request" against a database
// or an HTTP call without exhausting OS threads. For CPU-bound work like this,
// the bottleneck is cores, not threads, and you want exactly as many threads as
// you have cores. Using 10,000 virtual threads here would be slower, not faster.
//
// That distinction — CONCURRENCY (dealing with many things at once) vs
// PARALLELISM (doing many things at once) — is the thing to take away from
// this whole block.
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public final class ParallelMandelbrot {
    static final int MAX_ITER = 50;

    static long band(int n, int y0, int y1) {
        long inside = 0;
        double fn = n;
        for (int y = y0; y < y1; y++) {
            double ci = 2.0 * y / fn - 1.0;
            for (int x = 0; x < n; x++) {
                double cr = 2.0 * x / fn - 1.5;
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

    public static void main(String[] args) throws Exception {
        int n = args.length > 0 ? Integer.parseInt(args[0]) : 1000;
        int workers = args.length > 1 ? Integer.parseInt(args[1]) : 1;

        int step = (n + workers - 1) / workers;
        List<Callable<Long>> tasks = new ArrayList<>();
        for (int w = 0; w < workers; w++) {
            final int y0 = w * step;
            final int y1 = Math.min(y0 + step, n);
            if (y0 >= n) continue;
            tasks.add(() -> band(n, y0, y1));
        }

        long t0 = System.nanoTime();
        long total = 0;
        try (ExecutorService pool = Executors.newFixedThreadPool(workers)) {
            List<Future<Long>> futures = pool.invokeAll(tasks);
            for (Future<Long> f : futures) {
                total += f.get();
            }
        }
        double ms = (System.nanoTime() - t0) / 1e6;

        System.out.printf("inside=%d workers=%d ms=%.1f%n", total, workers, ms);
    }
}
