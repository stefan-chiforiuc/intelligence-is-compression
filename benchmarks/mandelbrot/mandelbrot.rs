//! CPU-bound workload: count points inside the Mandelbrot set.
//!
//! Pure scalar float math in a tight nested loop. No allocation, no I/O.
//! This isolates *raw interpreter/compiler quality* from everything else.

const MAX_ITER: u32 = 50;

fn mandelbrot(n: u32) -> u64 {
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
    let n: u32 = std::env::args()
        .nth(1)
        .map(|s| s.parse().expect("bad size"))
        .unwrap_or(1000);
    println!("{}", mandelbrot(n));
}
