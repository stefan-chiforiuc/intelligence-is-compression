// Kotlin has fold(), foldRight() AND reduce() as separate, named methods —
// because Kotlin collections are sequential by default (no combiner needed),
// so the language can afford to expose the real thing instead of Java's
// parallel-safe compromise. See Fold.java for that contrast.
//
//   kotlinc_ demos/programming-style/Fold.kt -d build/demos/style
//   java -cp build/demos/style:$KOTLIN_LIB FoldKt

fun main() {
    val nums = listOf(1, 2, 3, 4, 5)
    val words = listOf("alpha", "bee", "cat")

    println("1) reduce — no seed, throws on an empty collection (Java's Optional, made unchecked):")
    println("   sum = " + nums.reduce { acc, x -> acc + x })

    println()
    println("2) fold(seed) { acc, x -> ... } — accumulator type can differ from element type,")
    println("   with NO combiner required, because there is no parallel path to reconcile:")
    val totalChars: Int = words.fold(0) { acc, w -> acc + w.length }
    println("   total chars across $words = $totalChars   (seed: Int, elements: String)")

    println()
    println("   fold can build a completely different SHAPE, not just a different number:")
    val grouped: Map<Int, List<String>> = words.fold(mutableMapOf<Int, MutableList<String>>()) { acc, w ->
        acc.getOrPut(w.length) { mutableListOf() }.add(w); acc
    }
    println("   words grouped by length -> $grouped")
    println("   (that accumulator lambda MUTATES acc and returns it — fold does not forbid")
    println("   that; it only promises to call your function once per element, in order.)")

    println()
    println("3) foldRight — direction is a real, visible choice, not an implementation detail:")
    val leftMinus = nums.fold(0) { acc, x -> acc - x }
    val rightMinus = nums.foldRight(0) { x, acc -> x - acc }
    println("   0-1-2-3-4-5 (foldLeft)  = $leftMinus")
    println("   1-2-3-4-5-0, right-assoc (foldRight) = $rightMinus")
    println("   Subtraction is not associative, so direction changes the answer. Java's")
    println("   Stream API has no foldRight at all — a right fold needs the elements from")
    println("   the end first, which fights a Stream's forward, lazily-pulled iteration model.")
}
