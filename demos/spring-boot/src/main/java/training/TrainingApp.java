package training;

import java.sql.Connection;
import java.util.LinkedHashMap;
import java.util.Map;
import javax.sql.DataSource;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * A minimal Spring Boot service with three endpoints, each shaped to expose a
 * different bottleneck.
 *
 *   /hello        trivial. Measures pure request overhead.
 *   /io?ms=100    blocks the request thread. This is what 95% of real endpoints
 *                 do: wait on a database, an HTTP call, a queue.
 *   /cpu?n=...    burns CPU on the request thread. The other 5%.
 *   /db           borrows a HikariCP connection and runs one query.
 *   /whoami       reports which THREAD served the request - the fastest way to
 *                 show the room that virtual threads actually switched on.
 *
 * The two knobs the demo turns:
 *
 *   server.tomcat.threads.max=N        how many requests can be IN FLIGHT
 *   spring.threads.virtual.enabled     Spring Boot 3.2+: serve each request on
 *                                      a virtual thread instead of a pooled
 *                                      platform thread
 */
@SpringBootApplication
@RestController
public class TrainingApp {

    private final ObjectProvider<DataSource> dataSource;

    public TrainingApp(ObjectProvider<DataSource> dataSource) {
        this.dataSource = dataSource;
    }

    public static void main(String[] args) {
        SpringApplication.run(TrainingApp.class, args);
    }

    @GetMapping("/hello")
    public Map<String, Object> hello() {
        return Map.of("ok", true);
    }

    /**
     * Blocking I/O, modelled with sleep. This is honest for the question being
     * asked: a platform thread parked in Thread.sleep and a platform thread
     * parked in a socket read are both unavailable to anyone else, and a
     * VIRTUAL thread unmounts from its carrier in both cases too.
     */
    @GetMapping("/io")
    public Map<String, Object> io(@RequestParam(defaultValue = "100") long ms)
            throws InterruptedException {
        Thread.sleep(ms);
        return Map.of("sleptMs", ms, "thread", Thread.currentThread().toString());
    }

    @GetMapping("/cpu")
    public Map<String, Object> cpu(@RequestParam(defaultValue = "200000") int n) {
        double acc = 0;
        for (int i = 1; i <= n; i++) {
            acc += Math.sqrt(i) / (i + 1.0);
        }
        return Map.of("n", n, "acc", acc);
    }

    /** Borrows a pooled connection. Fails fast and loudly if there is no DB. */
    @GetMapping("/db")
    public Map<String, Object> db(@RequestParam(defaultValue = "0") int sleepMs) {
        DataSource ds = dataSource.getIfAvailable();
        if (ds == null) {
            return Map.of("error", "no datasource configured");
        }
        long t0 = System.nanoTime();
        try (Connection c = ds.getConnection()) {
            long acquiredMs = (System.nanoTime() - t0) / 1_000_000;
            try (var st = c.createStatement()) {
                st.execute("SELECT pg_sleep(" + (sleepMs / 1000.0) + ")");
            }
            Map<String, Object> out = new LinkedHashMap<>();
            out.put("connectionWaitMs", acquiredMs);   // <- the number that matters
            out.put("thread", Thread.currentThread().toString());
            return out;
        } catch (Exception e) {
            return Map.of("error", e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    /**
     * "VirtualThread[#123]/runnable@ForkJoinPool-1-worker-3" means virtual
     * threads are on. "Thread[#57,http-nio-8080-exec-7,5,main]" means they are
     * not. Curl this once before and once after flipping the flag; it is the
     * cheapest possible proof.
     */
    @GetMapping("/whoami")
    public Map<String, Object> whoami() {
        Thread t = Thread.currentThread();
        return Map.of(
                "thread", t.toString(),
                "virtual", t.isVirtual(),
                "name", t.getName());
    }
}
