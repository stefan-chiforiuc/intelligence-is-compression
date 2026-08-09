// Scala: the compiler rewrites self-recursive tail calls into a loop.
//
// Same JVM. Same bytecode format. Same JIT. Different compiler — and that is
// enough to change which programs are valid.
//
// Compile+run via demos/tail-calls/run.sh, or by hand:
//   java -cp <scala jars> scala.tools.nsc.Main -usejavacp -d out Recursion.scala
//   java -cp out:scala-library.jar RecursionScala

import scala.annotation.tailrec

object RecursionScala {

  // @tailrec is the interesting part. It does NOT enable the optimisation —
  // scalac would do it anyway. It makes the optimisation MANDATORY: if this
  // method is ever edited into a shape that cannot be turned into a loop, the
  // build fails. The annotation turns a silent performance/correctness cliff
  // into a compile error.
  @tailrec
  def sumTail(n: Long, acc: Long = 0): Long =
    if (n == 0) acc else sumTail(n - 1, acc + n)

  // No annotation, and genuinely not tail-recursive: the multiply happens after
  // the call returns. This still overflows in Scala. TCO is not magic — it is a
  // specific, narrow rewrite of a specific, narrow code shape.
  def factorial(n: Int): Long =
    if (n <= 1) 1 else n * factorial(n - 1)

  // Mutual recursion is NOT handled: scalac only rewrites a method that calls
  // ITSELF, because it implements the rewrite as a jump to the top of the same
  // method. isEven/isOdd below will overflow. The escape hatch is trampolining,
  // shown in Trampoline.scala.
  def isEven(n: Long): Boolean = if (n == 0) true else isOdd(n - 1)
  def isOdd(n: Long): Boolean = if (n == 0) false else isEven(n - 1)

  def main(args: Array[String]): Unit = {
    val n = if (args.length > 0) args(0).toLong else 10000000L

    println(f"Scala  sumTail($n%,d)  = ${sumTail(n)}%,d   <- @tailrec, constant stack")

    try {
      println(f"Scala  factorial(100000) = ${factorial(100000)}")
    } catch {
      case _: StackOverflowError =>
        println("Scala  factorial(100000) = StackOverflowError   <- NOT in tail position")
    }

    try {
      println(s"Scala  isEven($n)     = ${isEven(n)}")
    } catch {
      case _: StackOverflowError =>
        println(f"Scala  isEven($n%,d)   = StackOverflowError   <- mutual recursion, not rewritten")
    }
  }
}
