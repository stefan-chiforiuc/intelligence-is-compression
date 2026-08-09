//! Directly measure the true cost of one object holding two references.
//! See objsize.py for the method.

const N: usize = 1_000_000;

#[allow(dead_code)]
struct Node {
    l: Option<Box<Node>>,
    r: Option<Box<Node>>,
}

fn rss_bytes() -> i64 {
    let status = std::fs::read_to_string("/proc/self/status").unwrap_or_default();
    for line in status.lines() {
        if let Some(rest) = line.strip_prefix("VmRSS:") {
            if let Some(kb) = rest.split_whitespace().next() {
                return kb.parse::<i64>().unwrap_or(0) * 1024;
            }
        }
    }
    0
}

fn main() {
    let base = rss_bytes();
    let mut keep: Vec<Box<Node>> = Vec::with_capacity(N);
    for _ in 0..N {
        keep.push(Box::new(Node { l: None, r: None }));
    }
    let delta = rss_bytes() - base - (N * 8) as i64; // minus the Vec of pointers

    println!(
        "Rust   {:<14} {:6.1} bytes/node   (RSS delta {:.1} MB for {} nodes)",
        "(Box<Node>)",
        delta as f64 / N as f64,
        delta as f64 / 1048576.0,
        "1,000,000"
    );
    println!(
        "       {:<14} {:6} bytes        (size_of::<Node>() - the data alone)",
        "", std::mem::size_of::<Node>()
    );

    std::hint::black_box(&keep);
}
