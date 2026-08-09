// Java: the same race, on a platform that has had a memory model since 2004.
//
//   java -cp build/demos/concurrency Race
//
// `counter++` compiles to getfield / iadd / putfield — three bytecodes, not one.
// Two threads interleave and increments are lost.
//
// Java gives you more tools than Go here (synchronized, volatile, Atomic*,
// java.util.concurrent, and a genuinely specified memory model in JSR-133), but
// it gives you no compile-time protection either. Every one of these is opt-in
// and easy to forget.
//
// Note the third case: `volatile` is NOT enough. Juniors reach for it constantly
// because it sounds like "make this thread-safe". It guarantees VISIBILITY (you
// will see other threads' writes) but not ATOMICITY (read-modify-write is still
// three steps). A volatile counter still loses increments — demonstrating that
// is worth more than any amount of explanation.
import java.util.concurrent.atomic.AtomicLong;

public final class Race {
    static final int THREADS = 8;
    static final int INCREMENTS = 100_000;

    static long unsafeCounter = 0;
    static volatile long volatileCounter = 0;
    static long guardedCounter = 0;
    static final AtomicLong atomicCounter = new AtomicLong();
    static final Object lock = new Object();

    static void spawnAndJoin(Runnable body) throws InterruptedException {
        Thread[] ts = new Thread[THREADS];
        for (int i = 0; i < THREADS; i++) {
            ts[i] = new Thread(body);
            ts[i].start();
        }
        for (Thread t : ts) t.join();
    }

    public static void main(String[] args) throws InterruptedException {
        long expected = (long) THREADS * INCREMENTS;

        spawnAndJoin(() -> {
            for (int i = 0; i < INCREMENTS; i++) unsafeCounter++;       // race
        });

        spawnAndJoin(() -> {
            for (int i = 0; i < INCREMENTS; i++) volatileCounter++;     // STILL a race
        });

        spawnAndJoin(() -> {
            for (int i = 0; i < INCREMENTS; i++) {
                synchronized (lock) { guardedCounter++; }               // correct
            }
        });

        spawnAndJoin(() -> {
            for (int i = 0; i < INCREMENTS; i++) atomicCounter.incrementAndGet(); // correct
        });

        System.out.printf("Java   expected      %d%n", expected);
        System.out.printf("Java   racy          %d   (lost %d)%n", unsafeCounter, expected - unsafeCounter);
        System.out.printf("Java   volatile      %d   (lost %d - volatile is NOT atomic)%n",
                volatileCounter, expected - volatileCounter);
        System.out.printf("Java   synchronized  %d%n", guardedCounter);
        System.out.printf("Java   AtomicLong    %d%n", atomicCounter.get());
    }
}
