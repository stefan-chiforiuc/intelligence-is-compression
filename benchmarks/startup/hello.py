#!/usr/bin/env python3
"""Cold-start workload: do essentially nothing, as fast as possible.

Everything this program measures happens BEFORE your business logic runs:
process spawn, dynamic linking, runtime/VM initialisation, bytecode loading.
That fixed cost is what you pay on every single serverless invocation and on
every pod restart during a rolling deploy.
"""
import sys

n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
print(f"ready {n * 2}")
