// TypeScript: null safety is REAL at compile time, OPT-IN, and ERASED at run
// time - all three at once. This is the direct sequel to demos/typing/erasure.ts.
//
// Run WITHOUT strict null checks (the historical default - accepted, then crashes):
//   npx tsc demos/null-safety/null_safety.ts --outDir build/demos/nullsafety \
//       --target es2022 --module nodenext --moduleResolution nodenext --skipLibCheck
//   node build/demos/nullsafety/null_safety.js
//
// Check WITH strict null checks (recommended in every tsconfig written after ~2018):
//   npx tsc demos/null-safety/null_safety.ts --noEmit \
//       --target es2022 --module nodenext --moduleResolution nodenext --skipLibCheck \
//       --strictNullChecks
//   -> error TS18048: 'missing' is possibly 'undefined'.
//      (older TypeScript versions report this as TS2532.)

const users = new Map<string, string>([["1", "Ada"]]);

function getNickname(id: string): string | undefined {
  return users.get(id);
}

const name = getNickname("1");
console.log(`user 1: ${name!.length} chars`); // `!` = "trust me" - same shape as Kotlin's `!!`

const missing = getNickname("2");

// >>> Without --strictNullChecks: tsc accepts this line, node crashes.     <<<
// >>> With --strictNullChecks:    tsc rejects it before node ever runs.    <<<
console.log(`user 2: ${missing.length} chars`);

// The fix reads exactly like Kotlin's safe call - same idea, opt-in language:
//   console.log(`user 2: ${missing?.length ?? "no nickname"}`);
//
// And the erasure twist: compile the fixed version and open the emitted .js.
// The `?.` and the type that justified skipping it are BOTH gone - it is a
// plain property access with a plain guard, indistinguishable from code that
// was never type-checked at all. TypeScript's null safety protects your
// source, not your boundary, and only for the files that opted in.
