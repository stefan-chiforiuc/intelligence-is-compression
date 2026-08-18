// Kotlin: the SAME bug, but String and String? are different types.
//
// Run (needs the standalone compiler - see demos/null-safety/run.sh):
//   kotlinc_ demos/null-safety/NullSafety.kt -d build/demos/nullsafety
//   java -cp "build/demos/nullsafety:$KOTLIN_LIB" NullSafetyKt
//
// Uncomment the marked line below and recompile - it will not build:
//   error: only safe (?.) or non-null asserted (!!.) calls are allowed
//   on a nullable receiver of type String?

fun getNickname(users: Map<String, String>, id: String): String? = users[id]

fun main() {
    val users = mapOf("1" to "Ada")

    val name: String? = getNickname(users, "1")
    println("user 1: ${name?.length} chars") // safe call: null-propagating, not a crash

    val missing: String? = getNickname(users, "2")
    println("user 2: ${missing?.length ?: "no nickname"}")

    // >>> Uncomment: does not compile. The compiler catches it, not a test run. <<<
    // println("user 2: " + missing.length)

    // The escape hatch still exists - Kotlin doesn't remove the crash, it makes
    // you ask for it by name, so it shows up in a code review diff:
    // println(missing!!.length) // NullPointerException, but spelled out at the call site
}
