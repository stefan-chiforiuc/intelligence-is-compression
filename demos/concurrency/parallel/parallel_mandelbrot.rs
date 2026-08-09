//! Parallel Mandelbrot in Rust: `std::thread::scope`, no external crates.
//!
//!     parallel_mandelbrot_rs <n> <workers>
//!
//! The interesting part is what the compiler is checking while you write this.
//! Rust's `Send` and `Sync` marker traits encode "may be moved to another
//! thread" and "may be shared between threads" IN THE TYPE SYSTEM. A data race
//! is therefore not a bug you find with a race detector at run time — it is a
//! type error.
//!
//! `thread::scope` (stable since 1.63) lets threads borrow from the parent
//! stack, because the compiler can prove they all finish before the scope ends.
//! Before it existed you needed `Arc` just to share read-only data.
//!
//! See ../races/ for the version that refuses to compile.

const MAX_ITER: u32 = 50;

fn band(n: u32, y0: u32, y1: u32) -> u64 {
    let mut inside: u64 = 0;
    let fnn = n as f64;
    for y in y0..y1 {
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
    let mut args = std::env::args().skip(1);
    let n: u32 = args.next().and_then(|s| s.parse().ok()).unwrap_or(1000);
    let workers: u32 = args.next().and_then(|s| s.parse().ok()).unwrap_or(1);

    let step = (n + workers - 1) / workers;
    let start = std::time::Instant::now();

    let mut totals = vec![0u64; workers as usize];

    std::thread::scope(|s| {
        // Split the result vector into disjoint mutable slices. The borrow
        // checker verifies they do not overlap, which is exactly why no lock
        // is needed and no race is possible.
        for (w, slot) in totals.iter_mut().enumerate() {
            let y0 = w as u32 * step;
            let y1 = (y0 + step).min(n);
            if y0 >= n {
                continue;
            }
            s.spawn(move || {
                *slot = band(n, y0, y1);
            });
        }
    });

    let total: u64 = totals.iter().sum();
    let ms = start.elapsed().as_secs_f64() * 1000.0;
    println!("inside={} workers={} ms={:.1}", total, workers, ms);
}
