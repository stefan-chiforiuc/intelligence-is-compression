// Virtual threads (JDK 21): what they fix, and what they do not.
//
//   java -cp build/demos/parcost VirtualThreads
//
// The one-sentence version, which juniors should leave able to recite:
//
//   Virtual threads make BLOCKING cheap. They do not make COMPUTING faster.
//
// A platform thread is an OS thread: ~1 MB of reserved stack, created by a
// syscall, scheduled by the kernel. Blocking one wastes an expensive resource,
// which is why we invented thread pools, and then callbacks, and then reactive
// streams, and then async/await - an entire generation of complexity that
// exists only because threads were scarce.
//
// A virtual thread is a Java object, ~1 KB, scheduled by the JVM onto a small
// pool of carrier threads. When it blocks, the JVM UNMOUNTS it from its carrier
// and runs something else. Blocking is now cheap, so "one thread per request"
// becomes correct again and all that complexity becomes unnecessary.
//
// But the carrier pool still has exactly as many threads as you have cores. For
// CPU-bound work, nothing changed. You cannot conjure cores out of objects.
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;

public final class VirtualThreads {

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

    static long cpuTask() {
        long acc = 0;
        for (long i = 0; i < 200_000; i++) acc += expensive(i);
        return acc;
    }

    /** Thread.sleep is an honest model of blocking I/O here: a virtual thread
     *  unmounts from its carrier for sleep exactly as it does for a socket
     *  read. It is the same mechanism, without needing a database. */
    static void ioTask() throws InterruptedException {
        Thread.sleep(Duration.ofMillis(50));
    }

    static double runAll(ExecutorService pool, List<Runnable> tasks) throws Exception {
        long t0 = System.nanoTime();
        List<Future<?>> futures = new ArrayList<>();
        for (Runnable t : tasks) futures.add(pool.submit(t));
        for (Future<?> f : futures) f.get();
        pool.shutdown();
        return (System.nanoTime() - t0) / 1e6;
    }

    static long rssMb() {
        try {
            for (String line : java.nio.file.Files.readAllLines(java.nio.file.Path.of("/proc/self/status"))) {
                if (line.startsWith("VmRSS:")) return Long.parseLong(line.replaceAll("[^0-9]", "")) / 1024;
            }
        } catch (Exception ignored) { }
        return -1;
    }

