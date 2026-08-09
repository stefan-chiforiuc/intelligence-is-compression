// Directly measure the true cost of one object holding two references.
// See objsize.py for the method.
import { readFileSync } from "node:fs";

const N = 1_000_000;

class Node {
  l: Node | null = null;
  r: Node | null = null;
}

function rssBytes(): number {
  const status = readFileSync("/proc/self/status", "utf8");
  for (const line of status.split("\n")) {
    if (line.startsWith("VmRSS:")) {
      return Number(line.replace(/[^0-9]/g, "")) * 1024;
    }
  }
  return 0;
}

const base = rssBytes();
const keep: Array<Node | null> = new Array(N);
for (let i = 0; i < N; i++) {
  keep[i] = new Node();
}
const delta = rssBytes() - base - N * 8; // minus the array of pointers

console.log(
  `Node   ${"(class Node)".padEnd(14)} ${(delta / N).toFixed(1).padStart(6)} bytes/node   ` +
    `(RSS delta ${(delta / 1048576).toFixed(1)} MB for ${N.toLocaleString()} nodes)`,
);

// Keep it reachable past the measurement.
if (keep[N - 1] === null && keep[0] !== null) console.log("unreachable");
