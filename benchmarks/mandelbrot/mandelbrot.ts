// CPU-bound workload: count points inside the Mandelbrot set.
//
// Pure scalar float math in a tight nested loop. No allocation, no I/O.
// This isolates *raw interpreter/compiler quality* from everything else.
//
// Note for the training: every type annotation below is ERASED at compile time.
// It helps the human and the editor; it does nothing for the CPU. What makes
// this fast is V8's JIT noticing the loop is monomorphic float64 arithmetic.

const MAX_ITER = 50;

function mandelbrot(n: number): number {
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
      if (i === MAX_ITER) {
        inside++;
      }
    }
  }
  return inside;
}

const n: number = process.argv.length > 2 ? Number(process.argv[2]) : 1000;
console.log(mandelbrot(n));
