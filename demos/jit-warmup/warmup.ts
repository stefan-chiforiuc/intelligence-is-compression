// JIT warm-up curve for V8, measured from INSIDE one process.
//
// V8 has its own tiered pipeline: Ignition (bytecode interpreter) -> Sparkplug
// (baseline) -> Maglev -> TurboFan (optimising). You should see the same shape
// as the JVM: expensive first batches, then a plateau.
//
// You may also see a batch SPIKE partway through. That is usually a
// deoptimisation: TurboFan made an assumption, the assumption was violated,
// and it bailed back to the interpreter to recompile. That is the hidden cost
// of speculative optimisation, and it is worth pointing at when it happens.
//
// Output: one "batch,milliseconds" line per batch, for run.py to chart.

const BATCHES = 60;
const CALLS_PER_BATCH = 200;
const SIZE = 16;
const MAX_ITER = 50;

function kernel(n: number): number {
  let inside = 0;
  for (let y = 0; y < n; y++) {
    const ci = (2.0 * y) / n - 1.0;
    for (let x = 0; x < n; x++) {
      const cr = (2.0 * x) / n - 1.5;
      let zr = 0.0;
      let zi = 0.0;
      let i = 0;
      while (i < MAX_ITER && zr * zr + zi * zi <= 4.0) {
        const t = zr * zr - zi * zi + cr;
        zi = 2.0 * zr * zi + ci;
        zr = t;
        i++;
      }
      if (i === MAX_ITER) inside++;
    }
  }
  return inside;
}

let sink = 0;
for (let b = 0; b < BATCHES; b++) {
  const t0 = process.hrtime.bigint();
  for (let c = 0; c < CALLS_PER_BATCH; c++) {
    sink += kernel(SIZE);
  }
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  console.log(`${b},${ms.toFixed(3)}`);
}
if (sink === Number.MIN_SAFE_INTEGER) console.log("unreachable");
