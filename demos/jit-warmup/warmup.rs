//! "Warm-up" curve for Rust - the other control group.
//!
//! Like Go, Rust is compiled ahead of time, so this line should be FLAT.
//! The difference from Go is what happened at BUILD time rather than run time:
//! rustc/LLVM spent far longer optimising, which is why the Rust build is slow
//! and the Rust binary is quick. That is the AOT bargain in one sentence -
//! you move work from every run to one build.
//!
//! Output: one "batch,milliseconds" line per batch, for run.py to chart.

use std::time::Instant;

const BATCHES: usize = 60;
const CALLS_PER_BATCH: usize = 200;
const SIZE: u32 = 16;
const MAX_ITER: u32 = 50;

#[inline(never)]
fn kernel(n: u32) -> u64 {
    let mut inside: u64 = 0;
    let fnn = n as f64;
    for y in 0..n {
        let ci = 2.0 * (y as f64) / fnn - 1.0;
        for x in 0..n {
            let cr = 2.0 * (x as f64) / fnn - 1.5;
            let mut zr = 0.0f64;
            let mut zi = 0.0f64;
            let mut i = 0u32;
            while i < MAX_ITER && zr * zr + zi * zi <= 4.0 {
                let t = zr * zr - zi * zi + cr;
                zi = 2.0 * zr * zi + ci;
                zr = t;
                i += 1;
            }
            if i == MAX_ITER {
                inside += 1;
            }
        }
    }
    inside
}

fn main() {
    let mut sink: u64 = 0;
    for b in 0..BATCHES {
        let t0 = Instant::now();
        for _ in 0..CALLS_PER_BATCH {
            sink = sink.wrapping_add(kernel(std::hint::black_box(SIZE)));
        }
        println!("{},{:.3}", b, t0.elapsed().as_secs_f64() * 1000.0);
    }
    if sink == u64::MAX {
        println!("unreachable");
    }
}
