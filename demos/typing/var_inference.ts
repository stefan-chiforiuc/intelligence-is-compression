// BONUS - TypeScript inferred `let`: static too, and STILL erased.
//
// Run:
//   npx tsc demos/typing/var_inference.ts --outDir build/demos --target es2022 \
//       --module nodenext --moduleResolution nodenext --skipLibCheck --types node
//
// Expected (from tsc itself - it refuses to emit):
//   error TS2322: Type 'number' is not assignable to type 'string'.
//
// `let name = "Ada"` infers `name`'s type from its initializer, exactly like
// `var` in Java and `:=` in Go. The difference from Java/Go/Rust shows up a
// moment later, not here: run demos/typing/erasure.ts right after this one -
// an inferred type is enforced at compile time, and a moment after
// compilation it no longer exists to enforce anything.

let name = "Ada"; // inferred once: string

// >>> This is the line tsc will reject. <<<
name = 42;
console.log(name);
