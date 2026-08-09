// A real HTTP API. 20 users. One shared array. Five ways it can go.
//
//   java -cp build/demos/apirace ApiRace
//
// Everything here is JDK-only: com.sun.net.httpserver for the server,
// java.net.http.HttpClient for the load, virtual threads for the 20 users.
// No Spring, no Tomcat, no dependencies - so the race is visibly OURS and not
// something a framework did.
//
// Each endpoint appends one item to a shared list per request. Twenty
// concurrent clients each send the same number of requests, so the final size
// is arithmetic: clients x requests. Anything less is a lost update.
//
// This is the single most common concurrency bug in real web services, and it
// looks exactly like ordinary code:
//
//     private final List<String> items = new ArrayList<>();     // a field
//     ...
//     items.add(payload);                                       // in a handler
//
// A controller field is shared by every request thread. `ArrayList` is not
// thread-safe. That is the whole bug.
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Queue;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicInteger;

public final class ApiRace {

    static int USERS = 20;
    static int REQUESTS_PER_USER = 50;
    // Each request appends a BATCH. This is a realistic endpoint shape
    // ("POST /items" with an array in the body), and it is what makes the race
    // observable: with one append per request the HTTP round-trip dominates and
    // the threads rarely overlap inside ArrayList.add at all.
    static int ITEMS_PER_REQUEST = 200;
    static int EXPECTED = USERS * REQUESTS_PER_USER * ITEMS_PER_REQUEST;

    // --- the five shared collections ------------------------------------------
    static final List<String> unsafeList = new ArrayList<>();
    static final List<String> syncBlockList = new ArrayList<>();
    static final List<String> synchronizedList = Collections.synchronizedList(new ArrayList<>());
    static final List<String> copyOnWrite = new CopyOnWriteArrayList<>();
    static final Queue<String> concurrentQueue = new ConcurrentLinkedQueue<>();

    static final Object lock = new Object();
    static final AtomicInteger exceptions = new AtomicInteger();

    record Result(String name, int size, long ms, int errors, String note) { }

    public static void main(String[] args) throws Exception {
        if (args.length > 0) USERS = Integer.parseInt(args[0]);
        if (args.length > 1) REQUESTS_PER_USER = Integer.parseInt(args[1]);
        if (args.length > 2) ITEMS_PER_REQUEST = Integer.parseInt(args[2]);
        EXPECTED = USERS * REQUESTS_PER_USER * ITEMS_PER_REQUEST;

        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        // Without an executor, HttpServer handles requests on ONE thread and no
        // race is possible. A real server is multi-threaded, so we make this one
        // multi-threaded too.
        ExecutorService serverPool = Executors.newFixedThreadPool(16);
        server.setExecutor(serverPool);

        server.createContext("/unsafe", ex -> {
            // THE BUG. ArrayList.add is three steps: check capacity, write to
            // elementData[size], increment size. Two threads interleave and one
            // write is lost - or, if a resize happens mid-add, it throws.
            String v = body(ex);
            for (int i = 0; i < ITEMS_PER_REQUEST; i++) {
                try {
                    unsafeList.add(v + i);
                } catch (RuntimeException e) {
                    // ArrayIndexOutOfBounds / NPE from a torn resize.
                    exceptions.incrementAndGet();
                }
            }
            respond(ex);
        });

        server.createContext("/syncblock", ex -> {
            String v = body(ex);
            for (int i = 0; i < ITEMS_PER_REQUEST; i++) {
                synchronized (lock) {          // manual synchronisation
                    syncBlockList.add(v + i);
                }
            }
            respond(ex);
        });

        server.createContext("/synclist", ex -> {
            String vsynchronizedList = body(ex);
            for (int i = 0; i < ITEMS_PER_REQUEST; i++) synchronizedList.add(vsynchronizedList + i);    // Collections.synchronizedList
            respond(ex);
        });

        server.createContext("/cow", ex -> {
            String vcopyOnWrite = body(ex);
            for (int i = 0; i < ITEMS_PER_REQUEST; i++) copyOnWrite.add(vcopyOnWrite + i);         // CopyOnWriteArrayList
            respond(ex);
        });

        server.createContext("/queue", ex -> {
            String vconcurrentQueue = body(ex);
            for (int i = 0; i < ITEMS_PER_REQUEST; i++) concurrentQueue.add(vconcurrentQueue + i);     // ConcurrentLinkedQueue (lock-free)
            respond(ex);
        });

        server.start();
        int port = server.getAddress().getPort();
        System.out.printf("Server on port %d%n", port);
        System.out.printf("%d users x %d requests x %d items per request = %,d expected items%n%n",
                USERS, REQUESTS_PER_USER, ITEMS_PER_REQUEST, EXPECTED);

        List<Result> results = new ArrayList<>();
        results.add(hammer(port, "/unsafe",    "ArrayList (no sync)",        () -> unsafeList.size()));
        results.add(hammer(port, "/syncblock", "ArrayList + synchronized",   () -> syncBlockList.size()));
        results.add(hammer(port, "/synclist",  "Collections.synchronizedList", () -> synchronizedList.size()));
        results.add(hammer(port, "/cow",       "CopyOnWriteArrayList",       () -> copyOnWrite.size()));
        results.add(hammer(port, "/queue",     "ConcurrentLinkedQueue",      () -> concurrentQueue.size()));

        server.stop(0);
        serverPool.shutdownNow();   // these are NON-DAEMON threads: without this
                                    // the JVM hangs after main() returns.
        report(results);
        System.exit(0);
    }

