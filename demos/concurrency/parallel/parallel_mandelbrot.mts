// Parallel Mandelbrot in Node: worker_threads.
//
//   node build/js-demos/parallel_mandelbrot.js <n> <workers>
//
// JavaScript's concurrency model is a SINGLE-THREADED event loop. `async`/
// `await` and Promises give you concurrency for I/O — while one request waits
// on the network, others run — but they give you ZERO parallelism for CPU work.
// An await in a hot loop does not add a core; a long synchronous computation
// blocks the entire process, including the HTTP server.
//
// `worker_threads` is the escape hatch: real OS threads, each with its OWN V8
// isolate and its own heap. Because the heaps are separate, nothing is shared
// by default and messages are structured-cloned between them (or shared
// explicitly via SharedArrayBuffer). That is why JavaScript has never needed a
// GIL and has never had classic data races: there was never shared mutable
// state to race over.
//
// Note the cost: each worker boots a fresh V8 isolate (~30 ms and ~40 MB), so
// worker_threads pays off only for chunky work, not per-request fan-out.
import { Worker, isMainThread, parentPort, workerData } from "node:worker_threads";

const MAX_ITER = 50;

function band(n: number, y0: number, y1: number): number {
  let inside = 0;
  for (let y = y0; y < y1; y++) {
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

interface Job {
  n: number;
  y0: number;
  y1: number;
}

if (!isMainThread) {
  // Worker path: this same file, re-executed inside a fresh isolate.
  const { n, y0, y1 } = workerData as Job;
  parentPort!.postMessage(band(n, y0, y1));
} else {
  const n = process.argv.length > 2 ? Number(process.argv[2]) : 1000;
  const workers = process.argv.length > 3 ? Number(process.argv[3]) : 1;

  const step = Math.ceil(n / workers);
  const t0 = process.hrtime.bigint();

  if (workers === 1) {
    const total = band(n, 0, n);
    const ms = Number(process.hrtime.bigint() - t0) / 1e6;
    console.log(`inside=${total} workers=1 ms=${ms.toFixed(1)}`);
  } else {
    const jobs: Job[] = [];
    for (let y = 0; y < n; y += step) {
      jobs.push({ n, y0: y, y1: Math.min(y + step, n) });
    }

    let done = 0;
    let total = 0;
    for (const job of jobs) {
      const worker = new Worker(new URL(import.meta.url), { workerData: job });
      worker.on("message", (v: number) => {
        total += v;
        if (++done === jobs.length) {
          const ms = Number(process.hrtime.bigint() - t0) / 1e6;
          console.log(`inside=${total} workers=${workers} ms=${ms.toFixed(1)}`);
        }
      });
      worker.on("error", (e) => {
        console.error("worker error:", e);
        process.exit(1);
      });
    }
  }
}
