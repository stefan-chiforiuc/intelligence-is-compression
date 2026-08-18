// Java: any reference type can be null, and the type system doesn't know it.
//
// Run:  javac -g -d build/demos/nullsafety demos/null-safety/NullSafety.java
//       java -cp build/demos/nullsafety NullSafety
//
// (-g keeps local variable names, so the helpful-NPE message below names
// "missing" instead of a debug-stripped "<local3>".)
//
// Expected:
//   Exception in thread "main" java.lang.NullPointerException:
//       Cannot invoke "String.length()" because "missing" is null
//
// Nothing here is a bug in the usual sense - Map.get() legitimately returns
// null for a missing key, and String is exactly as valid a type for null as
// for "Ada". The compiler has no way to tell you that THIS call site forgot
// to check.
import java.util.Map;

public final class NullSafety {
    static String getNickname(Map<String, String> users, String id) {
        return users.get(id); // returns null on a missing key - by design
    }

    public static void main(String[] args) {
        Map<String, String> users = Map.of("1", "Ada");

        String name = getNickname(users, "1");
        System.out.println("user 1: " + name.length() + " chars"); // fine

        // >>> This line compiles perfectly and blows up at run time. <<<
        String missing = getNickname(users, "2");
        System.out.println("user 2: " + missing.length() + " chars");
    }
}
