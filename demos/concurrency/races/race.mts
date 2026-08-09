// JavaScript/Node: why this program is BORING, and why that is the interesting part.
//
//   node build/demos/concurrency/race.mjs
//
// A classic data race needs two things: two threads, and shared mutable memory.
// Plain JavaScript gives you neither. The event loop is single-threaded, and
// worker_threads each get their OWN V8 isolate and heap — objects are
// structured-cloned between them, not shared.
//
// So JavaScript never needed a GIL and never had this bug class. It bought that
// by giving up CPU parallelism entirely, until worker_threads arrived.
//
// The catch, shown below: `SharedArrayBuffer` DOES give you genuinely shared
// memory across workers, and with it the races come straight back. That is why
// `Atomics` exists. If you use SharedArrayBuffer, you are writing the same
// concurrent code as everyone else, with the same hazards and fewer guardrails.
//
// Also worth saying out loud: single-threaded does NOT mean free of concurrency
// bugs. Interleaved `await` points are a real source of logical races —
// check-then-act across an await is the JavaScript equivalent of a TOCTOU bug.
import { Worker, isMainThread, workerData } from "node:worker_threads";

const THREADS = 4;
const INCREMENTS = 200_000;

if (!isMainThread) {
  const { buf, useAtomics } = workerData as { buf: SharedArrayBuffer; useAtomics: boolean };
  const view = new Int32Array(buf);
  for (let i = 0; i < INCREMENTS; i++) {
    if (useAtomics) {
      Atomics.add(view, 0, 1);       // indivisible
    } else {
      view[0] = view[0] + 1;         // <-- read, add, write: a real data race
    }
  }
} else {
  // 1. Plain single-threaded increments: no race is even possible.
  let plain = 0;
  for (let i = 0; i < THREADS * INCREMENTS; i++) plain++;

  const runWorkers = (useAtomics: boolean): Promise<number> => {
    const buf = new SharedArrayBuffer(4);
    const view = new Int32Array(buf);
    return new Promise((resolve) => {
      let done = 0;
      for (let t = 0; t < THREADS; t++) {
        const w = new Worker(new URL(import.meta.url), { workerData: { buf, useAtomics } });
        w.on("exit", () => {
          if (++done === THREADS) resolve(view[0]!);
        });
      }
    });
  };

  const expected = THREADS * INCREMENTS;
  const racy = await runWorkers(false);
  const atomic = await runWorkers(true);

  console.log(`Node   expected      ${expected}`);
  console.log(`Node   single-thread ${plain}   (no threads, no race, ever)`);
  console.log(`Node   SharedArrayBuffer, plain writes  ${racy}   (lost ${expected - racy})`);
  console.log(`Node   SharedArrayBuffer, Atomics.add   ${atomic}`);
}
