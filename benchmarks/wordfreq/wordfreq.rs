//! Mixed real-world workload: read a text file, count words, print the top 10.
//!
//! This is the closest of the four benchmarks to actual business code: file
//! I/O, string slicing, hash map inserts, and a sort. It is dominated by
//! *library and runtime quality* rather than raw loop speed.
//!
//! Teaching note: Rust's default hasher (SipHash) is deliberately slower than
//! Go's or Java's because it is DoS-resistant. Swapping in FxHash via a crate
//! typically wins another 30-40% here. "Rust is fast" is not automatic — you
//! still have to know what the defaults are optimising for.

use std::collections::HashMap;

fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| "data/words.txt".to_string());
    let text = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        eprintln!("read {path}: {e}");
        std::process::exit(1);
    });

    // &str keys borrow directly from `text` — no per-word heap allocation at all.
    let mut counts: HashMap<&str, u32> = HashMap::with_capacity(1 << 16);
    for w in text.split_ascii_whitespace() {
        *counts.entry(w).or_insert(0) += 1;
    }

    let mut pairs: Vec<(&&str, &u32)> = counts.iter().collect();
    pairs.sort_unstable_by(|a, b| b.1.cmp(a.1).then_with(|| a.0.cmp(b.0)));

    println!("distinct: {}", counts.len());
    for (word, n) in pairs.iter().take(10) {
        println!("{word} {n}");
    }
}
