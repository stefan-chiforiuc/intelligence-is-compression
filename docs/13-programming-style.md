# Block 2c — Programming style: functional vs. object-oriented

**Run:** `make demo-style`

Every block so far has been about the runtime: what the compiler does, what
the GC does, what the scheduler does. This one is about a choice that happens
before any of that — how you shape the code itself — and why it turns out to
be the same choice underneath a surprising number of framework conventions
you already use without thinking about them.

---

## The distinction to open with

> **Object-oriented style** bundles data with the behaviour that mutates it,
> and models a program as objects sending each other messages over time.
>
> **Functional style** treats computation as the evaluation of expressions
> with no side effects, and models a program as a pipeline of pure functions
> from input to output.

Neither is "the right one." They are different bets about where complexity
should live: OOP puts it inside objects (an object's *current state* is a
summary of its history); FP puts it in the *shape of the data flowing between
functions* (there is no history to summarize — every value is total and
final).

The question that resolves most real arguments here, the same way "are you
waiting or computing" resolved Block 4:

> **Does calling this function/method again, with the same arguments, ever
> give you a different answer — or leave anything different behind?**

If no: it's pure, and every FP advantage below applies to it. If yes:
something is mutable and shared, and everything Block 4 said about shared
mutable state applies to it too, whether or not a second thread is involved.

---

## Part 1 — Fold: the FP litmus test, and why Java doesn't have one

**Run:** `demos/programming-style/Fold.java` / `.kt` / `.scala`

A **left fold** is three things: a seed, a combining function, and a
direction. `foldl(f, z, [x1,x2,x3]) = f(f(f(z, x1), x2), x3)`. That's the
entire concept — `sum`, `max`, `toList`, `groupBy`, string-building: almost
every "walk a collection and produce one answer" operation is a fold with a
different `f`.

**Kotlin and Scala have it as a named, one-argument-simpler method:**

```kotlin
words.fold(0) { acc, w -> acc + w.length }      // seed: Int, elements: String — fine
nums.foldRight(0) { x, acc -> x - acc }         // direction is explicit and changes the answer
```

**Java's `Stream` does not have `fold`. It has three overloads of `reduce`,**
and the gap between them is the whole lesson:

| Overload | Shape | The catch |
| --- | --- | --- |
| `reduce(BinaryOperator<T>)` | no seed | returns `Optional<T>` — what do you return for zero elements? |
| `reduce(T identity, BinaryOperator<T>)` | this **is** `foldLeft` | only when the accumulator type equals the element type |
| `reduce(U identity, BiFunction<U,T,U> acc, BinaryOperator<U> combiner)` | accumulator type can differ from element type — genuinely fold-shaped | **requires an associative `combiner`** |

