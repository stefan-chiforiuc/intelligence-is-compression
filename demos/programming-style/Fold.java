// Java's Stream has no method literally called "fold". It has reduce(),
// three overloads of it, and the gap between reduce() and a real fold is the
// whole lesson.
//
//   javac -d build/demos/style demos/programming-style/Fold.java
//   java -cp build/demos/style Fold
//
// A LEFT FOLD, informally: foldl(f, z, [x1, x2, x3]) = f(f(f(z, x1), x2), x3)
// It has three parts: a seed z, a combining function f, and a direction
// (left-to-right). That is all a fold is.
import java.util.List;
import java.util.Optional;

public final class Fold {

    public static void main(String[] args) {
        List<Integer> nums = List.of(1, 2, 3, 4, 5);
        List<String> words = List.of("alpha", "bee", "cat");

        System.out.println("1) reduce(BinaryOperator<T>) — no seed, returns Optional");
        Optional<Integer> sum1 = nums.stream().reduce((a, b) -> a + b);
        System.out.println("   sum = " + sum1.get());
        System.out.println("   empty list -> " + List.<Integer>of().stream().reduce((a, b) -> a + b));
        System.out.println("   No seed means no answer for an empty stream. A real fold never");
        System.out.println("   has this problem, because the seed IS the answer for the empty case.");

        System.out.println();
        System.out.println("2) reduce(T identity, BinaryOperator<T>) — this IS foldLeft, but");
        System.out.println("   only when the accumulator type equals the element type:");
        int sum2 = nums.stream().reduce(0, (acc, x) -> acc + x);
        System.out.println("   sum = " + sum2 + "   (T = Integer, accumulator: Integer x Integer -> Integer)");

        System.out.println();
        System.out.println("3) reduce(U identity, BiFunction<U,T,U> accumulator, BinaryOperator<U> combiner)");
        System.out.println("   The three-arg form DOES let the accumulator type U differ from the");
        System.out.println("   element type T — that is the part that is genuinely fold-shaped:");
        int totalChars = words.stream()
                .reduce(0, (charsSoFar, word) -> charsSoFar + word.length(), Integer::sum);
        System.out.println("   total chars across " + words + " = " + totalChars
                + "   (U = Integer, T = String)");

        System.out.println();
        System.out.println("WHY IT IS NOT JUST CALLED fold()");
        System.out.println("   The third argument, `combiner`, is the tell. reduce() was designed for a");
        System.out.println("   stream that MIGHT run in parallel (see demos/java-parallel-cost). A real");
        System.out.println("   sequential foldLeft only ever needs the seed and the accumulator — there");
        System.out.println("   is nothing to combine, because there is only ever one running total.");
        System.out.println("   reduce() additionally demands: 'and here is how to MERGE two partial");
        System.out.println("   results computed by different threads on different chunks.' That merge");
        System.out.println("   step only produces a correct answer if `accumulator`/`combiner` are");
        System.out.println("   associative. `(acc, x) -> acc - x` is NOT associative, and reduce() will");
        System.out.println("   silently give you a different (wrong, order-dependent) answer if you add");
        System.out.println("   .parallel() to a stream using it. A fold never has this trap, because a");
        System.out.println("   fold never runs your chunks out of order in the first place.");

        int leftFoldMinus = nums.stream().reduce(0, (acc, x) -> acc - x);          // sequential: deterministic
        int parallelMinus = nums.parallelStream().reduce(0, (acc, x) -> acc - x, Integer::sum);
        System.out.println("   sequential 0-1-2-3-4-5            = " + leftFoldMinus);
        System.out.println("   \"same\" reduce, .parallel(), non-associative op = " + parallelMinus
                + "   <- do not trust this number to be stable across machines/JDKs");

        System.out.println();
        System.out.println("WHERE THE MUTATION ACTUALLY LIVES: Collectors");
        System.out.println("   .collect(Collectors.toList()) LOOKS purely functional from the outside,");
        System.out.println("   but internally each thread mutates its OWN ArrayList (accumulator: (List,T)");
        System.out.println("   -> void, via list.add(x)), and only the final merge step is pure. That is");
        System.out.println("   the actual FP/OOP compromise Java made: use cheap local mutation where no");
        System.out.println("   other thread can observe it, expose a pure-looking API at the boundary.");
        List<Integer> doubled = nums.stream().map(x -> x * 2).collect(java.util.stream.Collectors.toList());
        System.out.println("   " + nums + " -> map(x*2) -> collect(toList()) -> " + doubled);
    }
}
