//! Rust: the two ways to say "yes, I really do want to share this".
//!
//! The compiler rejected the naive version (race_wont_compile.rs). It does not
//! forbid sharing — it forbids sharing WITHOUT SAYING SO. Both fixes below make
//! the synchronisation strategy part of the type.
//!
//! Read the types out loud in the session:
//!   Mutex<u64>     — "a u64 you can only touch while holding the lock"
//!   AtomicU64      — "a u64 whose reads and writes are indivisible"
//! In Go and Java the equivalent knowledge lives in a comment, or in someone's
//! head. Here it is checked.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::thread;

const THREADS: usize = 8;
const INCREMENTS: usize = 100_000;

fn main() {
    let expected = (THREADS * INCREMENTS) as u64;

    // --- 1. A mutex --------------------------------------------------------
    // You cannot read the u64 without locking, because the u64 is INSIDE the
    // Mutex. Forgetting to lock is not a discipline problem; it does not typecheck.
    let guarded = Mutex::new(0u64);
    thread::scope(|s| {
        for _ in 0..THREADS {
            s.spawn(|| {
                for _ in 0..INCREMENTS {
                    *guarded.lock().unwrap() += 1;
                }
            });
        }
    });

    // --- 2. An atomic ------------------------------------------------------
    // Note that Rust forces you to name the memory ORDERING. That is more
    // ceremony than Java's incrementAndGet(), and it is deliberate: the cost of
    // SeqCst vs Relaxed is real, and the language makes you decide rather than
    // silently picking the expensive one.
    let counter = AtomicU64::new(0);
    thread::scope(|s| {
        for _ in 0..THREADS {
            s.spawn(|| {
                for _ in 0..INCREMENTS {
                    counter.fetch_add(1, Ordering::Relaxed);
                }
            });
        }
    });

    println!("Rust   expected      {expected}");
    println!("Rust   Mutex<u64>    {}", guarded.lock().unwrap());
    println!("Rust   AtomicU64     {}", counter.load(Ordering::SeqCst));
    println!("Rust   racy          <does not compile - see race_wont_compile.rs>");
}
