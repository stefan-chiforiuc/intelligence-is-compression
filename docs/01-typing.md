# Block 1 — Type systems

**Run:** `make demo-typing`

---

## The two axes

The single most common junior misconception is that "typed vs untyped" is one
axis. It is two, and they are independent.

```
                    STATIC (checked at compile time)
                                 ^
              Java, Go, Rust     |     (essentially empty)
              TypeScript*        |
    STRONG <---------------------+---------------------> WEAK
    (few implicit                |     (aggressive implicit
     conversions)   Python       |      conversions)
                                 v
                    DYNAMIC (checked at run time)
```

- **static vs dynamic** — *when* are types checked?
- **strong vs weak** — *how much* implicit coercion does the language do?

"Untyped" is almost never the right word. Python has types; it checks them
later. Assembly is untyped. Python is not.

\* TypeScript is the odd one out: **static at compile time, dynamic and weak at
run time**, because the types are erased. It is the only language on this chart
that changes quadrant depending on when you look.

---

## The same bug, five ways

The payload has `subtotal` as a string — the single most common real-world type
bug there is (HTML forms, CSV imports, an older service version, a Mongo
document written last year).

```json
{"subtotal": "100", "shipping": 5}
```

| Language | Result | Found |
| --- | --- | --- |
| JavaScript | `"1005"`, and `total > 500` is **true** → free shipping wrongly applied | in a billing report, eventually |
| Python | `TypeError: can only concatenate str (not "int") to str` | at run time, at the right line |
| TypeScript | `"1005"` — **byte-identical to JavaScript** | at run time, despite `: number` |
| Go | `invalid operation: mismatched types string and int` | compile time |
| Java | `incompatible types: String cannot be converted to int` | compile time |
| Rust | `error[E0369]: cannot add {integer} to &str` | compile time |

### Why Python's failure is better than JavaScript's

Both are run-time failures, but they are not equally good:

- JavaScript **invented a meaning** for `string + number` and continued. The
  wrong value flows onward and corrupts everything downstream. You find out far
  from the cause.
- Python **refused to guess** and stopped at the exact line, with a stack trace.

That is the value of *strong* typing, independent of *static* typing. When
people say "at least Python fails loudly", this is what they mean.

### The Java wart worth showing

Java's `+` **is** overloaded for `String`, so `"100" + 5` compiles and produces
`"1005"`, exactly like JavaScript. What saves you is that the *result* is typed
`String`, so assigning it to an `int` is rejected:

```java
String concatenated = subtotal + shipping;  // fine: "1005"
int total = subtotal + shipping;            // error: String cannot be converted to int
```

**Lesson:** static typing does not remove footguns, it moves the point where
they are caught.

### Why Rust is the strictest

Rust has no implicit numeric widening either:

```rust
let x: i64 = 5i32;   // error - no implicit widening
let y = 1u32 + 1i32; // error - no mixed arithmetic
```

Java and Go will widen `int` to `long` silently. Rust makes you write the cast.
That catches a real class of overflow bug and costs you a lot of small
annoyances. Whether that is a good trade depends entirely on what the software
does.

---

## The erasure moment

This is the highest-value five minutes of the whole session.

Compile `demos/typing/erasure.ts` and diff the same line:

```ts
const total: number = order.subtotal + order.shipping;   // TypeScript source
```
```js
const total = order.subtotal + order.shipping;           // emitted JavaScript
```

`interface Order` appears **zero times** in the output. The compiler deleted
every annotation. Nothing at run time enforces anything.

So this compiles, runs, and lies:

```ts
const order = JSON.parse(payload) as Order;   // `as` is a PROMISE, not a check
const total: number = order.subtotal + order.shipping;
console.log(typeof total);   // "string"
```

### The rule to write on the board

> **Types protect the inside of your program.**
> At every boundary — HTTP, JSON, env vars, the database, message queues, CLI
> args — you must **validate**, not annotate.

The fix is a runtime check that narrows the type:

```ts
function parseOrder(raw: unknown): Order {
  if (typeof raw !== "object" || raw === null ||
      typeof (raw as any).subtotal !== "number") {
    throw new TypeError("invalid Order payload");
  }
  return raw as Order;
}
```

In practice use a schema library — **zod**, **valibot**, **io-ts** — which
generates both the runtime check and the static type from one declaration.

### Do Java and Go have this problem?

Yes — **the boundary problem is universal.** The difference is the *default*.
Go's `encoding/json` and Java's Jackson decode into a declared struct/class and
**fail loudly** when the payload does not match:

```
cannot unmarshal string into Go struct field Order.subtotal of type float64
```

TypeScript's `JSON.parse` returns `any` and cheerfully lets you assert anything
about it. Same hole; one language defaults to closed, the other to open.

---

## So is TypeScript worth it?

**Yes, overwhelmingly** — and the reason is worth spelling out, because the
erasure demo can leave people unfairly cynical.

Most bugs are not malformed payloads. Most bugs are: you renamed a field and
missed a call site; you changed a function's return shape; you forgot a `null`
case; you passed the arguments in the wrong order. Static types catch all of
those **in the editor, before you run anything**, across a codebase too large
to hold in your head.

What types do **not** do:
- protect you at the boundary (validate there)
- make your code faster (they are erased; V8 is doing its own thing)
- prove your logic is right (a correctly typed program can still be wrong)

---

## Gradual typing: the middle ground

Both dynamic languages here have optional static checking bolted on:

| | Tool | Enforced at run time? |
| --- | --- | --- |
| Python | type hints + **mypy** / **pyright** | No — hints are annotations only |
| JavaScript | **TypeScript** | No — erased |

Python's hints are, if anything, *weaker* than TypeScript's: they are just
metadata in `__annotations__`, and nothing checks them unless you run mypy in
CI. But:

```python
def total(items: list[Item]) -> Decimal: ...
```

is checkable, greppable documentation that your editor understands. For any
Python codebase past a few thousand lines, hints plus mypy in CI is close to
mandatory.

**Note the pattern:** both ecosystems independently converged on "dynamic at run
time, static in the toolchain". That is a strong signal about what teams
actually want as a codebase grows.

---

## Discussion prompts

1. Your service receives JSON from a partner. Which of the five languages
   protects you, and at which point? *(Answer: all of them protect you only if
   you validate; Go/Java default to validating, TS does not.)*
2. Where would you rather find a type error: your editor, CI, staging, or a
   customer's invoice? What does each option cost per bug?
3. Your team ships a Python service that has grown to 60k lines. What is the
   cheapest intervention? *(Answer: mypy in CI, incrementally, starting at the
   boundaries.)*
4. When is dynamic typing *actively better*? *(Answer: exploration, notebooks,
   glue, short scripts, anything where the program's shape is still unknown and
   you would spend more time appeasing the checker than writing the thing.)*
