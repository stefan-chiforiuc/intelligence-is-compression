#!/usr/bin/env python3
"""BONUS - Python: there is no inference to talk about, because there is no
declared type to infer. A name is just a label you can point at anything.

Run:  python3 demos/typing/var_inference.py

Contrast with the four files next to this one: `var` (Java), `:=` (Go) and
`let` (Rust, TypeScript) each pick ONE concrete type at the declaration and
the compiler enforces it forever after. Reassigning `name` to a different
TYPE, not just a different value, is completely legal here - because in
Python the type lives on the OBJECT, not on the variable.
"""
name = "Ada"
print(type(name).__name__)

name = 42  # perfectly legal: `name` now points at a different kind of thing
print(type(name).__name__)

print()
print("Nothing failed. `name` never had a type of its own to violate -")
print("only the objects it pointed at did, one at a time.")
