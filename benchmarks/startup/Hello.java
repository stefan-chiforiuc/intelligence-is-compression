// Cold-start workload: do essentially nothing, as fast as possible.
//
// Everything this program measures happens BEFORE your business logic runs:
// process spawn, dynamic linking, JVM initialisation, class loading and
// verification. That fixed cost is what you pay on every single serverless
// invocation and on every pod restart during a rolling deploy.
//
// The JVM is the worst performer here by a wide margin, and there are three
// standard mitigations worth knowing about:
//   1. Class Data Sharing (CDS) — see `make startup-cds`, typically -30%
//   2. GraalVM native-image     — AOT compile to a real binary, ~5 ms
//   3. Just don't use per-request processes — keep a warm JVM behind a queue
public final class Hello {
    public static void main(String[] args) {
        int n = args.length > 0 ? Integer.parseInt(args[0]) : 1;
        System.out.println("ready " + (n * 2));
    }
}
