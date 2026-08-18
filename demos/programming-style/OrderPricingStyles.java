// The same pricing rule, implemented twice, to isolate what OOP vs FP style
// actually costs once everything else is held constant:
//
//   OOP version: a @Service singleton. Behaviour is an OBJECT: a constructor
//                receives collaborator OBJECTS and stores them in fields;
//                calling a method reads those fields. This needs a container
//                (or `new`, by hand) to assemble, because objects have to be
//                built before they can be called.
//
//   FP version:  a calculator. Behaviour is a VALUE: a `Function<Order,
//                Receipt>` assembled once by composing smaller pure
//                functions with `.andThen(...)`. There is no class to
//                instantiate and no field to store a collaborator in —
//                the business-rule functions are closed over directly.
//                Nothing here is "a method written in a functional style";
//                there is no method, no object, and no constructor at all.
//
// Both:
//   * hold zero mutable state (see SpringBeanStyle.java for what an ACTUAL
//     semantic difference looks like — a mutable field, a real race. This
//     file has none of that, on either side.)
//   * produce byte-identical Receipt values for every order below
//
// The point: once mutability is off the table, OOP vs FP is not a
// correctness or safety question. It is a question of whether behaviour
// lives in an assembled OBJECT GRAPH or an assembled FUNCTION.
//
//   javac -d build/demos/style demos/programming-style/OrderPricingStyles.java
//   java -cp build/demos/style OrderPricingStyles
import java.util.List;
import java.util.function.Function;

public final class OrderPricingStyles {

    // ---- THE DOMAIN, SHARED BY BOTH VERSIONS ---------------------------
    record LineItem(String sku, int quantity, long unitPriceCents) {}
    record Order(String customerTier, List<LineItem> items, String couponCode) {}
    record Receipt(long subtotalCents, long discountCents, long taxCents,
                    long shippingCents, long totalCents) {}

    // Single-method interfaces — i.e. already just function TYPES. Both
    // versions below implement the exact same four signatures. What differs
    // is what fills them: an OBJECT (OOP) or a bare STATIC METHOD (FP).
    interface TierDiscountPolicy { long discountCents(String tier, long subtotalCents); }
    interface CouponPolicy { long discountCents(String couponCode, long amountCents); }
    interface TaxCalculator { long taxCents(long taxableCents); }
    interface ShippingPolicy { long shippingCents(long taxableCents); }

    // ---- OOP VERSION ----------------------------------------------------
    // @Component classes: a policy is an OBJECT you have to construct before
    // you can call it, even though it has no state of its own.
    static final class StandardTierDiscounts implements TierDiscountPolicy {
        public long discountCents(String tier, long subtotalCents) {
            return switch (tier) {
                case "GOLD" -> subtotalCents * 10 / 100;
                case "SILVER" -> subtotalCents * 5 / 100;
                default -> 0;
            };
        }
    }
    static final class CouponCodes implements CouponPolicy {
        public long discountCents(String code, long amountCents) {
            return "SAVE10".equals(code) ? amountCents * 10 / 100 : 0;
        }
    }
    static final class FlatRateTax implements TaxCalculator {
        public long taxCents(long taxableCents) { return taxableCents * 8 / 100; }
    }
    static final class FreeShippingOverThreshold implements ShippingPolicy {
        public long shippingCents(long taxableCents) { return taxableCents >= 5_000 ? 0 : 500; }
    }

    // @Service                                          <- default scope: SINGLETON
    // class OrderPricingService {
    //     OrderPricingService(TierDiscountPolicy t, CouponPolicy c,       <- constructor injection:
    //                          TaxCalculator tx, ShippingPolicy s) {...}     an OBJECT GRAPH gets built
    // }
    static final class OopPricingService {
        private final TierDiscountPolicy tierDiscounts;
        private final CouponPolicy coupons;
        private final TaxCalculator tax;
        private final ShippingPolicy shipping;

        OopPricingService(TierDiscountPolicy tierDiscounts, CouponPolicy coupons,
                           TaxCalculator tax, ShippingPolicy shipping) {
            this.tierDiscounts = tierDiscounts;
            this.coupons = coupons;
            this.tax = tax;
            this.shipping = shipping;
        }

