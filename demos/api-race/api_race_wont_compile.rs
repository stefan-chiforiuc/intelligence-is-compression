//! The same API, in Rust. This file DOES NOT COMPILE, and that is the point.
//!
//!   rustc --edition 2021 demos/api-race/api_race_wont_compile.rs -o /dev/null
//!
//! In Java, `private final List<String> items = new ArrayList<>();` as a
//! controller field is ordinary-looking code that every request thread shares.
//! It compiles, it passes review, it passes tests, and it silently loses data
//! under load — as the Java demo just showed, 2,343 items out of 200,000.
//!
//! Here is the identical design in Rust. It cannot be built.

use std::net::TcpListener;
use std::thread;

const ITEMS_PER_REQUEST: usize = 200;

fn main() {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");

    // The shared state. Exactly the Java field: a plain growable vector.
    let mut items: Vec<String> = Vec::new();

    for stream in listener.incoming() {
        let stream = stream.expect("accept");

        // >>> This is what will not compile. <<<
        //
        //   error[E0382]: use of moved value: `items`
        //                 value moved into closure here, in previous iteration of loop
        //
        // Note there are TWO doors and both are locked, which is worth showing
        // the room because students always try the other one:
        //
        //   * WITH `move` (as written): the vector is moved into the first
        //     handler's closure. The second request has nothing left to append
        //     to. E0382.
        //
        //   * WITHOUT `move`: the closure borrows `items`, and the compiler
        //     cannot prove the thread ends before `items` is dropped.
        //     E0373 "closure may outlive the current function".
        //
        // There is no arrangement of `mut`, `&` or `clone()` that gives twenty
        // handler threads one shared vector. To share it you must SAY HOW IT IS
        // SYNCHRONISED — which is exactly what api_race.rs does.
        thread::spawn(move || {
            let _ = &stream;
            for i in 0..ITEMS_PER_REQUEST {
                items.push(format!("item-{i}"));
            }
        });
    }
}
