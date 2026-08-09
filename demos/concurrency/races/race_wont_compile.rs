//! Rust: the same program, which DOES NOT COMPILE — and that is the whole point.
//!
//!   rustc --edition 2021 demos/concurrency/races/race_wont_compile.rs -o /dev/null
//!
//! Expected:
//!   error[E0499]: cannot borrow `counter` as mutable more than once at a time
//!
//! This is the concurrency twin of the typing demo in Block 1. In Go and Java
//! the racy program builds fine and gives a different wrong answer every run.
//! In Rust the class of bug does not survive `cargo build`.
//!
//! The mechanism is two marker traits the compiler tracks for every type:
//!   Send  — this value may be MOVED to another thread
//!   Sync  — this value may be SHARED (&T) between threads
//! Combined with the borrow checker's "one mutable borrow XOR many shared
//! borrows" rule, unsynchronised shared mutation becomes unrepresentable.
//!
//! Rust calls this "fearless concurrency". It is not that races are impossible
//! in principle — `unsafe` still exists, and logical races like deadlocks and
//! lost wakeups are entirely possible — but the specific bug below cannot be
//! written by accident.
//!
//! The correct versions are in race_fixed.rs.

use std::thread;

const THREADS: usize = 8;
const INCREMENTS: usize = 100_000;

fn main() {
    let mut counter: u64 = 0;

    thread::scope(|s| {
        for _ in 0..THREADS {
            // >>> This is the line that will not compile. <<<
            // Every spawned closure wants `&mut counter`, and the compiler
            // refuses to hand out a second mutable borrow while the first is
            // still alive.
            s.spawn(|| {
                for _ in 0..INCREMENTS {
                    counter += 1;
                }
            });
        }
    });

    println!("{counter}");
}
