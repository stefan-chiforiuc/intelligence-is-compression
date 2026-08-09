// Allocation / GC-bound workload: build and walk many short-lived binary trees.
//
// This is the mirror image of mandelbrot.ts: almost no arithmetic, but millions
// of tiny object allocations with a mix of short-lived garbage and one
// long-lived tree. It is the classic way to expose garbage collector behaviour
// and the true per-object memory overhead of a runtime.
//
// V8's young-generation ("scavenger") collector is very good at exactly this
// shape of garbage, which is why Node does better here than people expect.

const MIN_DEPTH = 4;

class Node {
  l: Node | null;
  r: Node | null;
  constructor(l: Node | null, r: Node | null) {
    this.l = l;
    this.r = r;
  }
}

function make(depth: number): Node {
  if (depth > 0) {
    return new Node(make(depth - 1), make(depth - 1));
  }
  return new Node(null, null);
}

function count(n: Node): number {
  if (n.l === null) {
    return 1;
  }
  return 1 + count(n.l) + count(n.r as Node);
}

const n: number = process.argv.length > 2 ? Number(process.argv[2]) : 16;
const maxDepth: number = Math.max(MIN_DEPTH + 2, n);

const stretchDepth = maxDepth + 1;
console.log(`stretch tree of depth ${stretchDepth}\t check: ${count(make(stretchDepth))}`);

const longLived = make(maxDepth);

for (let depth = MIN_DEPTH; depth <= maxDepth; depth += 2) {
  const iterations = 1 << (maxDepth - depth + MIN_DEPTH);
  let check = 0;
  for (let i = 0; i < iterations; i++) {
    check += count(make(depth));
  }
  console.log(`${iterations}\t trees of depth ${depth}\t check: ${check}`);
}

console.log(`long lived tree of depth ${maxDepth}\t check: ${count(longLived)}`);
