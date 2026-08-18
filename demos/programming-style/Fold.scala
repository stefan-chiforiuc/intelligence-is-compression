// Scala is where the names "foldLeft" and "foldRight" come from in the first
// place — most FP vocabulary on the JVM traces back here.
//
//   scalac_ -d build/demos/style demos/programming-style/Fold.scala
//   java -cp build/demos/style:$SCALA_LIB FoldScala

object FoldScala {
  def main(args: Array[String]): Unit = {
    val nums = List(1, 2, 3, 4, 5)
    val words = List("alpha", "bee", "cat")

    println("foldLeft(seed)(op) — the seed's type is the accumulator's type, full stop,")
    println("no relation required to the list's element type:")
    val totalChars = words.foldLeft(0)((acc, w) => acc + w.length)
    println(s"  total chars across $words = $totalChars")

    println()
    println("foldLeft vs foldRight on a non-associative op — same seed, same op, two answers:")
    val left = nums.foldLeft(0)((acc, x) => acc - x)
    val right = nums.foldRight(0)((x, acc) => x - acc)
    println(s"  foldLeft:  ((((0-1)-2)-3)-4)-5 = $left")
    println(s"  foldRight: 1-(2-(3-(4-(5-0)))) = $right")

    println()
    println("reduceLeft — foldLeft without a seed, seeded from the first element instead.")
    println("Throws (UnsupportedOperationException) on Nil, exactly like Kotlin's reduce")
    println("and Java's Stream.reduce(BinaryOperator) returning an empty Optional — three")
    println("languages, the same unavoidable question: what do you return for zero elements?")
    println(s"  ${nums.reduceLeft((a, b) => a + b)}")

    println()
    println("foldLeft is how you would implement Java's 3-arg reduce yourself, minus the")
    println("combiner: (U, (U, T) => U) => U over an ordered sequence, one element at a time.")
    println("Scala never needed a combiner parameter because List.foldLeft never runs in")
    println("parallel; .par (parallel collections) is a deliberate, separate opt-in, not")
    println("something foldLeft itself has to stay safe for by construction.")
  }
}