That third argument, `combiner`, is the tell. `reduce()` was designed for a
stream that *might* go parallel (`demos/java-parallel-cost`,
[`09-when-to-parallelize.md`](09-when-to-parallelize.md)): it has to say how
to merge two partial results computed by two different threads on two
different chunks. A sequential `foldLeft` never needs that — there is only
ever one running total. If your combiner isn't associative
(`(acc, x) -> acc - x` isn't), `.parallel().reduce(...)` will happily hand you
a different, order-dependent, wrong answer with no exception and no warning.
A real fold can't have this failure mode, because a real fold never lets your
chunks run out of order in the first place.

**Why no `foldRight` in Java at all?** A right fold needs the last element
first — conceptually you must reach the end before you can start combining.
That fights a `Stream`'s entire execution model: forward, lazily pulled,
one-pass. Kotlin and Scala's collections are eagerly materialized lists, so
walking them backwards costs nothing extra; a `Stream` promises not to
require that.

**Where the mutation actually is.** `.collect(Collectors.toList())` *looks*
purely functional from the outside. Internally, each parallel branch mutates
its *own* private `ArrayList` (`accumulator: (List, T) -> void`, literally
`list.add(x)`), and only the final merge across branches is pure. This is
Java's actual compromise, and it's a good one: use cheap local mutation where
no other thread can ever observe it, expose a pure-looking API at the
boundary. Keep this shape in mind for Part 3 — it's the same shape a
well-designed Spring bean uses.

---

## Part 2 — The same pricing rule: an assembled object vs. an assembled function

**Run:** `demos/programming-style/OrderPricingStyles.java`

The comparison that matters isn't "the same method body, one written with
loops and one written with streams" — that's cosmetics on top of the same
shape. The real fork in the road is earlier than the method body: **where
does behaviour live, and what has to exist before you can call it?**

**OOP: behaviour lives in an object.** A `@Service` is a class; calling it
needs an *instance*, and building that instance means wiring collaborator
*objects* into constructor parameters, stored as fields:

```java
@Service                                                  // singleton
class OrderPricingService {
    private final TierDiscountPolicy tierDiscounts;       // an OBJECT, stored
    private final CouponPolicy coupons;                    // an OBJECT, stored
    private final TaxCalculator tax;                       // an OBJECT, stored
    private final ShippingPolicy shipping;                 // an OBJECT, stored

    OrderPricingService(TierDiscountPolicy t, CouponPolicy c, TaxCalculator tx, ShippingPolicy s) {
        this.tierDiscounts = t; this.coupons = c; this.tax = tx; this.shipping = s;
    }

    Receipt price(Order order) {
        long subtotal = 0;
        for (LineItem item : order.items()) subtotal += item.unitPriceCents() * item.quantity();
        long discount = tierDiscounts.discountCents(order.customerTier(), subtotal);
        if (order.couponCode() != null) discount += coupons.discountCents(order.couponCode(), subtotal - discount);
        if (discount > subtotal) discount = subtotal;
        long taxable = subtotal - discount;
        long taxCents = tax.taxCents(taxable);
        return new Receipt(subtotal, discount, taxCents, shipping.shippingCents(taxable),
                            taxable + taxCents + shipping.shippingCents(taxable));
    }
}
```

This is precisely why Spring's container exists: assembling a graph of
objects like this one, by hand, at every call site, is exactly the tedium a
DI framework earns its keep removing.

**FP: behaviour is a value.** There is no class to instantiate. A pricing
calculator is a single `Function<Order, Receipt>`, assembled once by
composing smaller pure functions with `andThen`. The four "collaborators"
are plain static methods — nothing implements anything; a method reference
just happens to match the shape of the parameter:

```java
static long tierDiscount(String tier, long subtotalCents) { /* same rule */ }
static long couponDiscount(String code, long amountCents) { /* same rule */ }
static long tax(long taxableCents) { /* same rule */ }
static long shipping(long taxableCents) { /* same rule */ }

static Function<Order, Receipt> pipeline(
        TierDiscountPolicy tierDiscount, CouponPolicy couponDiscount,
        TaxCalculator tax, ShippingPolicy shipping) {

    Function<Order, Ctx> subtotal = order -> new Ctx(order,
            order.items().stream().mapToLong(i -> i.unitPriceCents() * i.quantity()).sum(), 0);
    Function<Ctx, Ctx> applyTierDiscount = ctx ->
            ctx.withDiscount(tierDiscount.discountCents(ctx.order().customerTier(), ctx.subtotalCents()));
    Function<Ctx, Ctx> applyCoupon = ctx -> ctx.order().couponCode() == null ? ctx
            : ctx.withDiscount(ctx.discountCents() + couponDiscount.discountCents(ctx.order().couponCode(), ctx.taxableCents()));
    Function<Ctx, Ctx> clamp = ctx -> ctx.withDiscount(Math.min(ctx.discountCents(), ctx.subtotalCents()));
    Function<Ctx, Receipt> settle = ctx -> /* build the Receipt */;

    return subtotal.andThen(applyTierDiscount).andThen(applyCoupon).andThen(clamp).andThen(settle);
}

// no `new` anywhere — four method references go in, a FUNCTION comes out:
Function<Order, Receipt> pricing = pipeline(
        FunctionalPricing::tierDiscount, FunctionalPricing::couponDiscount,
        FunctionalPricing::tax, FunctionalPricing::shipping);

pricing.apply(order);     // called like oop.price(order) — but nothing was constructed to get here
```

Run against four sample orders, **both produce byte-identical `Receipt`
values every time** — the demo asserts it and prints `identical` on each
line. Same business rules, same computation, same big-O, same thread-safety
(neither side has a mutable field — see Part 3 for what that would cost).
What differs is what you're holding at the end of assembly:

| | OOP | FP |
| --- | --- | --- |
| What gets built | an object graph — one instance per collaborator, wired via a constructor | one value — a `Function<Order,Receipt>`, closing over four method references |
| What's needed to call it | `new OrderPricingService(...)`, or a container that does it for you | nothing — call `pipeline(...)` once, keep the `Function` it returns |
| Where a reviewer looks to verify correctness | trace field reads through the method body, in statement order | read the `andThen` chain top to bottom — that chain *is* the list of rules, in order |
| Adding a fifth rule | a fifth field, a fifth constructor parameter, a fifth `if` | a fifth `Ctx -> Ctx` stage, one more `.andThen(...)` link |
| Does it need Spring? | yes, in spirit — this is the shape DI exists to assemble | no — a `static final Function<Order,Receipt>` needs no container. If you wanted it Spring-managed anyway (for `@ConditionalOnProperty`-style swapping, say), you'd expose it as one `@Bean` returning a `Function`, not as four `@Component` classes |

**That's the honest scope of the claim.** OOP's constructor injection is a
general answer to "how do I assemble behaviour from parts" that happens to
need a framework to stop being tedious at scale. FP's function composition
is a *different* general answer to the same question, and for a case this
shaped — a fixed, ordered list of pure transformations — it doesn't need a
container at all. Neither is faster, safer, or more correct here; the two
demonstrably compute the same numbers. What changes is what kind of thing
you're assembling — an object graph or a function — and how much machinery
that choice pulls in behind it.

Contrast that with what genuinely *is* a correctness difference — a
mutable field — covered next.

---

## Part 3 — Why a Spring bean with constructor injection behaves like a function

**Run:** `demos/programming-style/SpringBeanStyle.java`

This is the payoff, and the reason this block sits where it does: a fact
about dependency injection that most Spring developers use every day without
ever naming it.

```java
@Service                                    // default scope: SINGLETON
class PricingService {
    private final TaxRule taxRule;          // set once, by the constructor, never reassigned
    PricingService(TaxRule taxRule) { this.taxRule = taxRule; }   // constructor injection

    double price(double amount) {           // depends ONLY on amount + taxRule
        return amount + taxRule.apply(amount);
    }
}
```

If `TaxRule` is itself immutable and `PricingService` has **no field besides
its injected, immutable collaborators**, then `price(amount)` is a pure
function: same input, same output, forever, no matter what else has called it
first, on what thread. That is *why* Spring is comfortable handing the exact
same singleton instance to every concurrent request thread with no
synchronization anywhere in sight — there is no state on the object for two
requests to disagree about. Constructor injection didn't just replace
`@Autowired` field/setter injection because it's more testable (it is); it
also happens to be the shape that keeps a bean pure, by only ever assigning
`final` fields once, at construction, before any request can reach it.

**The instant a bean gets one mutable field, that guarantee is gone —
silently:**

```java
class StatefulPricingService {
    private final TaxRule taxRule;
    private int requestsServed = 0;         // <-- this one field breaks the property

    double price(double amount) {
        requestsServed++;                    // read-modify-write on shared state
        return amount + taxRule.apply(amount);
    }
}
```

The container still hands out **one shared instance**. Every concurrent
request thread now reads and writes `requestsServed` on that same object,
with no lock — the identical bug as the `ArrayList` field in
[`09-when-to-parallelize.md`](09-when-to-parallelize.md), Part 3, wearing a
`@Service` costume instead of a `@RestController` field. The measured demo:
8 threads × 100,000 calls each on one shared `StatefulPricingService` lose
tens of thousands of increments, with nothing thrown and nothing logged.

**Spring's container cannot see the difference between the two beans above.**
Dependency injection manages *wiring* — which object gets handed to which
constructor — not *statefulness*. Whether the object it hands out is safe to
share is a property of your class, and DI frameworks have no opinion on it
either way.

### The rule this collapses to

> A bean with only `final` fields assigned in the constructor, and no method
> that writes to a field afterward, **is** a pure function — share it as
> widely as you like.
>
> The moment a method writes to a field, that bean **is** shared mutable
> state, no different from a global variable, and every hazard from Block 4
> applies — whether or not you ever call it from more than one thread today.

If a bean genuinely needs to hold onto counters, caches, or connections, that
is not wrong — it means that piece of state deserves a type built for
concurrent state (`AtomicInteger`, a proper cache library, a connection
pool — see [`10-databases-and-scaling.md`](10-databases-and-scaling.md)), kept
separate from the pure decision logic, not folded into the same object as an
afterthought field.

---

## Notes on performance, maintainability, readability

- **Performance.** Pure/FP code is not inherently faster — the OOP and FP
  pricing calculators in Part 2 do the same arithmetic and measure the same.
  What FP style buys you is *safe default parallelism*: a pipeline of pure stages can usually
  take `.parallel()` without changing its answer (subject to Block 4b's
  crossover — measure, don't assume), while a pipeline built on shared
  mutable objects needs synchronization added by hand, correctly, everywhere
  that state is touched. FP's actual performance cost is usually allocation:
  an immutable pipeline tends to build more short-lived intermediate objects
  than an in-place mutating loop, which is a GC/allocator question, not a
  CPU one (see [`03-memory.md`](03-memory.md)).
- **Maintainability.** A pure function's contract is its signature — nothing
  else can affect it, and it can't affect anything else. A stateful object's
  contract includes every method that can mutate it, in every order they
  might be called, which is why "just add a `synchronized`" fixes on stateful
  legacy code tend to accumulate rather than resolve — each mutable field is
  a fact a maintainer now has to hold in their head to change *any* method on
  the class.
- **Readability.** An FP pipeline (`filter` → `map` → `reduce`) reads as *what*
  the result is; an imperative loop with mutable accumulators reads as *how*
  to compute it, one step at a time. The imperative version is not automatically
  worse — for a genuinely stateful process (a parser tracking position, a
  simulation stepping forward in time) the state *is* the domain, and forcing
  it into a fold can obscure more than it clarifies. Prefer FP when the task
  is "derive an answer from data"; prefer explicit state when the task is
  "model something that actually changes over time."

---

## Discussion prompts

1. A colleague adds a `private Map<String,Object> cache = new HashMap<>();`
   field to a `@Service` "to speed things up." What immediately becomes true
   about that bean that wasn't true before? *(It stops being a pure function;
   it becomes shared mutable state, racy under concurrent requests exactly
   like the plain `HashMap` in Block 4, and now also memory-unbounded.)*
2. Why does Kotlin get to have a real `foldRight` when Java's `Stream`
   doesn't? *(Kotlin's `List` is eagerly materialized and never silently
   parallel; a `Stream` is lazily pulled and was designed to survive
   `.parallel()`, which a right fold's need-the-end-first shape resists.)*
3. Setter injection (`@Autowired` on a field or setter) versus constructor
   injection: which one *forces* the "no field write after construction"
   property, and which one merely allows it? *(Constructor injection with
   `final` fields forces it — there is no setter to call later. Field/setter
   injection allows a well-behaved bean but doesn't prevent someone adding a
   mutator next sprint.)*
4. Where else in this session did "make the invalid state unrepresentable"
   show up? *(Static types, `@tailrec`, `Mutex<T>`/`Send`+`Sync` — and now
   `final` fields on a singleton bean, same idea, no framework required.)*
