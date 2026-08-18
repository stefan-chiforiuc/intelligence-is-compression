// BONUS - Java `var` (10+): type inference is still STATIC.
//
// Run:  javac -d build/demos demos/typing/VarInference.java
//
// Expected:
//   error: incompatible types: int cannot be converted to String
//
// `var` erases the ANNOTATION, not the axis. javac still works out one
// concrete type for `name` at the declaration - java.lang.String - and that
// type never changes afterwards. This is exactly as static as writing
// `String name = "Ada";`; it is just shorter to type. Confusing "the
// compiler inferred it" with "it can be anything from here on" is the most
// common thing juniors get wrong about `var`.
public final class VarInference {
    public static void main(String[] args) {
        var name = "Ada"; // inferred once: java.lang.String
        System.out.println(name.getClass().getSimpleName());

        // >>> This is the line that will not compile. <<<
        name = 42;
        System.out.println(name);
    }
}
