//! Allocation-bound workload: build and walk many short-lived binary trees.
//!
//! This is the mirror image of mandelbrot.rs. The interesting part for the
//! training: there is no garbage collector here at all. Every `Box` is freed
//! deterministically when it goes out of scope, so the "GC cost" shows up as
//! `malloc`/`free` traffic spread evenly through the run instead of as pauses.

const MIN_DEPTH: u32 = 4;

struct Node {
    l: Option<Box<Node>>,
    r: Option<Box<Node>>,
}

fn make(depth: u32) -> Box<Node> {
    if depth > 0 {
        Box::new(Node {
            l: Some(make(depth - 1)),
            r: Some(make(depth - 1)),
        })
    } else {
        Box::new(Node { l: None, r: None })
    }
}

fn count(node: &Node) -> u64 {
    match (&node.l, &node.r) {
        (Some(l), Some(r)) => 1 + count(l) + count(r),
        _ => 1,
    }
}

fn main() {
    let n: u32 = std::env::args()
        .nth(1)
        .map(|s| s.parse().expect("bad depth"))
        .unwrap_or(16);
    let max_depth = n.max(MIN_DEPTH + 2);

    let stretch_depth = max_depth + 1;
    println!(
        "stretch tree of depth {}\t check: {}",
        stretch_depth,
        count(&make(stretch_depth))
    );

    let long_lived = make(max_depth);

    let mut depth = MIN_DEPTH;
    while depth <= max_depth {
        let iterations = 1u64 << (max_depth - depth + MIN_DEPTH);
        let mut check: u64 = 0;
        for _ in 0..iterations {
            check += count(&make(depth));
        }
        println!("{}\t trees of depth {}\t check: {}", iterations, depth, check);
        depth += 2;
    }

    println!(
        "long lived tree of depth {}\t check: {}",
        max_depth,
        count(&long_lived)
    );
}
