#!/usr/bin/env python3
"""Python: None is a value any name can hold, checked nowhere until it blows
up. Same shape as Java's bug, a different exception type.

Run:  python3 demos/null-safety/null_safety.py
"""
users = {"1": "Ada"}


def get_nickname(user_id):
    return users.get(user_id)  # dict.get returns None on a missing key


name = get_nickname("1")
print(f"user 1: {len(name)} chars")  # fine

# >>> This line runs fine syntactically and crashes at run time. <<<
missing = get_nickname("2")
print(f"user 2: {len(missing)} chars")
# TypeError: object of type 'NoneType' has no len()

# Type hints (`Optional[str]`) let mypy catch this the way Kotlin's compiler
# does, but hints are not enforced at run time by the interpreter itself -
# the same erasure story as TypeScript, one language over.
