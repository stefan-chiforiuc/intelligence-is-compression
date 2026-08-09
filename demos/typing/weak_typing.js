// DEMO 1 - JavaScript: dynamically typed AND weakly typed.
//
// The client sent us `subtotal` as a string. That happens constantly in real
// systems: HTML form fields, CSV imports, sloppy upstream services, Mongo
// documents written by an older version of the code.
//
// Run:  node demos/typing/weak_typing.js

const payload = '{"subtotal": "100", "shipping": 5}';
const order = JSON.parse(payload);

const total = order.subtotal + order.shipping;

console.log("total       =", total);          // "1005"  <-- string concatenation
console.log("typeof      =", typeof total);   // string
console.log("total > 500 =", total > 500);    // true, via silent coercion back to number

// Nothing threw. Nothing logged a warning. The customer is now being charged
// 1005 instead of 105, and the "free shipping over 500" rule just fired.
//
// This is WEAK typing: the `+` operator accepted two different types and
// silently invented a meaning for the combination.
if (total > 500) {
  console.log("=> free shipping applied (WRONG - the real total is 105)");
}
