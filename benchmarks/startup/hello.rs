//! Cold-start workload: do essentially nothing, as fast as possible.
//!
//! Everything this program measures happens BEFORE your business logic runs:
//! process spawn, dynamic linking, runtime initialisation. That fixed cost is
//! what you pay on every single serverless invocation and on every pod restart
//! during a rolling deploy.
//!
//! Rust has essentially no runtime to initialise, so what you measure here is
//! close to the floor imposed by the operating system's `execve` itself.

fn main() {
    let n: i64 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(1);
    println!("ready {}", n * 2);
}
