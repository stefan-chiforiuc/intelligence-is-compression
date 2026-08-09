// DEMO 4b - Java: static + strong, but with one notorious wart.
//
// Run:  javac -d build/demos demos/typing/WontCompile.java
//
// Expected:
//   error: incompatible types: String cannot be converted to int
//
// The wart worth showing juniors: Java's `+` IS overloaded for String, so
// `"100" + 5` compiles happily and produces "1005", exactly like JavaScript.
// What saves you is that the RESULT is typed String, so assigning it to an
// int is rejected. The lesson: static typing does not remove footguns, it
// moves the point where they are caught.
public final class WontCompile {
    public static void main(String[] args) {
        String subtotal = "100";
        int shipping = 5;

        // This line is fine, and produces "1005" - Java's + is overloaded too:
        String concatenated = subtotal + shipping;
        System.out.println("string concat still happens: " + concatenated);

        // >>> This is the line that will not compile. <<<
        int total = subtotal + shipping;
        System.out.println(total);
    }
}
