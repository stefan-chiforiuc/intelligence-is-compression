// DEMO 3 - TypeScript: static types that DO NOT EXIST at run time.
//
// This is the most important and most misunderstood thing about TypeScript,
// and the single highest-value slide in this whole section.
//
// Run:
//   npx tsc demos/typing/erasure.ts --outDir build/demos --target es2022 \
//       --module nodenext --moduleResolution nodenext --skipLibCheck --types node
//   node build/demos/erasure.js
//
// Then OPEN build/demos/erasure.js and count the type annotations. There are
// none. `tsc` deleted every single one of them.

interface Order {
  subtotal: number;
  shipping: number;
}

// Inside our own code, TypeScript is genuinely excellent. Uncomment the next
// line and `tsc` refuses to compile it - caught before the code ever ran:
//
//   const bad: Order = { subtotal: "100", shipping: 5 };
//       ^ Type 'string' is not assignable to type 'number'.

const payload = '{"subtotal": "100", "shipping": 5}';

// ...but the moment data crosses the boundary from the outside world, the type
// system is reduced to a comment. `JSON.parse` returns `any`, and `as Order` is
// us PROMISING the compiler something we have not actually checked.
const order = JSON.parse(payload) as Order;

const total: number = order.subtotal + order.shipping;

console.log("declared type of total : number");
console.log("actual  type at runtime:", typeof total);
console.log("value                  :", total);

if (typeof total !== "number") {
  console.log();
  console.log("TypeScript said `number`. The runtime says `string`.");
  console.log("The type annotation was erased; nothing enforced it.");
  console.log();
  console.log("Rule for the class: types protect the INSIDE of your program.");
  console.log("At every boundary - HTTP, JSON, env vars, the database, message");
  console.log("queues - you must VALIDATE, not just annotate. Use zod / valibot /");
  console.log("io-ts, or hand-write a parser. Java and Go have exactly the same");
  console.log("problem; their JSON libraries just fail loudly at the boundary by");
  console.log("default, which is why they feel safer here.");
}

// The fix: a real runtime check that narrows the type.
function parseOrder(raw: unknown): Order {
  if (
    typeof raw !== "object" || raw === null ||
    typeof (raw as Record<string, unknown>).subtotal !== "number" ||
    typeof (raw as Record<string, unknown>).shipping !== "number"
  ) {
    throw new TypeError("invalid Order payload");
  }
  return raw as Order;
}

try {
  parseOrder(JSON.parse(payload));
} catch (err) {
  console.log();
  console.log("With validation at the boundary:", (err as Error).message);
}
