//! DEMO 4c - Rust: static + strong, and the strictest of the five.
//!
//! Run:  rustc --edition 2021 demos/typing/wont_compile.rs -o /dev/null
//!
//! Expected:
//!   error[E0369]: cannot add `{integer}` to `&str`
//!
//! Rust goes further than Java or Go: there is no implicit numeric widening
//! either. `let x: i64 = 5i32;` is also an error. Even `u32 + i32` is an error.
//!
//! That strictness is the whole trade: more of your bugs become compile
//! errors, and more of your Tuesday afternoon becomes an argument with the
//! compiler. Whether that is a good deal depends entirely on what the software
//! does. For a payment ledger or a flight controller it is a bargain. For a
//! throwaway data-cleaning script it is a tax with no return.

fn main() {
    let subtotal = "100";
    let shipping = 5;

    // >>> This is the line that will not compile. <<<
    let total = subtotal + shipping;
    println!("{}", total);
}