    public static void main(String[] args) throws Exception {
        int cores = Runtime.getRuntime().availableProcessors();
        System.out.println("Cores: " + cores);

        // ------------------------------------------------------------------
        System.out.println("""

                EXPERIMENT 1 - CPU-BOUND WORK
                =============================
                8 tasks, each doing real arithmetic. Does going from 4 platform
                threads to 1000 virtual threads help?""");

        List<Runnable> cpuTasks = new ArrayList<>();
        for (int i = 0; i < 8; i++) cpuTasks.add(() -> { if (cpuTask() == Long.MIN_VALUE) System.out.print(""); });

        // Warm the JIT on BOTH paths before timing either. Without this, the
        // second executor measured looks artificially fast because the first
        // one already got cpuTask() compiled - a mistake worth admitting to the
        // room if anyone asks why the code looks redundant.
        for (int i = 0; i < 2; i++) {
            runAll(Executors.newFixedThreadPool(cores), cpuTasks);
            runAll(Executors.newVirtualThreadPerTaskExecutor(), cpuTasks);
        }

        // Best of two, alternating, to blunt scheduler noise.
        double cpuPlatform = Math.min(runAll(Executors.newFixedThreadPool(cores), cpuTasks),
                                      runAll(Executors.newFixedThreadPool(cores), cpuTasks));
        double cpuVirtual  = Math.min(runAll(Executors.newVirtualThreadPerTaskExecutor(), cpuTasks),
                                      runAll(Executors.newVirtualThreadPerTaskExecutor(), cpuTasks));

        System.out.printf("  platform pool (%d threads) : %8.1f ms%n", cores, cpuPlatform);
        System.out.printf("  virtual thread per task    : %8.1f ms%n", cpuVirtual);
        System.out.printf("  -> virtual is %.2fx the platform time. %s%n",
                cpuVirtual / cpuPlatform,
                cpuVirtual > cpuPlatform * 1.05
                        ? "SLOWER - you added scheduling for nothing."
                        : "No meaningful gain: same cores, same work.");

        // ------------------------------------------------------------------
        System.out.println("""

                EXPERIMENT 2 - BLOCKING I/O
                ===========================
                10,000 tasks, each blocking for 50 ms (a database call).
                Perfect concurrency would finish in ~50 ms total.""");

        int ioCount = 10_000;
        List<Runnable> ioTasks = new ArrayList<>();
        for (int i = 0; i < ioCount; i++) {
            ioTasks.add(() -> {
                try { ioTask(); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
            });
        }

        double io200 = runAll(Executors.newFixedThreadPool(200), ioTasks);
        double ioVirtual = runAll(Executors.newVirtualThreadPerTaskExecutor(), ioTasks);

        System.out.printf("  platform pool (200 threads): %8.1f ms   (%d tasks / 200 at a time x 50 ms)%n",
                io200, ioCount);
        System.out.printf("  virtual thread per task    : %8.1f ms%n", ioVirtual);
        System.out.printf("  -> virtual is %.1fx FASTER. This is what virtual threads are for.%n",
                io200 / ioVirtual);

        // ------------------------------------------------------------------
        System.out.println("""

                EXPERIMENT 3 - WHAT DOES A THREAD COST?
                =======================================""");

        long rssBefore = rssMb();
        long t0 = System.nanoTime();
        List<Thread> virtuals = new ArrayList<>();
        for (int i = 0; i < 100_000; i++) {
            Thread t = Thread.ofVirtual().start(() -> {
                try { Thread.sleep(Duration.ofMillis(200)); } catch (InterruptedException ignored) { }
            });
            virtuals.add(t);
        }
        double vCreate = (System.nanoTime() - t0) / 1e6;
        long rssAfter = rssMb();
        for (Thread t : virtuals) t.join();

        System.out.printf("  100,000 virtual threads created in %.0f ms, RSS +%d MB%n",
                vCreate, Math.max(0, rssAfter - rssBefore));

        t0 = System.nanoTime();
        List<Thread> platforms = new ArrayList<>();
        int platformCount = 2_000;   // deliberately modest: 100k would exhaust the machine
        for (int i = 0; i < platformCount; i++) {
            Thread t = Thread.ofPlatform().start(() -> {
                try { Thread.sleep(Duration.ofMillis(200)); } catch (InterruptedException ignored) { }
            });
            platforms.add(t);
        }
        double pCreate = (System.nanoTime() - t0) / 1e6;
        for (Thread t : platforms) t.join();

        System.out.printf("  %,d platform threads created in %.0f ms  (%.1f us each)%n",
                platformCount, pCreate, pCreate * 1000 / platformCount);
        System.out.printf("  -> at that rate, 100,000 platform threads would take ~%.1f s%n",
                pCreate / platformCount * 100_000 / 1000);
        System.out.println("     ...and roughly 100 GB of reserved stack. They would not fit.");

        System.out.println("""

                WHEN TO USE WHAT
                ================

                  CPU-bound work        -> a fixed pool sized to your CORES.
                                           Virtual threads add scheduling, not cores.

                  Blocking I/O          -> virtual threads, one per task.
                                           This is the whole reason they exist.

                  Mixed                 -> two pools. Do not run CPU work on the
                                           pool that serves requests.

                THREE TRAPS WORTH NAMING

                1. parallelStream() uses the SHARED ForkJoinPool.commonPool().
                   One blocking parallelStream anywhere in your JVM stalls every
                   other parallelStream in the process. Never do I/O inside one.

                2. Virtual threads do not increase your DATABASE's capacity. If
                   10,000 virtual threads all reach for a 10-connection pool, you
                   have moved the queue, not removed it - and you can now
                   overwhelm the database far more easily than before. See the
                   database block.

                3. On JDK 21, a virtual thread blocking inside `synchronized`
                   PINS its carrier thread and cannot unmount - which can
                   deadlock a small carrier pool. Use ReentrantLock instead.
                   (Fixed in later JDKs; know which one you are on.)""");
    }
}
