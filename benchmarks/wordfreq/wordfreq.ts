// Mixed real-world workload: read a text file, count words, print the top 10.
//
// This is the closest of the four benchmarks to actual business code: file I/O,
// string slicing, hash map inserts, and a sort. It is dominated by *library and
// runtime quality* (how good is the string type, how good is the hash map)
// rather than by raw loop speed, which is why the language ranking here looks
// very different from mandelbrot.
//
// Teaching note: `Map<string, number>` is dramatically faster than a plain
// `{}` object for this. Plain objects force V8 into dictionary mode once you
// add tens of thousands of dynamic keys. Try swapping it to see the cost.
import { readFileSync } from "node:fs";

const path: string = process.argv.length > 2 ? process.argv[2] : "data/words.txt";
const text: string = readFileSync(path, "latin1");

const counts = new Map<string, number>();
for (const w of text.split(/\s+/)) {
  if (w.length === 0) continue;
  counts.set(w, (counts.get(w) ?? 0) + 1);
}

const pairs: Array<[string, number]> = Array.from(counts.entries());
pairs.sort((a, b) => (b[1] !== a[1] ? b[1] - a[1] : a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));

console.log(`distinct: ${counts.size}`);
for (const [word, n] of pairs.slice(0, 10)) {
  console.log(`${word} ${n}`);
}
