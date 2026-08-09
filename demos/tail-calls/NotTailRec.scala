// This file DOES NOT COMPILE, on purpose.
//
// It is the whole argument for @tailrec in four lines. The function looks
// recursive and innocent, and someone "improved" it by adding `+ 0` after the
// call — which quietly moves the call out of tail position.
//
// Without the annotation: it compiles, ships, and blows the stack in production
// on a large input, months later.
//
// With the annotation: the build fails immediately with
//
//   error: could not optimize @tailrec annotated method sumBroken:
//          it contains a recursive call not in tail position
//
// That is the real lesson. The optimisation matters less than the ENFORCEMENT.
// Java has neither, so a Java developer relying on tail recursion has no way to
// be told they have lost it.

import scala.annotation.tailrec

object NotTailRec {

  @tailrec
  def sumBroken(n: Long, acc: Long = 0): Long =
    if (n == 0) acc
    else sumBroken(n - 1, acc + n) + 0   // <- the `+ 0` breaks tail position

  def main(args: Array[String]): Unit = println(sumBroken(10))
}
