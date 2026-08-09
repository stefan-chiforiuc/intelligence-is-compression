#!/usr/bin/env python3
"""DEMO 2 - Python: dynamically typed but STRONGLY typed.

Same bad payload as the JavaScript demo. Python does not have static types
either, so the compiler catches nothing. But Python refuses to guess what
`"100" + 5` means, so the bug becomes a loud crash instead of a wrong number.

This is the distinction almost every junior gets wrong:
    static vs dynamic  = WHEN are types checked (compile time vs run time)
    strong vs weak     = HOW MUCH implicit coercion does the language do

They are independent axes. Python is dynamic + strong. JavaScript is
dynamic + weak. Java, Go and Rust are static + strong.

Run:  python3 demos/typing/strong_typing.py
"""
import json

payload = '{"subtotal": "100", "shipping": 5}'
order = json.loads(payload)

try:
    total = order["subtotal"] + order["shipping"]
    print("total =", total)
except TypeError as exc:
    print("TypeError:", exc)
    print()
    print("Python refused to guess. This is a *better* failure than JavaScript's:")
    print("it happens immediately, at the line that is actually wrong, with a")
    print("stack trace pointing at the culprit - not three services downstream")
    print("in a billing report next Tuesday.")

# The catch: this is still a RUNTIME failure. It only happens if this line
# actually executes. If it lives in a rarely-taken branch (a refund path, a
# specific currency, a leap-year edge case) it ships to production happily and
# waits. That is the gap static typing closes.
