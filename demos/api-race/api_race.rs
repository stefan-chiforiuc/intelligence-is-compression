//! The same API as ApiRace.java: a real HTTP server, 20 concurrent users,
//! one shared vector. Standard library only — no crates, no framework.
//!
//!   rustc -O --edition 2021 demos/api-race/api_race.rs -o build/demos/apirace/api_race_rs
//!   build/demos/apirace/api_race_rs
//!
//! The Java version needed you to REMEMBER to synchronise, and silently lost
//! 2,343 of 200,000 items when a developer forgot. This version cannot lose
//! anything, because the unsynchronised design does not compile
//! (see api_race_wont_compile.rs).
//!
//! Read the type out loud — it is the entire lesson:
//!
//!     Arc<Mutex<Vec<String>>>
//!      |    |     |
//!      |    |     +-- the data
//!      |    +-------- you may only touch it while holding the lock
//!      +------------- shared ownership across threads, refcounted
//!
//! In Java, "this list is guarded by that lock" is a fact that lives in a
//! comment, or in a code reviewer's memory. Here it is in the type, and the
//! compiler checks it on every single access.

use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Instant;

const USERS: usize = 20;
const REQUESTS_PER_USER: usize = 50;
const ITEMS_PER_REQUEST: usize = 200;
const EXPECTED: usize = USERS * REQUESTS_PER_USER * ITEMS_PER_REQUEST;

/// Minimal HTTP/1.1 handling: read the request line + headers, read the body if
/// Content-Length says there is one, reply 204. Enough to be a real server.
fn handle(mut stream: TcpStream, items: &Arc<Mutex<Vec<String>>>, counter: &Arc<AtomicU64>) {
    let mut reader = BufReader::new(stream.try_clone().expect("clone"));
    let mut content_length = 0usize;

    let mut line = String::new();
    if reader.read_line(&mut line).unwrap_or(0) == 0 {
        return; // client closed
    }
    loop {
        let mut header = String::new();
        if reader.read_line(&mut header).unwrap_or(0) == 0 {
            break;
        }
        if header == "\r\n" || header == "\n" {
            break;
        }
        let lower = header.to_ascii_lowercase();
        if let Some(rest) = lower.strip_prefix("content-length:") {
            content_length = rest.trim().parse().unwrap_or(0);
        }
    }
    if content_length > 0 {
        let mut body = vec![0u8; content_length];
        let _ = reader.read_exact(&mut body);
    }

    // The shared append. `lock()` returns a guard; the Vec is unreachable
    // without it. Forgetting to lock is not a discipline problem here — there
    // is no expression that reaches the data without going through the Mutex.
    {
        let mut guard = items.lock().expect("poisoned");
        for i in 0..ITEMS_PER_REQUEST {
            guard.push(format!("item-{i}"));
        }
    } // guard drops here, lock released — you cannot forget to unlock either

    counter.fetch_add(1, Ordering::Relaxed);
    let _ = stream.write_all(b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
    let _ = stream.flush();
}

fn main() {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().expect("addr").port();

    let items: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
    let served = Arc::new(AtomicU64::new(0));

    // Server accept loop, on its own thread.
    {
        let items = Arc::clone(&items);
        let served = Arc::clone(&served);
        thread::spawn(move || {
            for stream in listener.incoming() {
                match stream {
                    Ok(s) => {
                        let items = Arc::clone(&items);
                        let served = Arc::clone(&served);
                        // One thread per connection. Arc::clone is what makes
                        // "shared" explicit and cheap: a refcount bump.
                        thread::spawn(move || handle(s, &items, &served));
                    }
                    Err(_) => break,
                }
            }
        });
    }

    println!("Rust server on port {port}");
    println!(
        "{USERS} users x {REQUESTS_PER_USER} requests x {ITEMS_PER_REQUEST} items per request = {EXPECTED} expected items\n"
    );

    let start = Instant::now();
    let mut users = Vec::new();
    for u in 0..USERS {
        users.push(thread::spawn(move || {
            for r in 0..REQUESTS_PER_USER {
                let body = format!("user-{u}-item-{r}");
                if let Ok(mut s) = TcpStream::connect(("127.0.0.1", port)) {
                    let req = format!(
                        "POST /items HTTP/1.1\r\nHost: localhost\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                        body.len(),
                        body
                    );
                    let _ = s.write_all(req.as_bytes());
                    let _ = s.flush();
                    let mut sink = Vec::new();
                    let _ = s.read_to_end(&mut sink);
                }
            }
        }));
    }
    for u in users {
        let _ = u.join();
    }
    let ms = start.elapsed().as_millis();

    let actual = items.lock().expect("poisoned").len();
    println!("{:<32} {:>10} {:>10} {:>8}   {}",
             "Implementation", "expected", "actual", "ms", "verdict");
    println!("{}", "-".repeat(76));
    println!(
        "{:<32} {:>10} {:>10} {:>8}   {}",
        "Arc<Mutex<Vec<String>>>",
        EXPECTED,
        actual,
        ms,
        if actual == EXPECTED { "correct" } else { "LOST ITEMS" }
    );
    println!(
        "{:<32} {:>10} {:>10} {:>8}   {}",
        "Vec<String>, no Mutex", EXPECTED, "-", "-", "DOES NOT COMPILE"
    );

    println!(
        "
WHY THE BUG IS UNREACHABLE HERE
===============================

  Java's ArrayList and Rust's Vec are the same data structure with the same
  hazard. The difference is not the collection - it is that Rust tracks, in the
  type system, whether a value may be shared between threads:

      Send   this value may be MOVED to another thread
      Sync   this value may be SHARED (&T) between threads

  `Vec<String>` is Send but NOT Sync. So `&Vec<String>` cannot cross a thread
  boundary, full stop. `Mutex<Vec<String>>` IS Sync - because the Mutex is what
  makes concurrent access safe - and `Arc` provides the shared ownership. The
  compiler will not let you skip either one.

  Two consequences worth stating explicitly:

  1. You cannot forget to LOCK. The Vec lives inside the Mutex; there is no
     path to the data that does not go through lock().
  2. You cannot forget to UNLOCK. The guard releases on drop, including if the
     thread panics mid-update.

  AND THE HONEST LIMIT
  This buys you freedom from DATA races. It does not buy correctness. This
  program could still deadlock by taking two locks in the wrong order, or hold
  the lock too long and serialise every request - note that this whole demo has
  exactly one global lock, which is the worst possible design for throughput.
  Rust removes a bug class. It does not remove the need to think."
    );
}