        Receipt price(Order order) {
            long subtotal = 0;
            for (LineItem item : order.items()) {                       // manual accumulation
                subtotal += item.unitPriceCents() * item.quantity();
            }

            long discount = tierDiscounts.discountCents(order.customerTier(), subtotal);
            if (order.couponCode() != null) {                            // manual branch
                discount += coupons.discountCents(order.couponCode(), subtotal - discount);
            }
            if (discount > subtotal) {                                   // manual edge-case clamp
                discount = subtotal;
            }

            long taxable = subtotal - discount;
            long taxCents = tax.taxCents(taxable);
            long shippingCents = shipping.shippingCents(taxable);
            long total = taxable + taxCents + shippingCents;

            return new Receipt(subtotal, discount, taxCents, shippingCents, total);
        }
    }

    // ---- FP VERSION: not a service, not a bean, not a class you construct ---
    // There is no `new FunctionalPricingCalculator(...)` anywhere in this
    // file. A pricing calculator is ONE VALUE — a Function<Order, Receipt> —
    // built once by composing smaller pure functions. The four rules below
    // are plain static methods, not objects: nothing implements
    // TierDiscountPolicy here, a method reference just HAPPENS to match its
    // shape, because a functional interface is nothing more than a shape.
    static final class FunctionalPricing {
        private FunctionalPricing() {}                     // never instantiated — not even once

        // The rules themselves. No class, no @Component, no `implements`.
        static long tierDiscount(String tier, long subtotalCents) {
            return switch (tier) {
                case "GOLD" -> subtotalCents * 10 / 100;
                case "SILVER" -> subtotalCents * 5 / 100;
                default -> 0;
            };
        }
        static long couponDiscount(String code, long amountCents) {
            return "SAVE10".equals(code) ? amountCents * 10 / 100 : 0;
        }
        static long tax(long taxableCents) { return taxableCents * 8 / 100; }
        static long shipping(long taxableCents) { return taxableCents >= 5_000 ? 0 : 500; }

        // The value flowing through the pipeline. It carries the Order
        // alongside the running totals because a pipeline stage has no
        // field to read `order` from — whatever a stage needs must travel
        // IN the value, not be reached for on `this`.
        private record Ctx(Order order, long subtotalCents, long discountCents) {
            long taxableCents() { return subtotalCents - discountCents; }
            Ctx withDiscount(long d) { return new Ctx(order, subtotalCents, d); }
        }

        /**
         * Assembles the calculator: five pure stages glued end to end with
         * {@code andThen}. Calling this returns a FUNCTION, not an object —
         * there is nothing to hold onto, nothing to inject it into, and
         * nothing that needs a container to exist. The four parameters play
         * exactly the role constructor-injected collaborators play for the
         * OOP version above; here they are just captured by the closures
         * `andThen` builds, instead of assigned to fields.
         */
        static Function<Order, Receipt> pipeline(
                TierDiscountPolicy tierDiscount,
                CouponPolicy couponDiscount,
                TaxCalculator tax,
                ShippingPolicy shipping) {

            Function<Order, Ctx> subtotal = order -> new Ctx(order,
                    order.items().stream().mapToLong(i -> i.unitPriceCents() * i.quantity()).sum(), 0);

            Function<Ctx, Ctx> applyTierDiscount = ctx ->
                    ctx.withDiscount(tierDiscount.discountCents(ctx.order().customerTier(), ctx.subtotalCents()));

            Function<Ctx, Ctx> applyCoupon = ctx -> ctx.order().couponCode() == null
                    ? ctx
                    : ctx.withDiscount(ctx.discountCents()
                            + couponDiscount.discountCents(ctx.order().couponCode(), ctx.taxableCents()));

            Function<Ctx, Ctx> clamp = ctx -> ctx.withDiscount(Math.min(ctx.discountCents(), ctx.subtotalCents()));

            Function<Ctx, Receipt> settle = ctx -> {
                long taxCents = tax.taxCents(ctx.taxableCents());
                long shippingCents = shipping.shippingCents(ctx.taxableCents());
                return new Receipt(ctx.subtotalCents(), ctx.discountCents(), taxCents, shippingCents,
                        ctx.taxableCents() + taxCents + shippingCents);
            };

            // THE PIPELINE. This one expression IS the calculator — reading
            // it top to bottom already reads as the list of business rules,
            // in the order they apply, with nothing else to trace.
            return subtotal.andThen(applyTierDiscount).andThen(applyCoupon).andThen(clamp).andThen(settle);
        }
    }

