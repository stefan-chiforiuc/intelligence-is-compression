//! BONUS - Rust `let`: inferred, static, and immutable by default.
//!
//! Run:  rustc --edition 2021 demos/typing/var_inference.rs -o /dev/null
//!
//! Expected:
//!   error[E0308]: mismatched types
//!
//! `let` infers one concrete type at the declaration, same as `var` and `:=`.
//! `mut` is added here on purpose so the ONLY error below is the type
//! mismatch - Rust would also reject reassigning a same-typed value to a
//! non-`mut` binding, but that is a separate axis (immutability-by-default),
//! not the one this file is about.

fn main() {
    let mut name = "Ada"; // inferred once: &str
    println!("{name}");

    // >>> This is the line that will not compile - wrong type, not wrong mutability. <<<
    name = 42;
    println!("{name}");
}
