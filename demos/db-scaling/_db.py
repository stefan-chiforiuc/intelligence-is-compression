"""Shared plumbing for the real-database demos.

Resolution order matches demos/db-scaling/db.sh:
  1. $TRAINING_DB_URL
  2. the Docker container on 127.0.0.1:55432
  3. a local PostgreSQL on 127.0.0.1:5432

If none is reachable, the caller is told to fall back to the simulation. We
never quietly pretend — a demo that silently switches to fake data is worse
than no demo.
"""
from __future__ import annotations

import os
import sys

CANDIDATES = [
    "postgresql://training:training@127.0.0.1:55432/training",   # docker-compose
    "postgresql://training:training@127.0.0.1:5432/training",    # local install
]


def _import_psycopg():
    try:
        import psycopg  # noqa: F401
        return psycopg
    except ImportError:
        return None


def resolve_url() -> str | None:
    psycopg = _import_psycopg()
    if psycopg is None:
        return None
    urls = [os.environ["TRAINING_DB_URL"]] if os.environ.get("TRAINING_DB_URL") else CANDIDATES
    for url in urls:
        try:
            with psycopg.connect(url, connect_timeout=3):
                return url
        except Exception:
            continue
    return None


def require_db(demo_name: str) -> str:
    """Return a working URL, or explain what to do and exit non-zero."""
    if _import_psycopg() is None:
        print("psycopg is not installed.\n")
        print("  pip install 'psycopg[binary]'\n")
        print(f"Until then, the simulated version of this demo is available:")
        print(f"  python3 demos/db-scaling/{demo_name}")
        sys.exit(2)

    url = resolve_url()
    if url is None:
        print("No training database reachable.\n")
        print("Start one (1 CPU, 512 MB, max_connections=50):")
        print("  bash demos/db-scaling/db.sh up\n")
        print("Or point at an existing PostgreSQL:")
        print("  export TRAINING_DB_URL=postgresql://user:pass@host:5432/db\n")
        print("Or run the simulated version, which needs nothing:")
        print(f"  python3 demos/db-scaling/{demo_name}")
        sys.exit(2)
    return url


def server_facts(url: str) -> dict[str, str]:
    import psycopg
    facts: dict[str, str] = {}
    with psycopg.connect(url) as con:
        for name in ("max_connections", "shared_buffers", "server_version"):
            row = con.execute("SELECT setting FROM pg_settings WHERE name = %s", (name,)).fetchone()
            if row:
                facts[name] = row[0]
        row = con.execute("SELECT count(*) FROM pg_stat_activity").fetchone()
        facts["in_use"] = str(row[0]) if row else "?"
    return facts


def banner(url: str) -> None:
    facts = server_facts(url)
    safe = url.split("@")[-1] if "@" in url else url
    print(f"Database        : {safe}")
    print(f"PostgreSQL      : {facts.get('server_version', '?')}")
    print(f"max_connections : {facts.get('max_connections', '?')}"
          f"   (in use right now: {facts.get('in_use', '?')})")
    print()