    public static void main(String[] args) {
        OopPricingService oop = new OopPricingService(
                new StandardTierDiscounts(), new CouponCodes(), new FlatRateTax(), new FreeShippingOverThreshold());

        // No `new` on this side. Four method references go in; a function
        // comes out. `pricing` is not "an instance of the FP service" —
        // there is no such thing — it is the calculator itself, as a value.
        Function<Order, Receipt> pricing = FunctionalPricing.pipeline(
                FunctionalPricing::tierDiscount, FunctionalPricing::couponDiscount,
                FunctionalPricing::tax, FunctionalPricing::shipping);

        List<Order> orders = List.of(
                new Order("GOLD", List.of(new LineItem("WIDGET", 3, 1200), new LineItem("GADGET", 1, 4500)), "SAVE10"),
                new Order("SILVER", List.of(new LineItem("WIDGET", 1, 999)), null),
                new Order("BASIC", List.of(new LineItem("BULK", 100, 50)), "SAVE10"),
                new Order("GOLD", List.of(), null));

        System.out.println("OOP: oop.price(order) — a method call on an assembled OBJECT.");
        System.out.println("FP:  pricing.apply(order) — a call on an assembled FUNCTION. No object exists.");

        boolean allIdentical = true;
        for (Order o : orders) {
            Receipt r1 = oop.price(o);
            Receipt r2 = pricing.apply(o);
            boolean same = r1.equals(r2);
            allIdentical &= same;
            System.out.println();
            System.out.printf("  %s x%d item(s), coupon=%s%n",
                    o.customerTier(), o.items().size(), o.couponCode());
            System.out.printf("    OOP -> subtotal=%-6d discount=%-6d tax=%-6d shipping=%-6d total=%-6d%n",
                    r1.subtotalCents(), r1.discountCents(), r1.taxCents(), r1.shippingCents(), r1.totalCents());
            System.out.printf("    FP  -> subtotal=%-6d discount=%-6d tax=%-6d shipping=%-6d total=%-6d   %s%n",
                    r2.subtotalCents(), r2.discountCents(), r2.taxCents(), r2.shippingCents(), r2.totalCents(),
                    same ? "identical" : "DIFFERENT — bug!");
        }

        System.out.println();
        System.out.println(allIdentical
                ? "Every order priced IDENTICALLY by both versions."
                : "Mismatch found — that would be a real bug, not a style difference.");

        System.out.println();
        System.out.println("WHAT ACTUALLY DIFFERS");
        System.out.println("  OOP: behaviour lives in an OBJECT GRAPH. `new OopPricingService(...)` builds");
        System.out.println("  one object holding four collaborator objects in fields. A framework earns");
        System.out.println("  its keep here — Spring's container exists to build graphs like this one so");
        System.out.println("  you don't call `new` by hand at every use site.");
        System.out.println();
        System.out.println("  FP: behaviour is a VALUE. `FunctionalPricing.pipeline(...)` returns a");
        System.out.println("  Function<Order,Receipt> that closes over four method references — no class");
        System.out.println("  was instantiated to get it. `pricing` could be a `static final` constant,");
        System.out.println("  a field, a method parameter, or a @Bean's return value; nothing about it");
        System.out.println("  needs a container, because there is no graph, only one function value.");
        System.out.println();
        System.out.println("  Both are equally correct and equally thread-safe (no mutable state, either");
        System.out.println("  side — see SpringBeanStyle.java for what breaks that). The difference is");
        System.out.println("  what you are handed back: an object you call a method on, or a function you");
        System.out.println("  apply — and, downstream of that, how you add a fifth rule: a fifth `private");
        System.out.println("  final` field plus a fifth constructor parameter and a fifth if-branch, or a");
        System.out.println("  fifth `.andThen(...)` link with one new pure Ctx -> Ctx stage.");
    }
}