    interface SizeFn { int size(); }

    static Result hammer(int port, String path, String name, SizeFn size) throws Exception {
        exceptions.set(0);
        ExecutorService clientPool = Executors.newVirtualThreadPerTaskExecutor();
        HttpClient client = HttpClient.newBuilder()
                .version(HttpClient.Version.HTTP_1_1)
                .executor(clientPool)
                .build();

        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(USERS);
        ExecutorService users = Executors.newVirtualThreadPerTaskExecutor();

        long[] elapsed = new long[1];
        for (int u = 0; u < USERS; u++) {
            final int id = u;
            users.submit(() -> {
                try {
                    start.await();                       // all 20 released at once
                    for (int r = 0; r < REQUESTS_PER_USER; r++) {
                        HttpRequest req = HttpRequest.newBuilder()
                                .uri(URI.create("http://localhost:" + port + path))
                                .POST(HttpRequest.BodyPublishers.ofString("user-" + id + "-item-" + r))
                                .build();
                        client.send(req, HttpResponse.BodyHandlers.discarding());
                    }
                } catch (Exception e) {
                    exceptions.incrementAndGet();
                } finally {
                    done.countDown();
                }
            });
        }

        long t0 = System.nanoTime();
        start.countDown();
        done.await();
        elapsed[0] = System.nanoTime() - t0;
        users.shutdown();
        clientPool.shutdownNow();
        client.close();

        int actual = size.size();
        int lost = EXPECTED - actual;
        String note = lost == 0 ? "correct" : "LOST " + lost + " items";
        return new Result(name, actual, elapsed[0] / 1_000_000, exceptions.get(), note);
    }

    static String body(com.sun.net.httpserver.HttpExchange ex) throws IOException {
        return new String(ex.getRequestBody().readAllBytes());
    }

    static void respond(com.sun.net.httpserver.HttpExchange ex) throws IOException {
        ex.sendResponseHeaders(204, -1);   // -1 = no response body
        ex.close();
    }

    static void report(List<Result> results) {
        System.out.printf("%-32s %10s %10s %9s %8s   %s%n",
                "Implementation", "expected", "actual", "errors", "ms", "verdict");
        System.out.println("-".repeat(92));
        for (Result r : results) {
            System.out.printf("%-32s %10d %10d %9d %8d   %s%n",
                    r.name(), EXPECTED, r.size(), r.errors(), r.ms(), r.note());
        }

        System.out.println("""

                WHAT JUST HAPPENED
                ==================

                /unsafe - ArrayList.add() is not one operation:
                    if (size + 1 > elementData.length) grow();
                    elementData[size] = element;
                    size = size + 1;
                Two request threads read the same `size`, both write to that slot,
                both store size+1. One item is silently overwritten.

                Lost items are the reliable symptom. The errors column may also be
                non-zero: if a resize happens while another thread is mid-write you
                get an ArrayIndexOutOfBoundsException or a null hole. That one is
                timing-dependent, so do not promise the room it will appear - if it
                does, point at it; if it does not, say that a bug you cannot
                reproduce on demand is exactly the problem.

                Nothing crashed the server. The API returned 204 to every caller.
                Every one of those users believes their item was saved.

                THE THREE FIXES ARE NOT EQUIVALENT
                ==================================

                synchronized block      you hold the lock; correct as long as EVERY
                                        access is inside it. Miss one read and it is
                                        broken again, silently. Correctness by
                                        discipline.

                synchronizedList        the same lock, applied for you on each method.
                                        BUT compound operations are still unsafe:
                                            if (!list.contains(x)) list.add(x);
                                        is two safe calls and one race.

                CopyOnWriteArrayList    copies the WHOLE backing array on EVERY write.
                                        Thread-safe and O(n) per write, so appending n
                                        items is O(n^2). Look at its ms column: it is
                                        roughly 100x slower than the queue here, and it
                                        is the only run in this demo you have time to
                                        get a coffee during. Correct for read-mostly
                                        data (listener lists, cached config); a
                                        catastrophe on a write-heavy endpoint.
                                        "Thread-safe" told you nothing about cost.

                ConcurrentLinkedQueue   lock-free, designed for exactly this. Usually
                                        the right answer when you only append.

                "Thread-safe" is not one property. Ask thread-safe FOR WHAT ACCESS
                PATTERN, and at what cost.""");
    }
}
