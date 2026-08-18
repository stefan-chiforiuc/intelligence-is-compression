// The centerpiece claim of this block: a Spring bean built with constructor
// injection and no other mutable state IS a function, in the formal sense —
// and that is exactly why Spring is comfortable handing the SAME instance to
// every concurrent request thread as a singleton, no synchronization needed.
//
// This file has no Spring dependency (the demo build stays a one-file javac,
// like every other file here) — the annotations are written as comments so
// you can see exactly which real Spring annotation each shape corresponds to.
// The mechanism is not framework magic; it is just "does this object have a
// mutable field", the same question Block 4 (demos/concurrency) asks about
// any shared object.
//
//   javac -d build/demos/style demos/programming-style/SpringBeanStyle.java
//   java -cp build/demos/style SpringBeanStyle
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

public final class SpringBeanStyle {

    // ---- "FUNCTIONAL" BEAN --------------------------------------------
    // @Service
    // class TaxRule { ... }
    // Injected by constructor, stored in a `final` field: an immutable,
    // pure collaborator with no state of its own.
    static final class TaxRule {
        private final double rate;
        TaxRule(double rate) { this.rate = rate; }     // constructor injection
        double apply(double amount) { return amount * rate; }   // pure
    }

    // @Service                                  <- default scope: SINGLETON
    // class PricingService {
    //     private final TaxRule taxRule;         <- @Autowired via constructor
    //     PricingService(TaxRule taxRule) { this.taxRule = taxRule; }
    //     double price(double amount) { ... }     <- a REST controller calls this
    // }
    static final class PricingService {
        private final TaxRule taxRule;                  // final: set once, never reassigned
        PricingService(TaxRule taxRule) { this.taxRule = taxRule; }

        // price(amount) depends ONLY on `amount` and on `taxRule`, which is
        // itself immutable. Every call, from every thread, computes forward
        // from its arguments and touches nothing any other call could have
        // left behind. That is a pure function wearing a class as a costume.
        double price(double amount) {
            return amount + taxRule.apply(amount);
        }
    }

    // ---- THE SAME BEAN, WITH ONE MUTABLE FIELD ADDED -------------------
    // The moment you add ANY field that a method writes to, you have smuggled
    // OOP-style shared mutable state into an object the container still hands
    // out as ONE shared instance to every concurrent request thread. Spring
    // never warns you — dependency injection manages WIRING, not statefulness.
    static final class StatefulPricingService {
        private final TaxRule taxRule;
        private int requestsServed = 0;          // <-- this one field breaks the property

        StatefulPricingService(TaxRule taxRule) { this.taxRule = taxRule; }

        double price(double amount) {
            requestsServed++;                      // read-modify-write on shared state
            return amount + taxRule.apply(amount);
        }

        int requestsServed() { return requestsServed; }
    }

    public static void main(String[] args) throws InterruptedException {
        TaxRule vat = new TaxRule(0.19);

        System.out.println("PURE BEAN — constructor injection, no other state");
        PricingService pricing = new PricingService(vat);
        System.out.println("  price(100.0) called 3 times: "
                + pricing.price(100.0) + ", " + pricing.price(100.0) + ", " + pricing.price(100.0));
        System.out.println("  Identical input -> identical output, every time, regardless of what");
        System.out.println("  else has called price() on this SAME shared singleton in the meantime.");
        System.out.println("  That is the entire reason Spring can default beans to singleton scope:");
        System.out.println("  sharing a pure object across every request thread costs nothing, because");
        System.out.println("  there is no state to race on.");

        System.out.println();
        System.out.println("STATEFUL BEAN — same shape, one mutable field added");
        StatefulPricingService stateful = new StatefulPricingService(vat);
        int threads = 8, callsPerThread = 100_000;
        Thread[] pool = new Thread[threads];
        for (int t = 0; t < threads; t++) {
            pool[t] = new Thread(() -> {
                for (int i = 0; i < callsPerThread; i++) stateful.price(100.0);
            });
        }
        for (Thread th : pool) th.start();
        for (Thread th : pool) th.join();
        int expected = threads * callsPerThread;
        System.out.println("  " + threads + " request threads x " + callsPerThread + " calls each"
                + " on the ONE shared singleton bean:");
        System.out.println("  expected requestsServed = " + expected);
        System.out.println("  actual   requestsServed = " + stateful.requestsServed()
                + (stateful.requestsServed() == expected ? "  (got lucky this run)" : "  <- LOST UPDATES"));
        System.out.println("  Nothing threw. Nothing logged. The counter is just quietly wrong — the");
        System.out.println("  identical bug as the ArrayList in docs/09-when-to-parallelize.md, Part 3,");
        System.out.println("  except this time the shared mutable field is one line inside a @Service");
        System.out.println("  nobody thought of as 'concurrent code' because it never mentions a thread.");

        System.out.println();
        System.out.println("THE FIX IS THE SAME FIX AS BLOCK 4: put the strategy in the type.");
        AtomicInteger safeCounter = new AtomicInteger();
        Thread[] pool2 = new Thread[threads];
        for (int t = 0; t < threads; t++) {
            pool2[t] = new Thread(() -> { for (int i = 0; i < callsPerThread; i++) safeCounter.incrementAndGet(); });
        }
        for (Thread th : pool2) th.start();
        for (Thread th : pool2) th.join();
        System.out.println("  AtomicInteger instead of int requestsServed: " + safeCounter.get()
                + "   (always exactly " + expected + ")");
        System.out.println("  But the honest recommendation is not 'use AtomicInteger' — it is 'ask");
        System.out.println("  whether this bean needs the field at all'. A request counter belongs in");
        System.out.println("  a metrics registry (Micrometer), not in the same object that computes");
        System.out.println("  prices. Keep the pure decision logic pure; put anything stateful behind");
        System.out.println("  an interface built for concurrent state (see demos/concurrency).");

        System.out.println();
        System.out.println(List.of(
                "SUMMARY",
                "  final fields only, no writes after the constructor  -> behaves like a function",
                "  any field a method mutates                          -> behaves like shared state",
                "  Spring's container cannot see the difference. You have to."
        ).stream().reduce("", (acc, line) -> acc + line + "\n"));
    }
}
