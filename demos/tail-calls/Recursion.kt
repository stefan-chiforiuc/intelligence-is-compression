// Kotlin: same optimisation, different spelling.
//
// Worth showing alongside Scala so nobody concludes this is an exotic
// functional-language feature. Kotlin is a mainstream, pragmatic, Java-adjacent
// language and it does exactly the same rewrite. It is `tailrec`, a modifier on
// the function, rather than an annotation.
//
// Like Scala's @tailrec, it is CHECKED: mark a non-tail-recursive function
// `tailrec` and the compiler warns that it cannot be optimised, so you find out
// at build time rather than in production.

// Compiles to a loop. Constant stack.
tailrec fun sumTail(n: Long, acc: Long = 0): Long =
    if (n == 0L) acc else sumTail(n - 1, acc + n)

// Not in tail position — the multiply happens after the call returns.
fun factorial(n: Int): Long =
    if (n <= 1) 1 else n * factorial(n - 1)

fun main(args: Array<String>) {
    val n = if (args.isNotEmpty()) args[0].toLong() else 10_000_000L

    println("Kotlin sumTail(%,d)  = %,d   <- tailrec, constant stack".format(n, sumTail(n)))

    try {
        println("Kotlin factorial(100000) = ${factorial(100000)}")
    } catch (e: StackOverflowError) {
        println("Kotlin factorial(100000) = StackOverflowError   <- NOT in tail position")
    }
}
