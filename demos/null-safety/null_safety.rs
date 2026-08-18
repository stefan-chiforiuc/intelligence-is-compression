//! Rust: there is no null. Absence is a value, Option<T>, and the compiler
//! will not let you use the T until you have handled the None case.
//!
//! Run:  rustc --edition 2021 demos/null-safety/null_safety.rs -o build/demos/nullsafety/null_safety_rs
//!       build/demos/nullsafety/null_safety_rs

use std::collections::HashMap;

fn get_nickname<'a>(users: &'a HashMap<&str, &str>, id: &str) -> Option<&'a str> {
    users.get(id).copied()
}

fn main() {
    let mut users = HashMap::new();
    users.insert("1", "Ada");

    // >>> Uncomment: does not compile. <<<
    // let name = get_nickname(&users, "1");
    // println!("{}", name.len());
    //   error[E0624]: method `len` is private
    //   (other rustc versions report E0599: no method named `len` found for
    //   enum `Option<&str>` - either message says the same thing: `Option<&str>`
    //   and `&str` are different types, and this one doesn't have `.len()`.)

    match get_nickname(&users, "1") {
        Some(n) => println!("user 1: {} chars", n.len()),
        None => println!("user 1: no nickname"),
    }

    match get_nickname(&users, "2") {
        Some(n) => println!("user 2: {} chars", n.len()),
        None => println!("user 2: no nickname"),
    }

    // The escape hatch exists here too, and it is just as visible as Kotlin's !!:
    // let forced = get_nickname(&users, "2").unwrap(); // panics, but the call says so
}
