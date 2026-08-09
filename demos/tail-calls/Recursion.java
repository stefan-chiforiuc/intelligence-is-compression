// Java: no tail-call optimisation. The recursion is real, and so is the stack.
//
// `sumTail` below IS written in tail position — the recursive call is the very
// last thing the method does. In Scala or Kotlin that shape compiles to a loop.
// In Java it compiles to a recursive `invokestatic`, and it blows the stack.
//
// Run:  java -cp build/demos Recursion 10000000
//
// The point is NOT "Java is bad". The point is that two languages targeting the
// SAME bytecode, on the SAME JVM, with the same JIT, disagree about whether this
// program is valid — because the transformation happens in the compiler, not the
// runtime.
public final class Recursion {

    // Tail position: nothing happens after the recursive call returns.
    static long sumTail(long n, long acc) {
        if (n == 0) return acc;
        return sumTail(n - 1, acc + n);     // <- javac emits invokestatic here
    }

    // NOT tail position: the multiplication happens AFTER the call returns, so
    // this frame must survive. No compiler on any platform can turn this into a
    // simple loop without also rewriting the arithmetic.
    static long factorial(int n) {
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }

    // What you actually write in Java. Identical semantics to sumTail, constant
    // stack. This is exactly what scalac/kotlinc generate for you.
    static long sumLoop(long n) {
        long acc = 0;
        while (n != 0) {
            acc += n;
            n--;
        }
        return acc;
    }

    public static void main(String[] args) {
        long n = args.length > 0 ? Long.parseLong(args[0]) : 10_000_000L;

        System.out.printf("Java   sumLoop(%,d)  = %,d%n", n, sumLoop(n));

        try {
            long r = sumTail(n, 0);
            System.out.printf("Java   sumTail(%,d)  = %,d%n", n, r);
        } catch (StackOverflowError e) {
            System.out.printf("Java   sumTail(%,d)  = StackOverflowError%n", n);
            System.out.println("       ^ the call was in tail position and javac recursed anyway");
        }

        // How deep can we actually go before it breaks?
        System.out.printf("Java   max depth      ~ %,d frames%n", probeDepth());
    }

    static long probeDepth() {
        try {
            return depth(0);
        } catch (StackOverflowError e) {
            return lastDepth;
        }
    }

    static long lastDepth = 0;

    static long depth(long d) {
        lastDepth = d;
        return depth(d + 1);
    }
}
